#!/usr/bin/env python3
"""
IP policy routing rules and route update scripts.
"""

from typing import Optional

from .constants import (
    APPLY_ROUTE_SCRIPT,
    CONFIG,
    GITHUB_ROUTE_SCRIPT,
    POLICY_SCRIPT,
)
from .context import Context
from .runner import log, run_args


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
    ok, out, err = runner(["sudo", script, target_iface, "apply"])
    if not ok:
        detail = err or out or "unknown error"
        logger(f"VPN policy apply failed: {detail}", "ERROR")
        return False

    table = str(cfg.get("routing_table", 100))
    subnet = cfg.get("hotspot_subnet", "10.42.0.0/24")
    route_ok, route_out, _ = runner(["ip", "route", "show", "table", table])
    rule_ok, rule_out, _ = runner(["ip", "rule", "show"])
    policy_ok = (
        route_ok
        and (f"default dev {interface}" in route_out or "default dev" in route_out)
        and rule_ok
        and (
            f"from {subnet} lookup {table}" in rule_out
            or f"from 10.42.0.0/24 lookup {table}" in rule_out
            or "from 10.42.0.0/24 lookup 100" in rule_out
        )
    )
    if not policy_ok:
        logger(
            f"VPN policy apply did not install GoodWifi table {table} routing",
            "ERROR",
        )
        return False
    return True


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
