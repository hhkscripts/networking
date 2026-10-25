# GoodWifi VPN Backend Setup Guide

This guide explains how to configure and activate any of the supported VPN backends on your Raspberry Pi GoodWifi hotspot.

GoodWifi uses Linux Policy Routing (`table 100`) to transparently route all connected hotspot devices through your VPN while keeping the Raspberry Pi host, Docker workloads, and local SSH reachable on your local network.

---

## Supported VPN Backends Overview

| Backend | Interface | Anti-Censorship / DPI Evasion | Recommended For |
| :--- | :--- | :--- | :--- |
| **sing-box VLESS Reality** | `sing0` | ⭐⭐⭐⭐⭐ Highest (TLS Handshake Camouflage) | Strict firewalls, SNI filtering, active DPI |
| **AmneziaWG** | `awg0` | ⭐⭐⭐⭐ High (WireGuard header obfuscation + junk packets) | WireGuard protocol blocking / packet sniffing |
| **Standard WireGuard** | `wg0` | ⭐⭐ Standard (UDP WireGuard) | High throughput, low latency (uncensored networks) |
| **OpenVPN** | `tun0` | ⭐⭐⭐ Medium (Hardened with replay-window wrapper) | Traditional VPN providers, fallback routing |

---

## 1. sing-box (VLESS Reality)

sing-box with VLESS Reality encapsulates your traffic into genuine TLS connections to prominent CDN/Cloud targets, making it virtually indistinguishable from regular HTTPS browsing.

### Configuration Path
Place your configuration at:
```bash
/etc/sing-box/config.json
```

### Essential Inbound Configuration
Make sure the inbound TUN interface is named `sing0`:
```json
{
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "sing0",
      "inet4_address": "10.99.0.1/30",
      "auto_route": false,
      "strict_route": false,
      "mtu": 1380
    }
  ],
  "outbounds": [
    {
      "type": "vless",
      "tag": "vless-out",
      "server": "YOUR_SERVER_IP_OR_DOMAIN",
      "server_port": 443,
      "uuid": "YOUR_UUID_HERE",
      "flow": "xtls-rprx-vision",
      "tls": {
        "enabled": true,
        "server_name": "www.cloudflare.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        },
        "reality": {
          "enabled": true,
          "public_key": "YOUR_REALITY_PUBLIC_KEY",
          "short_id": "YOUR_SHORT_ID"
        }
      }
    }
  ]
}
```

### Enable & Start
```bash
sudo systemctl enable --now sing-box
hotspot --switch-vpn sing0
```

---

## 2. AmneziaWG (Obfuscated WireGuard)

AmneziaWG adds packet header junk bytes (`Jc`, `Jmin`, `Jmax`) and magic cookie headers (`H1`-`H4`) to standard WireGuard packets to defeat deep packet inspection (DPI).

### Configuration Path
Place your configuration at:
```bash
/etc/amnezia/amneziawg/awg0.conf
```

### Crucial Requirement: `Table = off`
> [!IMPORTANT]
> You **MUST** specify `Table = off` in the `[Interface]` section. This prevents WireGuard from overriding the host default gateway (`table main`), preserving local SSH, Docker networks, and policy routing.

```ini
[Interface]
Address = 10.8.0.2/24
PrivateKey = YOUR_PRIVATE_KEY
DNS = 1.1.1.1
Table = off
MTU = 1280
Jc = 4
Jmin = 40
Jmax = 70
S1 = 15
S2 = 30
H1 = 1
H2 = 2
H3 = 3
H4 = 4

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = YOUR_SERVER_IP:PORT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

### Enable & Start
```bash
sudo systemctl enable --now awg-quick@awg0
hotspot --switch-vpn awg0
```

---

## 3. Standard WireGuard

### Configuration Path
Place your configuration at:
```bash
/etc/wireguard/wg0.conf
```

### Configuration Example
```ini
[Interface]
Address = 10.8.0.2/24
PrivateKey = YOUR_PRIVATE_KEY
DNS = 1.1.1.1
Table = off
MTU = 1380

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = YOUR_SERVER_IP:PORT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

### Enable & Start
```bash
sudo systemctl enable --now wg-quick@wg0
hotspot --switch-vpn wg0
```

---

## 4. OpenVPN

### Import via NetworkManager
You can import any `.ovpn` profile using `nmcli`:
```bash
sudo nmcli connection import type openvpn file /path/to/your-profile.ovpn
```

NetworkManager will name the connection after the `.ovpn` filename (e.g., `my-vpn`).

### Replay Window Protection
GoodWifi automatically installs an OpenVPN diversion wrapper (`/usr/local/bin/openvpn-replay-wrapper`) that applies `--replay-window 8192 60` to mitigate packet dropping on jittery mobile networks.

### Enable & Start
```bash
# Connect via nmcli:
sudo nmcli connection up "my-vpn"

# Apply GoodWifi policy:
hotspot --switch-vpn tun0
```

---

## 5. Daily Management & Switching

Once your VPN backend is active, managing it is effortless:

```bash
# Check overall health and active VPN backend
hotspot --status
# Or short alias:
hs

# Switch active VPN backend dynamically
hotspot --switch-vpn sing0   # Switch to sing-box VLESS Reality
hotspot --switch-vpn awg0    # Switch to AmneziaWG
hotspot --switch-vpn wg0     # Switch to standard WireGuard
hotspot --switch-vpn tun0    # Switch to OpenVPN
hotspot --switch-vpn auto    # Auto-detect best active VPN

# Reconnect VPN and refresh routing tables
hotspot --restart-vpn

# Run automated self-healing fix if connection stalls
hf
```

### Via Telegram Bot
If you configured the Telegram Bot container:
1. Send `/status` to the bot.
2. Use the interactive inline buttons to switch backends (`[ ⚡ Switch to AmneziaWG ]`, `[ 🇯🇵 Switch Country ]`, etc.) on the fly.
