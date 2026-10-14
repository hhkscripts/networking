# GoodWifi Route Configurations & Policy Rules

This directory contains modular domain and CIDR route definitions used by `scripts/apply-routes.sh` to configure **AdGuard Home** ipsets and Linux host **iptables / ipset** routing tables.

---

## Architecture Overview

```
                                    ┌─── local_routes.list ───► [local_routes ipset] ──► Direct Local ISP
                                    │    ├── local-banking.txt
                                    │    ├── local-crypto.txt
                                    │    └── local-custom.txt
Client DNS Query ──► AdGuard Home ──┤
                                    ├─── vpn_routes.list ────► [vpn_domains ipset]  ──► Active VPN (sing0/awg0/tun0)
                                    │    ├── vpn-telegram.txt (includes fragment.com)
                                    │    ├── vpn-github.txt
                                    │    ├── vpn-linux-repo.txt
                                    │    └── vpn-custom.txt
                                    │
                                    └─── dns-doh-blocklist.txt ──► [AdGuard user_rules] ──► Block DoH Bypass
```

---

## File Classification

### 1. Master Manifest Lists (Aggregators)
These files determine which modular files are compiled by `apply-routes.sh`. You can enable or disable route modules by commenting them out with `#`.

| File | Purpose | Target Action |
| :--- | :--- | :--- |
| `local_routes.list` | Manifest of files to bypass VPN | Routes via direct local ISP gateway |
| `vpn_routes.list` | Manifest of files to route through VPN | Routes through active VPN tunnel |

---

### 2. VPN Tunnel Routes (`vpn_routes.list`)
Domains and CIDRs that must bypass ISP censorship, DPI throttling, or geo-blocks.

| File | Description | Notable Domains / CIDRs |
| :--- | :--- | :--- |
| `vpn-telegram.txt` | Telegram Messenger, Bot API, and Fragment platform | `telegram.org`, `t.me`, `api.telegram.org`, `fragment.com`, Telegram CIDRs |
| `vpn-github.txt` | GitHub developer services & raw assets | `github.com`, `raw.githubusercontent.com`, `ghcr.io` |
| `vpn-linux-repo.txt` | Package mirrors, Tailscale, Docker, Rust, PyPI | `deb.debian.org`, `docker.com`, `tailscale.com`, Fastly CIDRs |
| `vpn-custom.txt` | User-defined custom domains or CIDRs | Any user-added blocked websites |

---

### 3. Local Bypass Routes (`local_routes.list`)
Domains and CIDRs that bypass the VPN to maintain low latency, avoid geo-restrictions on banking, or prevent crypto account flags.

| File | Description | Notable Domains |
| :--- | :--- | :--- |
| `local-banking.txt` | Myanmar domestic banks & mobile wallets | KBZPay, WavePay, CB Pay, AYA Pay, Yoma, uabpay |
| `local-crypto.txt` | Cryptocurrency exchanges & P2P trading | Binance, Bybit, OKX, Bitget, KuCoin, Gate.io |
| `local-streaming.txt` | Optional domestic/regional streaming services | (Disabled by default) |
| `local-custom.txt` | User-defined local bypass domains or CIDRs | Any user-added local services |

---

### 4. DNS Filter Rules (AdGuard Home)
| File | Description | Target |
| :--- | :--- | :--- |
| `dns-doh-blocklist.txt` | Blocks DoH and Apple iCloud Private Relay | Injected into AdGuard `user_rules:` to prevent client DNS bypass |

---

## How to Apply Changes

After editing any route file, apply the changes to the running system:

```bash
# Test syntax and inspect output without making host changes:
sudo bash scripts/apply-routes.sh --dry-run

# Apply immediately to AdGuard Home and ipsets:
sudo bash scripts/apply-routes.sh

# Or via hotspot-manager:
sudo hotspot-manager.py --refresh-routes
```
