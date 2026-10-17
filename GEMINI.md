# GoodWifi & Telegram Bot Developer Guidelines

## Codebase Architecture
This repository manages a Raspberry Pi GoodWifi hotspot with multi-VPN routing (sing-box VLESS Reality, AmneziaWG, OpenVPN, WireGuard), AdGuard Home DNS protection, and a Telegram Bot interface.

### Key Directories
* `scripts/`:
  * `hotspot-manager.py`: Thin CLI entrypoint (~30 lines) installed to `/usr/local/bin/hotspot-manager.py`.
  * `hotspot/`: Modular core package (<300 lines per file):
    * `constants.py`: TypedDicts, configs, emoji maps.
    * `context.py`: Dynamic execution facade resolver.
    * `runner.py`: Host command runner & config parsers.
    * `singbox.py`: Sing-box JSON generator & reality switcher.
    * `profiles.py`: Country profiles scanning.
    * `routing.py`: Policy routing & route refreshers.
    * `detection.py`: Interface and connection detector.
    * `vpn.py`: Backend switching and service lifecycles.
    * `adguard.py`: AdGuard DNS and IPv6 protection.
    * `status.py`: Health checks and diagnostic runner.
    * `formatter.py`: Telegram HTML and Terminal formatting.
    * `cli.py`: Argument parser and dispatch router.
* `telegrambot/`: Dockerized Telegram Bot following a **Granular Modular Architecture** (<300 lines per file):
  * `constants/`: Emojis, flags, country profiles discovery.
  * `core/`: Config, host execution runner (`nsenter`), and Docker health check HTTP server.
  * `ui/`: Reply keyboards and inline button builders.
  * `handlers/`: Feature-specific command and callback handlers.
  * `bot.py`: Minimal application entrypoint (~120 lines).
* `tests/`:
  * `test_telegram_bot.py`: Unified suite runner for Telegram Bot.
  * `test_hotspot_manager.py`: Unified suite runner for Hotspot Manager.
  * `bot/`: Granular tests for Bot config, health, runner, UI, and application creation.
  * `hotspot/`: Granular tests for Hotspot runner, VPN lifecycle, detection, AdGuard, IPv6, and Sing-box.
* `.agents/skills/vpn-codebase-analysis/`: Workspace skill for automated codebase analysis and quality checks.

## Fast-Lookup Topic Matrix (Instant Navigation - Zero Token Waste)
Do NOT scan or grep the whole codebase for known features. Use this direct mapping:

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

## Code Quality & Architecture Rules
1. **Never duplicate `hotspot-manager.py` into `telegrambot/`**: The bot container executes the host script via `nsenter`.
2. **Keep Python files in the Sweet Spot (<300 lines)**: Follow Single Responsibility Principle (SRP).
3. **Verify changes before committing**: Run `.agents/skills/vpn-codebase-analysis/scripts/analyze.sh` to ensure all tests, syntax, and architectural invariants pass.
4. **Zero Token Waste Navigation**: When addressing a specific feature (e.g. "switch vpn", "adguard"), jump directly to the target file from the Fast-Lookup Topic Matrix. Never perform broad multi-file searches or full-codebase scans.
5. **Instant Analysis**: When asked to analyze, inspect, or test the codebase, run `analyze.sh` directly in bash rather than reading multiple files into context.
6. **Modular Test Suites Strict Isolation**: Never dump test cases or unittest classes directly into root test runners (`tests/test_telegram_bot.py` or `tests/test_hotspot_manager.py`). Root runners are strictly thin suite aggregators (<40 lines). All new tests must be written in granular modular files (`tests/bot/test_*.py` mirroring `telegrambot/` and `tests/hotspot/test_*.py` mirroring `scripts/hotspot/`).
7. **Multi-WAN & Routing Invariants**: Always verify end-to-end internet connectivity (ping/curl) rather than naive link carrier when testing Fiber reachability (degraded Fiber maintains carrier). Mobile USB tethering blocks ICMP; always use HTTP/TCP connect fallback. Always clean unmetered metric-0 routes when switching default WAN.

