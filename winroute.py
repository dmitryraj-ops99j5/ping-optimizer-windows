import subprocess
import ctypes
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Route:
    destination: str
    netmask: str
    gateway: str
    interface: str
    metric: int

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False

def get_active_routes() -> List[Route]:
    """Parse the Windows routing table to find current active IPv4 routes."""
    # Using route print -4 to keep parsing simple and ignore IPv6
    res = subprocess.run(["route", "print", "-4"], capture_output=True, text=True, check=True)
    routes = []
    in_active_section = False
    
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Active Routes:" in line:
            in_active_section = True
            continue
        
        if in_active_section:
            # Active routes section ends with a separator line of equals signs
            if line.startswith("="):
                if routes:  # Already parsed some routes, so this equals line marks the end
                    break
                continue
            
            if "Network Destination" in line or "Gateway" in line:
                continue
            
            parts = line.split()
            # print(f"DEBUG line: {parts}")  # left here to help debug on strange interface setups
            if len(parts) >= 5:
                # Ignore loopback/multicast blocks to avoid cluttering calculations
                dest = parts[0]
                if dest.startswith("127.") or dest.startswith("224.") or dest.startswith("255."):
                    continue
                    
                try:
                    routes.append(Route(
                        destination=dest,
                        netmask=parts[1],
                        gateway=parts[2],
                        interface=parts[3],
                        metric=int(parts[4])
                    ))
                except ValueError:
                    # Catches cases where table header lines or system messages bleed in
                    pass
    return routes

def modify_route(action: str, destination: str, mask: str, gateway: str, metric: Optional[int] = None, persistent: bool = True) -> bool:
    """Internal helper to execute route table modifications."""
    if not is_admin():
        raise PermissionError("Administrator privileges required to modify the routing table.")
        
    cmd = ["route"]
    if persistent:
        cmd.append("-p")
    
    cmd.extend([action, destination, "mask", mask, gateway])
    if metric is not None:
        cmd.extend(["metric", str(metric)])
        
    # Startupinfo to hide the cmd popup window if run from a GUI/background process
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
    return res.returncode == 0

def add_route(destination: str, mask: str, gateway: str, metric: Optional[int] = None, persistent: bool = True) -> bool:
    return modify_route("add", destination, mask, gateway, metric, persistent)

def change_route(destination: str, mask: str, gateway: str, metric: Optional[int] = None, persistent: bool = True) -> bool:
    # TODO: Windows change command can occasionally fail if route does not exist.
    # Should we fallback to add if change fails? For now, caller handles it.
    return modify_route("change", destination, mask, gateway, metric, persistent)

def delete_route(destination: str, netmask: str, gateway: str, persistent: bool = True) -> bool:
    if not is_admin():
        raise PermissionError("Administrator privileges required to modify the routing table.")
        
    cmd = ["route"]
    if persistent:
        cmd.append("-p")
    cmd.extend(["delete", destination, "mask", netmask, gateway])
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
    return res.returncode == 0
