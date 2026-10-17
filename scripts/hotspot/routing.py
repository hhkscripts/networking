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
from .runner import log, run_args, update_goodwifi_conf


def _get_routing_table_names(table: str = "100") -> Set[str]:
    """Retrieve all valid alias names for the routing table ID."""
    names = {str(table), "100", "github_vpn", "goodwifi", "vpn_routes"}
    for p in ["/etc/iproute2/rt_tables", "/usr/share/iproute2/rt_tables"]:
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
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
            if attempt < max_attempts:
                time.sleep(1)
                continue
            logger(f"VPN policy apply failed: {err or out or 'unknown error'}", "ERROR")
            return False

        route_ok, route_out, _ = runner(["ip", "route", "show", "table", table])
        rule_ok, rule_out, _ = runner(["ip", "rule", "show"])
        has_default = route_ok and (
            f"default dev {target_iface}" in route_out or "default dev" in route_out
        )
        has_rule = any(
            (f"from {subnet}" in line or "from 10.42.0.0/24" in line)
            and any(f"lookup {t}" in line for t in valid_tables)
            for line in (rule_out or "").splitlines()
        )
        if has_default and has_rule:
            return True
        if attempt < max_attempts:
            time.sleep(1)

    logger(f"VPN policy apply did not install GoodWifi table {table} routing", "ERROR")
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
    scripts = [(ap_script, "Route apply", 60), (gh_script, "GitHub route refresh", 120)]
    for script, name, to in scripts:
        if runner(["test", "-x", script])[0]:
            s_ok, _, err = runner(["sudo", script], timeout=to)
            if not s_ok:
                all_ok = False
                logger(f"{name} failed: {err}" if err else f"{name} failed", "WARN")
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

    targets = [target] if target != "8.8.8.8" else ["8.8.8.8", "1.1.1.1"]
    for tgt in targets:
        p_cmd = ["ping", "-c", "2", "-W", str(timeout), "-I", iface, tgt]
        c_cmd = [
            "curl",
            "-Is",
            "--max-time",
            "2",
            "--interface",
            iface,
            f"http://{tgt}",
        ]
        if runner(p_cmd, timeout=timeout + 3)[0] or runner(c_cmd, timeout=4)[0]:
            return True
    return False


def _get_dev_gateway(runner, dev: str) -> Optional[str]:
    ok, out, _ = runner(["ip", "-4", "route", "show", "dev", dev])
    if ok and out:
        for line in out.splitlines():
            parts = line.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    ok_nm, out_nm, _ = runner(["nmcli", "-g", "IP4.GATEWAY", "dev", "show", dev])
    return (
        out_nm.strip().splitlines()[0] if ok_nm and out_nm and out_nm.strip() else None
    )


def _clean_routes_for_dev(runner, dev: str, is_primary: bool) -> None:
    ok, out, _ = runner(["ip", "-4", "route", "show", "default", "dev", dev])
    if not (ok and out):
        return
    for line in out.splitlines():
        if (not is_primary and ("metric 50" in line or "metric" not in line)) or (
            is_primary and "metric" not in line
        ):
            parts = line.split()
            cmd = ["sudo", "ip", "route", "del", "default"]
            if "via" in parts:
                cmd.extend(["via", parts[parts.index("via") + 1]])
            cmd.extend(["dev", dev])
            if "metric" in parts and not is_primary:
                cmd.extend(["metric", parts[parts.index("metric") + 1]])
            runner(cmd)


def _route_cmd(dev: str, gw: Optional[str], metric: str) -> list[str]:
    cmd = ["sudo", "ip", "route", "replace", "default"]
    if gw:
        cmd.extend(["via", gw])
    cmd.extend(["dev", dev, "metric", metric])
    return cmd


def get_current_default_wan() -> str:
    """Return the device with the primary default route in main table."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    ok, out, _ = runner(["ip", "-4", "route", "show", "default", "table", "main"])
    if ok and out:
        best_dev, lowest_metric = None, 999999
        for line in out.splitlines():
            parts = line.split()
            if "dev" in parts:
                dev = parts[parts.index("dev") + 1]
                if dev not in ["wlan0", "sing0", "awg0", "wg0", "tun0"]:
                    m = (
                        int(parts[parts.index("metric") + 1])
                        if "metric" in parts
                        else 0
                    )
                    if m < lowest_metric:
                        lowest_metric, best_dev = m, dev
        if best_dev:
            return best_dev
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
    cur_state = ""
    if os.path.exists(WAN_STATE_FILE):
        try:
            cur_state = open(WAN_STATE_FILE, encoding="utf-8").read().strip()
        except Exception:
            pass

    if target == current_wan and target == cur_state:
        return True

    logger(f"Switching default WAN uplink to [{target}]...", "INFO")
    for dev in ["eth0", "usb0"]:
        _clean_routes_for_dev(runner, dev, is_primary=(dev == target))
        metric = "50" if dev == target else "600"
        runner(_route_cmd(dev, _get_dev_gateway(runner, dev), metric))

    try:
        with open(WAN_STATE_FILE, "w", encoding="utf-8") as f:
            f.write(target)
    except Exception:
        pass
    getattr(ctx, "update_goodwifi_conf", update_goodwifi_conf)("LAN_IF", target)
    getattr(ctx, "apply_vpn_policy", apply_vpn_policy)()
    restart_fn = getattr(ctx, "restart_vpn", None)
    if restart_fn:
        restart_fn()

    logger(f"Successfully switched WAN to [{target}]", "SUCCESS")
    notify_fn = getattr(ctx, "send_telegram_notification", send_telegram_notification)
    if target == "usb0":
        notify_fn(
            "⚠️ <b>GoodWifi WAN Alert</b>\n"
            "Fiber (eth0) dropped. Uplink: <b>Mobile USB (usb0)</b>."
        )
    elif target == "eth0" and current_wan and current_wan != "eth0":
        notify_fn(
            "✅ <b>GoodWifi WAN Alert</b>\n"
            "Fiber (eth0) restored! Uplink: <b>Fiber (eth0)</b>."
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
