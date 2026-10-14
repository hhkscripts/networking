#!/usr/bin/env python3
"""
Command Line Interface parser and dispatcher for Hotspot Manager.
"""

import argparse
import json
import os
import sys

from .constants import CONFIG
from .context import Context
from .detection import get_connected_clients
from .runner import check_docker_container

try:
    import fcntl
except ImportError:
    fcntl = None


def _acquire_cli_lock():
    if fcntl is None:
        return None
    lock_file = "/run/lock/hotspot-manager-cli.lock"
    try:
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    except Exception:
        lock_file = "/tmp/hotspot-manager-cli.lock"
    try:
        import time

        fd = open(lock_file, "w")
        start = time.time()
        while time.time() - start < 15:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except (BlockingIOError, OSError):
                time.sleep(0.5)
        return False
    except Exception:
        return None


def main() -> None:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)

    parser = argparse.ArgumentParser(
        description="Raspberry Pi Hotspot Manager - Smart Monitoring"
    )
    parser.add_argument("-s", "--status", action="store_true")
    parser.add_argument("-r", "--restart", action="store_true")
    parser.add_argument("-rv", "--restart-vpn", action="store_true")
    parser.add_argument("-f", "--fix", action="store_true")
    parser.add_argument(
        "--switch-vpn",
        dest="switch_vpn",
        choices=["sing0", "awg0", "tun0", "wg0", "auto"],
        help="Switch active VPN backend",
    )
    parser.add_argument(
        "--reality-server",
        dest="reality_server",
        choices=["1", "2", "server-1", "server-2"],
        help="Switch primary Reality server (1: server-1, 2: server-2)",
    )
    parser.add_argument(
        "--unlimited-country",
        dest="unlimited_country",
        help="Switch VPN Unlimited exit country (e.g. sg, jp, direct)",
    )
    parser.add_argument(
        "--rotate-ip",
        action="store_true",
        help="Rotate to next candidate IP endpoint for active country exit",
    )
    parser.add_argument(
        "--list-countries",
        action="store_true",
        help="List available VPN Unlimited country profiles",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--set-ipv6",
        "--ipv6",
        dest="set_ipv6",
        choices=["drop", "reject", "off"],
        help="Set IPv6 leak protection mode (drop, reject, off)",
    )
    parser.add_argument(
        "--adguard",
        dest="set_adguard",
        choices=["on", "off", "enable", "disable", "status", "restart"],
        help="Manage AdGuard Home service (on, off, status, restart)",
    )
    parser.add_argument("--clients", action="store_true")
    parser.add_argument(
        "--refresh-routes",
        action="store_true",
        help="Recompile and apply modular routes to AdGuard Home and ipsets",
    )
    parser.add_argument(
        "--watchdog-vpn",
        action="store_true",
        help="Check VPN health and auto-rotate candidate IP or restart if down",
    )
    parser.add_argument(
        "--watchdog",
        action="store_true",
        help="Run comprehensive health watchdog for both VPN and DNS resilience",
    )
    parser.add_argument(
        "--watchdog-dns",
        action="store_true",
        help="Check AdGuard container health and auto-failover to fallback DNS if down",
    )
    parser.add_argument(
        "--telegram", action="store_true", help="Output in HTML format for Telegram"
    )
    parser.add_argument(
        "--html", action="store_true", help="Output formatted as HTML for Telegram"
    )

    args = parser.parse_args()
    telegram_format = bool(args.telegram or args.html)

    if len(sys.argv) == 1:
        args.status = True

    mutating = bool(
        args.restart
        or args.restart_vpn
        or args.fix
        or args.switch_vpn
        or args.reality_server
        or args.unlimited_country
        or args.rotate_ip
        or args.set_ipv6
        or args.set_adguard
        or args.refresh_routes
        or args.watchdog
        or args.watchdog_vpn
        or args.watchdog_dns
    )
    if mutating:
        lock_fd = _acquire_cli_lock()
        if lock_fd is False:
            print("Notice: Another hotspot task is in progress. Please retry.")
            sys.exit(1)

    if args.refresh_routes:
        getattr(ctx, "refresh_routes", getattr(ctx, "refresh_github_routes"))()
        print("Routes refreshed successfully.")
        sys.exit(0)

    if args.watchdog_vpn:
        ok, state = getattr(ctx, "ensure_vpn_resilience")()
        print(f"VPN Watchdog: {state}")
        sys.exit(0 if ok else 1)

    if args.watchdog:
        vpn_ok, vpn_state = getattr(ctx, "ensure_vpn_resilience")()
        dns_ok, dns_state = getattr(ctx, "ensure_adguard_resilience")()
        print(f"Watchdog: VPN={vpn_state}, DNS={dns_state}")
        sys.exit(0 if (vpn_ok and dns_ok) else 1)

    if args.watchdog_dns:
        ok, state = getattr(ctx, "ensure_adguard_resilience")()
        print(f"DNS Watchdog: {state}")
        sys.exit(0 if ok else 1)

    if args.list_countries:
        profs = getattr(ctx, "get_country_profiles")()
        if args.json:
            print(json.dumps(profs))
        else:
            for cc, p in profs.items():
                print(
                    f"{p['flag']} {cc.upper()}: {p['country_name']} ({p['filename']})"
                )
        sys.exit(0)

    if args.unlimited_country:
        success = getattr(ctx, "switch_unlimited_country")(args.unlimited_country)
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.rotate_ip:
        success = getattr(ctx, "rotate_unlimited_country_ip")()
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.reality_server:
        num = "1" if args.reality_server in ["1", "server-1"] else "2"
        success = getattr(ctx, "switch_reality_server")(num)
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.switch_vpn:
        success = getattr(ctx, "switch_vpn")(args.switch_vpn)
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.set_ipv6:
        success = getattr(ctx, "set_ipv6_mode")(args.set_ipv6)
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.set_adguard:
        success = False
        set_adg_fn = getattr(ctx, "set_adguard_state")
        if args.set_adguard in ["on", "enable"]:
            success = set_adg_fn(True)
        elif args.set_adguard in ["off", "disable"]:
            success = set_adg_fn(False)
        elif args.set_adguard == "restart":
            set_adg_fn(False)
            success = set_adg_fn(True)
        elif args.set_adguard == "status":
            enabled = getattr(ctx, "get_adguard_enabled")()
            chk_container = getattr(
                ctx, "check_docker_container", check_docker_container
            )
            st = chk_container(cfg.get("adguard_container", "adguardhome"))
            state_str = "Running" if st else "Stopped"
            config_str = "Enabled" if enabled else "Disabled"
            print(f"AdGuard Config: {config_str} | Container: {state_str}")
            sys.exit(0)
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.status:
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)

    if args.clients:
        from .clients import format_clients

        connected = getattr(ctx, "get_connected_clients", get_connected_clients)()
        fmt_fn = getattr(ctx, "format_clients", format_clients)
        print(fmt_fn(connected or [], telegram_format=telegram_format))

    if args.restart_vpn:
        if not getattr(ctx, "restart_vpn")():
            sys.exit(1)

    if args.fix:
        if not getattr(ctx, "fix_hotspot")():
            sys.exit(1)
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)

    if args.restart:
        if not getattr(ctx, "fix_hotspot")():
            sys.exit(1)


if __name__ == "__main__":
    main()
