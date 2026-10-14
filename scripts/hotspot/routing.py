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
