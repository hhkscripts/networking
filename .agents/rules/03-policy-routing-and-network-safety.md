# Policy Routing & Network Safety Invariants

- **Zero Host Default Route Hijacking**:
  - NEVER replace the host default gateway (`ip route replace default dev tun0/awg0`).
  - Host traffic must remain on `eth0` (`table main`) to protect local SSH management, Docker networking, and DNS integrity.
- **Enterprise Policy Routing Hierarchy**:
  - `priority 997`: Management subnets (`10.42.0.0/24` to `10.8.0.0/24`, `192.168.100.0/24`, `192.168.1.0/24`) -> `table main`.
  - `priority 998`: `fwmark 0x65` (`local_routes` ipset for Myanmar banking/Binance bypass) -> `table main`.
  - `priority 999`: `fwmark 0x64` (`vpn_routes` ipset for GitHub & selected services) -> `table 100`.
  - `priority 1000`: All other hotspot client traffic (`10.42.0.0/24`) -> `table 100` (VPN).
- **Leak Protection Standards**:
  - IPv6 Leak Protection: Enforce `drop` or `reject` on forwarding rules to prevent IPv6 VPN bypass.
  - DNS Leak Protection: Hotspot clients must query AdGuard Home at `10.42.0.1:53` which routes upstream queries securely over encrypted upstream DNS.
- **Multi-WAN & Failover Invariants**:
  - **Green PON Light Pitfall**: A degraded Fiber connection often maintains physical carrier and local DHCP (`state UP`). Link-state checks are insufficient; actual internet reachability (ping/curl to external IP) is mandatory.
  - **Android Tethering ICMP Drop**: Mobile carriers and Android tethering frequently drop ICMP ping packets (`Destination Host Unreachable`). Reachability tests must always include a lightweight HTTP/TCP connect fallback (`curl -Is --max-time 2 --interface <dev> http://1.1.1.1`).
  - **Metric 0 Route Collision Trap**: Any unmetered default route (`metric 0`) on an inactive interface will override metered routes. When switching WAN, always delete unmetered default routes on all WAN interfaces and set primary to metric 50 and standby to metric 600.
  - **Offline Resilience**: When Pi host is offline, never invoke scripts that rely strictly on remote git access without offline fallbacks.

