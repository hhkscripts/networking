# Raspberry Pi VPN Hotspot (`rpi-vpn-hotspot`)

A resilient Raspberry Pi Wi-Fi hotspot router designed to defeat censorship and DPI (Deep Packet Inspection). It automatically routes connected Wi-Fi clients through an encrypted, high-performance VPN tunnel (**sing-box VLESS Reality**, **AmneziaWG**, **WireGuard**, or **OpenVPN**) while keeping the Pi host, Docker workloads, and local services on the normal Ethernet route.

---

## Key Features

- **Multi-Backend VPN Engine**: Native support for:
  - **sing-box VLESS Reality (`sing0`)**: Advanced anti-censorship tunneling with dynamic multi-country exit switching (Japan, Singapore, US, etc.) masquerading as genuine TLS traffic.
  - **AmneziaWG (`awg0`)**: Obfuscated anti-DPI WireGuard with customized junk packets and header magic.
  - **WireGuard (`wg0`)**: High-speed, low-latency standard WireGuard.
  - **OpenVPN (`tun0`)**: Traditional OpenVPN with replay-window adjustments.
- **Selective Policy Routing**: Hotspot client traffic goes through the active VPN; Raspberry Pi host services, SSH, and Docker containers remain reachable on Ethernet (`eth0`).
- **Selective GitHub & Linux Repo Routing**: Routes GitHub API, Git, GitHub Actions runner, and repository mirrors through the VPN to bypass ISP throttling while keeping other host traffic on local LAN.
- **Selective Local Bypass (Crypto / Banking)**: Automatically routes specific services (such as Binance, Bybit, and local banking) through the local ISP gateway via DNS ipsets (`local_routes`) to avoid VPN geo-blocking.
- **AdGuard Home DNS Protection**: Blocks ads, malicious domains, and tracking network-wide while dynamically populating policy routing ipsets.
- **Telegram Bot Remote Control**: Manage VPN backends, switch exit countries on the fly, inspect connected clients, and monitor system health with interactive inline buttons and status badges.
- **Fully Customizable Hotspot**: Choose any Wi-Fi name (SSID) and WPA2 passphrase easily during setup or dynamically at runtime.

---

## Routing Architecture

Traffic is split dynamically using Linux policy routing, packet marks, and ipsets:

| Source / Destination | Interface | Routing Mechanism | Purpose |
| :--- | :--- | :--- | :--- |
| **Hotspot Clients** (`10.42.0.0/24`) | Active VPN (`sing0` / `awg0` / `wg0` / `tun0`) | Policy `table 100` | Encrypted, secure Internet for all Wi-Fi clients |
| **Binance / Local Bypass** | `eth0` (Local ISP) | `fwmark 0x65` -> `table main` | Bypasses VPN so P2P exchanges see local Myanmar IP |
| **GoodWifi Management Subnets** | `eth0` / Local LAN | `priority 997` -> `table main` | Clients can access Pi services (`10.42.0.1`, LAN IPs, VPN IPs) |
| **Raspberry Pi Host Traffic** | `eth0` (Local ISP) | Default route (`table main`) | Fast, unaffected host networking, SSH, and Docker |
| **Host VPN Routing (Git/Telegram/Linux repos)** | Active VPN (`sing0` / `awg0` / `tun0`) | `fwmark 0x64` (`vpn_routes`) | Ensures Git, GitHub Actions, and repos never timeout |

### Policy Routing Tables

```text
# ip rule show
997:  from 10.42.0.0/24 to 10.8.0.0/24 lookup main
997:  from 10.42.0.0/24 to 192.168.100.0/24 lookup main
998:  from all fwmark 0x65 lookup main              # local_routes (Binance / Banking / Local Bypass)
999:  from all fwmark 0x64 lookup 100               # vpn_routes
1000: from 10.42.0.0/24 lookup 100                  # all other client traffic
```

> [!IMPORTANT]
> **Do NOT force the host default route to VPN.**
> Never replace the host default gateway (`ip route replace default dev tun0/awg0`). Keeping host traffic on `eth0` preserves Docker containers, local SSH management, and stable DNS.

---

## Components

- `hostapd`: Broadcasts the Wi-Fi AP on `wlan0` (`10.42.0.1/24`).
- `dnsmasq`: Lightweight DHCP server assigning IP leases (`10.42.0.10`–`10.42.0.100`) and advertising AdGuard Home as DNS (`10.42.0.1:53`).
- `AdGuard Home`: Dockerized DNS filter on host network; blocks ads and assigns resolved domains into policy ipsets.
- `NetworkManager` & `awg-quick`: Manages Ethernet, Wi-Fi AP, AmneziaWG, and OpenVPN connections.
- `configs/90-hotspot-vpn-policy`: Core firewall and policy routing dispatcher script installed to `/etc/NetworkManager/dispatcher.d/90-hotspot-vpn-policy`.
- `configs/20-hotspot-manager`: NetworkManager dispatcher script ensuring VPN policy on network change.
- `scripts/hotspot-manager.py`: Thin CLI entrypoint (~32 lines) delegating to `scripts/hotspot/`.
- `scripts/hotspot/`: Modular Python core package (<300 lines/file: routing, Sing-box, AdGuard, diagnostics, CLI).
- `scripts/github-vpn-routes.sh`: Fetches published GitHub IPv4 CIDRs and loads them into `vpn_routes`.
- `scripts/apply-routes.sh`: Compiles modular route definitions (`configs/routes/`) into AdGuard Home and host ipsets.
- `telegrambot/`: Dockerized Python Telegram Bot following a Granular Modular Architecture (<300 lines/file).
- `tests/`: Modular test suites for Telegram Bot (`tests/bot/`) and Hotspot Manager (`tests/hotspot/`).

---

## Configuration (`/etc/goodwifi/goodwifi.conf`)

The configuration file `/etc/goodwifi/goodwifi.conf` is **automatically deployed with default settings** during `./setup.sh` from [`configs/goodwifi.conf`](configs/goodwifi.conf). You do not need to create it manually.

If you wish to customize project-wide preferences, you can edit `/etc/goodwifi/goodwifi.conf`:

```bash
# Preferred VPN backend: "auto", "awg0", "wg0", or "tun0"
# "auto" detects any active VPN interface (awg0 > wg0 > tun0)
VPN_BACKEND="auto"

# VPN MTU (e.g. 1280 for AmneziaWG/WireGuard, 1400 for OpenVPN)
# Leave unset or empty to use automatic per-interface defaults
VPN_MTU=""

# OpenVPN NetworkManager connection profile name
VPN_UUID=""

# Policy routing ipset names
VPN_ROUTES_IPSET="vpn_routes"
LOCAL_ROUTES_IPSET="local_routes"

# Network Interfaces
HOTSPOT_IF="wlan0"
HOTSPOT_SUBNET="10.42.0.0/24"
HOTSPOT_IP="10.42.0.1"
LAN_IF="eth0"

# IPv6 leak protection for Wi-Fi hotspot clients:
# "drop"   : Silently drop client IPv6 forwarding (default; prevents VPN bypass / IPv6 leak)
# "reject" : Reject client IPv6 forwarding with ICMPv6 unreachable (fail fast)
# "off"    : Allow IPv6 forwarding (use only if your VPN provides full dual-stack IPv6 routing)
IPV6_LEAK_PROTECTION="drop"
```

---

## Multi-Backend VPN Support

GoodWifi dynamically adapts to whichever VPN backend is running:

- **Sing-box Reality (`sing0`)**: Highest-tier DPI circumvention using VLESS-Reality protocol with fake TLS handshakes (masquerading as legitimate major cloud/CDN destinations). Immune to protocol-level UDP filtering and deep packet inspection.
- **AmneziaWG (`awg0`)**: Recommended for heavily censored environments. Obfuscates WireGuard packet headers (`Jc`, `Jmin`, `Jmax`, `S1`, `S2`, `H1`-`H4`) to bypass DPI blocks.
- **WireGuard (`wg0`)**: Standard WireGuard protocol for high-speed, low-latency tunneling.
- **OpenVPN (`tun0`)**: Traditional OpenVPN protocol managed by NetworkManager. Includes automatic `--replay-window 8192 60` diversion wrapper for unstable mobile UDP paths.

### AmneziaWG / WireGuard Configuration

Ensure `Table = off` is configured in `/etc/amnezia/amneziawg/awg0.conf` or `/etc/wireguard/wg0.conf`:

```ini
[Interface]
Address = 10.8.0.2/24
PrivateKey = <private_key>
DNS = 1.1.1.1
Table = off          # Prevents hijacking Pi host default routes
MTU = 1280
...
```

### Switching VPN Backends via CLI

```bash
# Check current active backend, external IP, and client count
hotspot --status

# Switch active backend to AmneziaWG
hotspot --switch-vpn awg0

# Switch active backend to OpenVPN
hotspot --switch-vpn tun0

# Set to auto-failover (prefers awg0, falls back to tun0/wg0)
hotspot --switch-vpn auto
```

### Switching via Telegram Bot

The Telegram bot includes interactive **Inline Keyboard Buttons** under `/status`:
- When running on `awg0`: displays a `[ 🔄 Switch to OpenVPN (tun0) ]` button.
- When running on `tun0`: displays a `[ ⚡ Switch to AmneziaWG (awg0) ]` button.
- You can also send `/switch_vpn awg0` or `/switch_vpn tun0` directly as text commands.

---

## Daily Management Commands

Convenience aliases installed by `setup.sh`:

```bash
alias hotspot="sudo /usr/local/bin/hotspot-manager.py"
alias hs="sudo /usr/local/bin/hotspot-manager.py --status"
alias hf="sudo /usr/local/bin/hotspot-manager.py --fix"
```

Useful commands:

```bash
hotspot --status        # View current status, VPN backend, IP, and clients
hotspot --clients       # List connected client devices and IP/MAC mappings
hotspot --restart-vpn   # Reconnect active VPN and refresh routes
hotspot --restart       # Restart hotspot services and reapply firewall policy
hotspot --watchdog-dns  # Check AdGuard health and auto-failover to dnsmasq if crashed
hf                      # Run automated self-healing fix
```

---

## AdGuard Home & DNS Policy

GoodWifi clients query `10.42.0.1:53` for DNS. AdGuard Home performs ad-blocking, anti-tracking, and routes specific domains into kernel ipsets:

- `github.com` & subdomains -> `vpn_domains`
- `binance.com`, `bybit.com`, Myanmar banks -> `local_routes`
- DoH & Apple Private Relay bootstrap domains -> blocked (forces devices to use local DNS so routes are populated)

### DoH & Apple Private Relay Protection
To ensure mobile devices cannot bypass policy routing via encrypted DNS:
- **DNS-over-TLS (Port 853)**: Hard-rejected via `iptables` in `90-hotspot-vpn-policy`, forcing Android Private DNS to fail over to standard DHCP DNS.
- **DNS-over-HTTPS (DoH)**: Public DoH bootstrap domains (`cloudflare-dns.com`, `dns.google`, `dns.quad9.net`, etc.) are blocked via AdGuard Home rules (`configs/routes/doh-blocklist.txt`).
- **Apple iCloud Private Relay**: `mask.icloud.com` and `mask-h2.icloud.com` are blocked, which triggers Apple devices to gracefully disable Private Relay on GoodWifi Wi-Fi as per Apple specifications.

### Verifying DNS & Ipsets

```bash
# Test DNS resolution
dig @10.42.0.1 binance.com
dig @10.42.0.1 kbzpay.com

# Verify that resolved IPs were added to bypass set
sudo ipset list local_routes

# Verify GitHub set
sudo ipset list vpn_domains
```

> [!TIP]
> **Ad Blocking on Client Devices:**
> If ads appear on specific client devices:
> 1. With GoodWifi's DoH/DoT hardening, devices automatically use local DNS. Ensure mobile devices have "Private DNS" set to "Off" or "Automatic" (do not use a fixed third-party hostname like `dns.adguard.com` which would be blocked).
> 2. Video in-stream ads (such as YouTube or Facebook video ads) are served from the same CDNs as media streams and cannot be blocked via DNS alone without breaking video playback.

---

## GitHub Actions Self-Hosted Runner

The Pi can run a self-hosted GitHub Actions runner (`actions.runner.hhkscripts.RaspberryPi.service`) for automated deployment of containers and code updates.

- GitHub connections automatically route through the active VPN via `vpn_routes` and `table 100`.
- Git SSH operations automatically bind to the active VPN interface (`awg0` or `tun0`) via `~/.ssh/config`.
- TCP MSS is clamped to PMTU on outbound packets, ensuring TLS handshakes and large payloads never timeout.

## Quick Start & Installation

```bash
git clone https://github.com/hhkscripts/rpi-vpn-hotspot.git
cd rpi-vpn-hotspot
chmod +x setup.sh uninstall.sh scripts/*.sh scripts/hotspot-manager.py
sudo ./setup.sh
```

During installation, the setup wizard will prompt you to set your custom **Hotspot Wi-Fi SSID** and **WPA2 Password** (at least 8 characters).

You can also pass credentials directly for automated/unattended deployments:

```bash
HOTSPOT_SSID="MySecureHotspot" HOTSPOT_PASSWORD="SuperSecretPassword123" sudo -E ./setup.sh
```

### Changing Hotspot Name or Password Later

To change the SSID or password after installation, simply edit `/etc/hostapd/hostapd.conf`:

```ini
ssid=MyNewHotspot
wpa_passphrase=MyNewPassword123
```

Then restart the Wi-Fi service:

```bash
sudo systemctl restart hostapd
```

The hotspot manager CLI and Telegram Bot will automatically detect and reflect the new SSID in their status dashboards.

---

To uninstall and clean up all firewall rules, configs, and services:

```bash
sudo ./uninstall.sh
```

---

## License

This project is licensed under the MIT License.
