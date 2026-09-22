# ping-optimizer-windows

This is a utility to automatically optimize network routing on Windows machines with multiple active gateways (such as dual-WAN setups, VPN + local ISP, or concurrent Wi-Fi and Ethernet connections).

It pings target endpoints through each active local interface, compares the average latency, and dynamically updates the Windows static routing table to direct traffic to those targets through the lowest-latency gateway.

## Installation

No third-party packages are required. The script uses standard Windows system binaries (`ping.exe` and `route.exe`) and the Python standard library.

Clone the repository and run the optimizer from an elevated command prompt (Administrator privileges are required to modify the system routing table).

## How to run

Create a config file with target hosts and their associated IP ranges:

```json
{
  "destinations": [
    {
      "name": "Work VPN Gateway",
      "host": "vpn.mycompany.com",
      "subnets": ["10.0.0.0/8", "192.168.10.0/24"]
    },
    {
      "name": "Game Server",
      "host": "104.16.0.1",
      "subnets": ["104.16.0.0/16"]
    }
  ]
}
```

Run the optimization once:

    python ping_opt.py --config targets.json

To keep checking in the background and updating routes as network conditions fluctuate, pass the interval flag (in seconds):

    python ping_opt.py --config targets.json --interval 300

<!-- updated: 2026-09-22 -->
