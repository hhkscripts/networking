#!/usr/bin/env python3
"""
IP policy routing rules and route update scripts.
"""

import os
import time
from typing import Optional, Set

from .constants import (
    APPLY_ROUTE_SCRIPT,
    CONFIG,
    GITHUB_ROUTE_SCRIPT,
    POLICY_SCRIPT,
)
from .context import Context
from .formatter import send_telegram_notification
from .runner import log, run_args


def _get_routing_table_names(table: str = "100") -> Set[str]:
    """Retrieve all valid alias names for the routing table ID."""
    names = {str(table), "100", "github_vpn", "goodwifi", "vpn_routes"}
    for path in ["/etc/iproute2/rt_tables", "/usr/share/iproute2/rt_tables"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split()
                            if len(parts) >= 2 and parts[0] == str(table):
                                names.add(parts[1])
            except Exception:
                pass
    return names


def apply_vpn_policy(interface: Optional[str] = None) -> bool:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)
    cfg = getattr(ctx, "CONFIG", CONFIG)
    script = getattr(ctx, "POLICY_SCRIPT", POLICY_SCRIPT)
    get_iface = getattr(ctx, "get_active_vpn_interface")

    if not interface or interface == "auto":
        interface, _ = get_iface()
    target_iface = str(interface or "tun0")

    table = str(cfg.get("routing_table", 100))
    subnet = cfg.get("hotspot_subnet", "10.42.0.0/24")
    valid_tables = _get_routing_table_names(table)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        ok, out, err = runner(["sudo", script, target_iface, "apply"])
        if not ok:
            detail = err or out or "unknown error"
            if attempt < max_attempts:
                time.sleep(1)
                continue
            logger(f"VPN policy apply failed: {detail}", "ERROR")
            return False

        route_ok, route_out, _ = runner(["ip", "route", "show", "table", table])
        rule_ok, rule_out, _ = runner(["ip", "rule", "show"])

        has_default_route = route_ok and (
            f"default dev {target_iface}" in route_out or "default dev" in route_out
        )

        has_table_rule = False
        if rule_ok and rule_out:
            for line in rule_out.splitlines():
                line_clean = " ".join(line.split())
                if f"from {subnet}" in line_clean or "from 10.42.0.0/24" in line_clean:
                    for t_name in valid_tables:
                        if f"lookup {t_name}" in line_clean:
                            has_table_rule = True
                            break
                if has_table_rule:
                    break

        if has_default_route and has_table_rule:
            return True

        if attempt < max_attempts:
            time.sleep(1)

    logger(
        f"VPN policy apply did not install GoodWifi table {table} routing",
        "ERROR",
    )
    return False


def refresh_routes() -> bool:
    """Compile and apply modular local/VPN routes and refresh GitHub CIDRs.

    Ensures local_routes (Binance, Banking bypass) and vpn_routes are synchronized
    to AdGuard Home and kernel ipsets, followed by refreshing GitHub IP ranges.
    """
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)
    gh_script = getattr(ctx, "GITHUB_ROUTE_SCRIPT", GITHUB_ROUTE_SCRIPT)
    ap_script = getattr(ctx, "APPLY_ROUTE_SCRIPT", APPLY_ROUTE_SCRIPT)

    all_ok = True

    # 1. Primary: Apply modular local_routes & vpn_routes via apply-routes.sh
    ok, _, _ = runner(["test", "-x", ap_script])
    if ok:
        ap_ok, _, err = runner(["sudo", ap_script], timeout=60)
        if not ap_ok:
            all_ok = False
            detail = f": {err}" if err else ""
            logger(f"Route apply failed{detail}", "WARN")

    # 2. Secondary: Refresh published GitHub CIDRs into vpn_routes if script present
    ok, _, _ = runner(["test", "-x", gh_script])
    if ok:
        gh_ok, _, err = runner(["sudo", gh_script], timeout=120)
        if not gh_ok:
            all_ok = False
            detail = f": {err}" if err else ""
            logger(f"GitHub route refresh failed{detail}", "WARN")

    return all_ok


# Backward-compatible alias for existing callers and external integrations
refresh_github_routes = refresh_routes

WAN_STATE_FILE = "/run/goodwifi-active-wan"


def check_wan_reachability(
    iface: str, target: str = "8.8.8.8", timeout: int = 2
) -> bool:
    """Test actual internet reachability through a specific WAN interface."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)

    ok_l, out_l, _ = runner(["ip", "link", "show", "dev", iface])
    if not ok_l or ("state UP" not in out_l and "UP" not in out_l):
        return False

    ok_a, out_a, _ = runner(["ip", "-4", "addr", "show", "dev", iface])
    if not ok_a or "inet " not in out_a:
        return False

    ok_p, _, _ = runner(
        ["ping", "-c", "2", "-W", str(timeout), "-I", iface, target],
        timeout=timeout + 3,
    )
    return bool(ok_p)


def get_current_default_wan() -> str:
    """Return the device with the primary default route in main table."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    ok, out, _ = runner(["ip", "-4", "route", "show", "default", "table", "main"])
    if ok and out:
        for line in out.splitlines():
            parts = line.split()
            if "dev" in parts:
                dev = parts[parts.index("dev") + 1]
                if dev not in ["wlan0", "sing0", "awg0", "wg0", "tun0"]:
                    return dev
    return "eth0"


def switch_wan_uplink(target: str) -> bool:
    """Switch primary default WAN route between eth0 and usb0."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)
    chk_wan = getattr(ctx, "check_wan_reachability", check_wan_reachability)
    get_wan = getattr(ctx, "get_current_default_wan", get_current_default_wan)

    target = target.lower().strip()
    if target == "auto":
        if chk_wan("eth0"):
            target = "eth0"
        elif chk_wan("usb0"):
            target = "usb0"
        else:
            logger("Auto-WAN: neither eth0 nor usb0 reachable", "WARN")
            return False

    if target not in ["eth0", "usb0", "eth1", "usb1"]:
        logger(f"Invalid WAN target: {target}", "ERROR")
        return False

    current_wan = get_wan()
    current_state = ""
    if os.path.exists(WAN_STATE_FILE):
        try:
            with open(WAN_STATE_FILE, "r", encoding="utf-8") as f:
                current_state = f.read().strip()
        except Exception:
            pass

    if target == current_wan and target == current_state:
        return True

    logger(f"Switching default WAN uplink to [{target}]...", "INFO")
    m1 = "100" if target == "eth0" else "600"
    m2 = "500" if target == "eth0" else "50"
    runner(["sudo", "ip", "route", "replace", "default", "dev", "eth0", "metric", m1])
    runner(["sudo", "ip", "route", "replace", "default", "dev", "usb0", "metric", m2])

    try:
        with open(WAN_STATE_FILE, "w", encoding="utf-8") as f:
            f.write(target)
    except Exception:
        pass

    getattr(ctx, "apply_vpn_policy", apply_vpn_policy)()
    restart_fn = getattr(ctx, "restart_vpn", None)
    if restart_fn:
        restart_fn()

    logger(f"Successfully switched WAN to [{target}]", "SUCCESS")
    notify_fn = getattr(ctx, "send_telegram_notification", send_telegram_notification)
    if target == "usb0":
        notify_fn(
            "⚠️ <b>GoodWifi WAN Alert</b>\n"
            "Fiber (eth0) connection dropped.\n"
            "Switched uplink to <b>Mobile USB (usb0)</b>."
        )
    elif target == "eth0" and current_wan and current_wan != "eth0":
        notify_fn(
            "✅ <b>GoodWifi WAN Alert</b>\n"
            "Fiber (eth0) connection restored!\n"
            "Switched uplink back to <b>Fiber (eth0)</b>."
        )
    return True


def ensure_wan_resilience() -> tuple[bool, str]:
    """Check WAN health and perform automatic failover or failback."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    chk_wan = getattr(ctx, "check_wan_reachability", check_wan_reachability)
    get_wan = getattr(ctx, "get_current_default_wan", get_current_default_wan)
    sw_wan = getattr(ctx, "switch_wan_uplink", switch_wan_uplink)

    current_wan = get_wan()
    eth0_ok = chk_wan("eth0")
    usb0_ok = chk_wan("usb0")

    if current_wan != "eth0":
        if eth0_ok and sw_wan("eth0"):
            logger("Fiber (eth0) recovered! Failing back to Fiber...", "INFO")
            return True, "wan_failed_back_to_fiber"
        return (True, "wan_usb_active") if usb0_ok else (False, "wan_all_offline")

    if eth0_ok:
        return True, "wan_fiber_healthy"

    logger("Fiber (eth0) internet down! Checking USB backup...", "WARN")
    if usb0_ok and sw_wan("usb0"):
        logger("Failing over to USB (usb0)...", "INFO")
        return True, "wan_failed_over_to_usb"

    return False, "wan_all_offline"
