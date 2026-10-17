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

        fd = open(lock_file, "a+")
        start = time.time()
        while time.time() - start < 15:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fd.seek(0)
                fd.truncate()
                fd.write(f"PID={os.getpid()} CMD={' '.join(sys.argv)}\n")
                fd.flush()
                return fd
            except (BlockingIOError, OSError):
                time.sleep(0.5)
        holder = ""
        try:
            fd.seek(0)
            holder = fd.read().strip()
        except Exception:
            pass
        return holder or False
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
        "--wan",
        dest="wan_target",
        choices=["eth0", "usb0", "auto", "status"],
        help="Switch active WAN uplink (eth0, usb0, auto) or query status",
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
        or (args.wan_target and args.wan_target != "status")
    )
    if mutating:
        lock_fd = _acquire_cli_lock()
        if lock_fd is False or isinstance(lock_fd, str):
            detail = f" ({lock_fd})" if isinstance(lock_fd, str) and lock_fd else ""
            print(f"Notice: Another hotspot task is in progress{detail}. Please retry.")
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
        wan_fn = getattr(ctx, "ensure_wan_resilience", None)
        wan_ok, wan_state = wan_fn() if wan_fn else (True, "wan_ok")
        if not wan_ok:
            print(
                f"Watchdog: WAN={wan_state}, "
                "VPN=wan_offline_skipped, DNS=wan_offline_skipped"
            )
            sys.exit(1)
        vpn_ok, vpn_state = getattr(ctx, "ensure_vpn_resilience")()
        dns_ok, dns_state = getattr(ctx, "ensure_adguard_resilience")()
        print(f"Watchdog: WAN={wan_state}, VPN={vpn_state}, DNS={dns_state}")
        sys.exit(0 if (wan_ok and vpn_ok and dns_ok) else 1)

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

    def _exit_status(success: bool = True):
        output = getattr(ctx, "print_status")(
            getattr(ctx, "get_status")(), telegram_format=telegram_format
        )
        print(output)
        sys.exit(0 if success else 1)

    if args.unlimited_country:
        _exit_status(getattr(ctx, "switch_unlimited_country")(args.unlimited_country))

    if args.rotate_ip:
        _exit_status(getattr(ctx, "rotate_unlimited_country_ip")())

    if args.reality_server:
        num = "1" if args.reality_server in ["1", "server-1"] else "2"
        _exit_status(getattr(ctx, "switch_reality_server")(num))

    if args.switch_vpn:
        _exit_status(getattr(ctx, "switch_vpn")(args.switch_vpn))

    if args.set_ipv6:
        _exit_status(getattr(ctx, "set_ipv6_mode")(args.set_ipv6))

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
            chk_c = getattr(ctx, "check_docker_container", check_docker_container)
            st = chk_c(cfg.get("adguard_container", "adguardhome"))
            s_str = "Running" if st else "Stopped"
            c_str = "Enabled" if enabled else "Disabled"
            print(f"AdGuard Config: {c_str} | Container: {s_str}")
            sys.exit(0)
        _exit_status(success)

    if args.wan_target:
        if args.wan_target == "status":
            cur = getattr(ctx, "get_current_default_wan", lambda: "eth0")()
            chk = getattr(ctx, "check_wan_reachability", lambda _: False)
            e_st = "ONLINE" if chk("eth0") else "OFFLINE"
            u_st = "ONLINE" if chk("usb0") else "OFFLINE"
            print(f"Active WAN: {cur} | eth0 (Fiber): {e_st} | usb0 (USB): {u_st}")
            sys.exit(0)
        sw_fn = getattr(ctx, "switch_wan_uplink", None)
        ok = sw_fn(args.wan_target) if sw_fn else False
        sys.exit(0 if ok else 1)

    if args.status:
        _exit_status(True)

    if args.clients:
        from .clients import format_clients

        connected = getattr(ctx, "get_connected_clients", get_connected_clients)()
        fmt_fn = getattr(ctx, "format_clients", format_clients)
        print(fmt_fn(connected or [], telegram_format=telegram_format))

    if args.restart_vpn:
        if not getattr(ctx, "restart_vpn")():
            sys.exit(1)

    if args.fix or args.restart:
        if not getattr(ctx, "fix_hotspot")():
            sys.exit(1)
        if args.fix:
            _exit_status(True)


if __name__ == "__main__":
    main()
