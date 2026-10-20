#!/usr/bin/env python3
"""IP policy routing rules and route update scripts."""

import os
import time
from typing import Optional, Set

from .constants import APPLY_ROUTE_SCRIPT, CONFIG, GITHUB_ROUTE_SCRIPT, POLICY_SCRIPT
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
                    names.update(
                        parts[1]
                        for parts in (line.split() for line in f)
                        if len(parts) >= 2 and parts[0] == str(table)
                    )
            except Exception:
                pass
    return names


def apply_vpn_policy(interface: Optional[str] = None) -> bool:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)
    cfg = getattr(ctx, "CONFIG", CONFIG)
    script = getattr(ctx, "POLICY_SCRIPT", POLICY_SCRIPT)
    if not interface or interface == "auto":
        interface, _ = getattr(ctx, "get_active_vpn_interface")()
    target_iface = str(interface or "tun0")
    table = str(cfg.get("routing_table", 100))
    subnet = cfg.get("hotspot_subnet", "10.42.0.0/24")
    r_subnet = cfg.get("router_ap_subnet", "10.43.0.0/24")
    valid_tables = _get_routing_table_names(table)

    for attempt in range(1, 4):
        ok, out, err = runner(["sudo", script, target_iface, "apply"])
        if not ok:
            if attempt < 3:
                time.sleep(1)
                continue
            logger(f"VPN policy apply failed: {err or out or 'unknown error'}", "ERROR")
            return False

        r_ok, r_out, _ = runner(["ip", "route", "show", "table", table])
        _, rule_out, _ = runner(["ip", "rule", "show"])
        has_default = r_ok and (
            f"default dev {target_iface}" in r_out or "default dev" in r_out
        )
        has_rule = any(
            (
                f"from {subnet}" in line
                or f"from {r_subnet}" in line
                or "from 10.42.0.0/24" in line
                or "from 10.43.0.0/24" in line
            )
            and any(f"lookup {t}" in line for t in valid_tables)
            for line in (rule_out or "").splitlines()
        )
        if has_default and has_rule:
            return True
        if attempt < 3:
            time.sleep(1)

    logger(f"VPN policy apply did not install GoodWifi table {table} routing", "ERROR")
    return False


def refresh_routes() -> bool:
    """Compile and apply modular local/VPN routes and refresh GitHub CIDRs."""
    ctx = Context.get()
    runner, logger = getattr(ctx, "run_args", run_args), getattr(ctx, "log", log)
    gh_script = getattr(ctx, "GITHUB_ROUTE_SCRIPT", GITHUB_ROUTE_SCRIPT)
    ap_script = getattr(ctx, "APPLY_ROUTE_SCRIPT", APPLY_ROUTE_SCRIPT)
    all_ok = True
    jobs = [(ap_script, "Route apply", 60), (gh_script, "GitHub route refresh", 120)]
    for script, name, to in jobs:
        if runner(["test", "-x", script])[0]:
            s_ok, _, err = runner(["sudo", script], timeout=to)
            if not s_ok:
                all_ok = False
                logger(f"{name} failed: {err}" if err else f"{name} failed", "WARN")
    return all_ok


# Backward-compatible alias for existing callers and external integrations
refresh_github_routes = refresh_routes

WAN_STATE_FILE = "/run/goodwifi-active-wan"
WAN_MODE_FILE = "/run/goodwifi-wan-mode"


def get_wan_mode() -> str:
    """Return WAN mode: 'auto' or 'manual'."""
    try:
        val = open(WAN_MODE_FILE, encoding="utf-8").read().strip().lower()
        return val if val in ["auto", "manual"] else "auto"
    except OSError:
        return "auto"


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
        c_cmd = ["curl", "-Is", "-m", "2", "--interface", iface, f"http://{tgt}"]
        if runner(p_cmd, timeout=timeout + 3)[0] or runner(c_cmd, timeout=4)[0]:
            return True
    return False


def check_wan_stability(iface: str = "eth0", count: int = 4) -> bool:
    """Verify that interface has 0% packet loss before failback."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    ok, out, _ = runner(
        ["ping", "-c", str(count), "-W", "2", "-I", iface, "8.8.8.8"], timeout=count + 4
    )
    return ok and "0% packet loss" in out


def _get_dev_gateway(runner, dev: str) -> Optional[str]:
    ok, out, _ = runner(["ip", "-4", "route", "show", "dev", dev])
    if ok and out:
        for line in out.splitlines():
            parts = line.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    ok_nm, out_nm, _ = runner(["nmcli", "-g", "IP4.GATEWAY", "dev", "show", dev])
    gw = out_nm.strip().splitlines() if ok_nm and out_nm else []
    return gw[0] if gw else None


def _clean_routes_for_dev(runner, dev: str, is_primary: bool) -> None:
    ok, out, _ = runner(["ip", "-4", "route", "show", "default", "dev", dev])
    if not (ok and out):
        return
    keep = "metric 50" if is_primary else "metric 600"
    for line in out.splitlines():
        if keep not in line:
            p = line.split()
            via = ["via", p[p.index("via") + 1]] if "via" in p else []
            metric = ["metric", p[p.index("metric") + 1]] if "metric" in p else []
            runner(["sudo", "ip", "route", "del", "default", *via, "dev", dev, *metric])


def _route_cmd(dev: str, gw: Optional[str], metric: str) -> list[str]:
    gw_p = ["via", gw] if gw else []
    base = ["sudo", "ip", "route", "replace", "default"]
    return [*base, *gw_p, "dev", dev, "metric", metric]


def get_current_default_wan() -> str:
    """Return the device with the primary default route in main table."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    cfg = getattr(ctx, "CONFIG", CONFIG)
    router_if = cfg.get("router_ap_if", "eth1")
    ok, out, _ = runner(["ip", "-4", "route", "show", "default", "table", "main"])
    if not (ok and out):
        return "eth0"
    best_dev, lowest_metric = None, 999999
    for line in out.splitlines():
        p = line.split()
        if "dev" in p:
            dev = p[p.index("dev") + 1]
            if dev not in ["wlan0", router_if, "sing0", "awg0", "wg0", "tun0"]:
                m = int(p[p.index("metric") + 1]) if "metric" in p else 0
                if m < lowest_metric:
                    lowest_metric, best_dev = m, dev
    return best_dev or "eth0"


def switch_wan_uplink(target: str, mode: Optional[str] = None) -> bool:
    """Switch primary default WAN route between eth0 and usb0."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)
    chk_wan = getattr(ctx, "check_wan_reachability", check_wan_reachability)
    get_wan = getattr(ctx, "get_current_default_wan", get_current_default_wan)

    target = target.lower().strip()
    if mode is None:
        mode = "auto" if target == "auto" else "manual"

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

    try:
        open(WAN_MODE_FILE, "w", encoding="utf-8").write(mode)
    except OSError:
        pass

    current_wan = get_wan()
    cur_state = ""
    try:
        cur_state = open(WAN_STATE_FILE, encoding="utf-8").read().strip()
    except OSError:
        pass

    if target == current_wan and target == cur_state:
        return True

    logger(f"Switching default WAN uplink to [{target}]...", "INFO")
    for dev in ["eth0", "usb0"]:
        gw = _get_dev_gateway(runner, dev)
        _clean_routes_for_dev(runner, dev, is_primary=(dev == target))
        runner(_route_cmd(dev, gw, "50" if dev == target else "600"))

    try:
        open(WAN_STATE_FILE, "w", encoding="utf-8").write(target)
    except Exception:
        pass
    getattr(ctx, "update_goodwifi_conf", update_goodwifi_conf)("LAN_IF", target)
    getattr(ctx, "apply_vpn_policy", apply_vpn_policy)()
    rst = getattr(ctx, "restart_vpn", None)
    if rst:
        rst()

    logger(f"Successfully switched WAN to [{target}]", "SUCCESS")
    notify_fn = getattr(ctx, "send_telegram_notification", send_telegram_notification)
    alert = "<b>GoodWifi WAN Alert</b>\n"
    if target == "usb0":
        notify_fn(f"⚠️ {alert}Fiber dropped. Uplink: <b>Mobile USB (usb0)</b>.")
    elif target == "eth0" and current_wan and current_wan != "eth0":
        notify_fn(f"✅ {alert}Fiber restored! Uplink: <b>Fiber (eth0)</b>.")
    return True


def ensure_wan_resilience() -> tuple[bool, str]:
    """Check WAN health and perform automatic failover or failback."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    chk_wan = getattr(ctx, "check_wan_reachability", check_wan_reachability)
    chk_stab = getattr(ctx, "check_wan_stability", check_wan_stability)
    sw_wan = getattr(ctx, "switch_wan_uplink", switch_wan_uplink)
    current_wan = getattr(ctx, "get_current_default_wan", get_current_default_wan)()
    mode = getattr(ctx, "get_wan_mode", get_wan_mode)()
    eth0_ok, usb0_ok = chk_wan("eth0"), chk_wan("usb0")

    if mode == "manual":
        cur_ok = eth0_ok if current_wan == "eth0" else usb0_ok
        st = "wan_fiber_manual" if current_wan == "eth0" else "wan_usb_manual"
        return (True, st) if cur_ok else (False, "wan_all_offline")

    if current_wan != "eth0":
        if eth0_ok:
            if not chk_stab("eth0"):
                logger("Fiber (eth0) unstable (loss). Holding on USB...", "WARN")
                return (
                    (True, "wan_usb_active") if usb0_ok else (False, "wan_all_offline")
                )
            if sw_wan("eth0"):
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
