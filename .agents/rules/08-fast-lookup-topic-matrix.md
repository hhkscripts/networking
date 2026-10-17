# Fast-Lookup Topic Matrix (Zero Token Waste Navigation)

When working on a feature, jump directly to the target file. Do NOT perform broad multi-file searches or full-codebase scans:

| Feature / User Keyword | Core Script Module | Telegram Bot Handler | UI Keyboard | Relevant Test |
| :--- | :--- | :--- | :--- | :--- |
| **VPN Switching** (`switch vpn`, `awg0`, `tun0`, `sing0`) | `scripts/hotspot/vpn.py` | `telegrambot/handlers/vpn.py` | `telegrambot/ui/vpn_keyboards.py` | `tests/hotspot/test_vpn.py` |
| **AdGuard / DNS Fallback** (`adguard`, `dns`, `watchdog`) | `scripts/hotspot/adguard.py` | `telegrambot/handlers/adguard.py` | `telegrambot/ui/adguard_keyboards.py` | `tests/hotspot/test_adguard.py` |
| **Status / Diagnostics** (`status`, `ping`, `health`) | `scripts/hotspot/status.py` | `telegrambot/handlers/status.py` | `telegrambot/ui/status_keyboards.py` | `tests/bot/test_runner.py` |
| **Exit Countries** (`country`, `singbox`, `vless`, `reality`) | `scripts/hotspot/singbox.py`, `profiles.py` | `telegrambot/handlers/country.py` | `telegrambot/ui/country_keyboards.py` | `tests/hotspot/test_singbox.py` |
| **IPv6 Protection** (`ipv6`, `drop`, `reject`) | `scripts/hotspot/adguard.py` | `telegrambot/handlers/ipv6.py` | `telegrambot/ui/ipv6_keyboards.py` | `tests/hotspot/test_ipv6.py` |
| **Routing & Firewall** (`routing`, `iptables`, `policy`) | `scripts/hotspot/routing.py`, `90-hotspot-vpn-policy` | - | - | `tests/test-vpn-scripts.sh` |
| **WAN Switching / Failover** (`wan`, `failover`, `eth0`, `usb0`, `mobile`, `fiber`) | `scripts/hotspot/routing.py`, `configs/95-hotspot-wan-trigger` | - | - | `tests/hotspot/test_wan.py` |
| **Dynamic Emojis / Sticker Pack** (`emoji`, `sticker`, `flag`) | `telegrambot/core/dynamic_emojis.py` | `telegrambot/handlers/status.py` | `telegrambot/ui/dynamic_emojis.py` | `tests/bot/test_dynamic_emojis.py` |
| **Text Router & Dispatch** (`menu`, `router`, `callback`) | - | `telegrambot/handlers/text_router.py` | `telegrambot/ui/main_keyboard.py` | `tests/bot/test_router.py` |
| **Client Devices** (`clients`, `dhcp`, `mac`) | `scripts/hotspot/detection.py` | `telegrambot/handlers/maintenance.py` | - | `tests/hotspot/test_detection.py` |
| **Bot Auth & Config** (`auth`, `token`, `allowed users`) | - | `telegrambot/core/config.py` | - | `tests/bot/test_config.py` |
| **Host CLI Dispatch** (`cli`, `args`, `flags`) | `scripts/hotspot/cli.py` | `telegrambot/core/runner.py` | - | `tests/hotspot/test_runner.py` |
