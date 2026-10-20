#!/usr/bin/env python3
"""
Hotspot network diagnostics and status inspection.
"""

import os
import re
import time
from typing import Optional

from .constants import CONFIG, HotspotStatus, PingStatus
from .context import Context
from .routing import get_current_default_wan
from .runner import (
    check_docker_container,
    check_service,
    get_configured_ipv6_mode,
    log,
    run_args,
)


def check_internet() -> bool:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    runner = getattr(ctx, "run_args", run_args)
    get_iface = getattr(ctx, "get_active_vpn_interface")

    targets = [cfg.get("ping_target", "8.8.8.8"), "9.9.9.9", "8.8.4.4"]
    active_if, _ = get_iface()
    vpn_ok, _, _ = runner(["ip", "-4", "addr", "show", active_if])
    for target in targets:
        cmd = (
            ["ping", "-c", "2", "-W", "3"]
            + (["-I", active_if] if vpn_ok else [])
            + [target]
        )
        ok, _, _ = runner(cmd)
        if ok:
            return True
    return False


def check_dns() -> bool:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    runner = getattr(ctx, "run_args", run_args)
    test_domains = [cfg.get("dns_test_domain", "google.com"), "cloudflare.com"]
    dns_ip = cfg.get("hotspot_ip", "10.42.0.1")
    for domain in dict.fromkeys(d for d in test_domains if d):
        ok, _, _ = runner(["nslookup", domain, dns_ip])
        if ok:
            return True
    return False


def check_ping(target: Optional[str] = None) -> PingStatus:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    runner = getattr(ctx, "run_args", run_args)
    get_iface = getattr(ctx, "get_active_vpn_interface")

    ping_target = str(target or cfg.get("ping_target", "8.8.8.8") or "8.8.8.8")
    active_if, _ = get_iface()
    vpn_ok, _, _ = runner(["ip", "-4", "addr", "show", active_if])
    ok, out = False, ""
    if vpn_ok:
        ok, out, _ = runner(
            ["ping", "-c", "3", "-W", "2", "-I", active_if, ping_target]
        )
    if not ok:
        ok, out, _ = runner(["ping", "-c", "3", "-W", "2", ping_target])

    packet_line, rtt_line = "No ping result", ""
    for line in out.splitlines():
        if "packets transmitted" in line:
            packet_line = line.strip()
        elif line.startswith("rtt "):
            rtt_line = line.strip()

    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", packet_line)
    avg_match = re.search(r"= ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+) ms", rtt_line)
    return {
        "ok": ok,
        "target": ping_target,
        "summary": packet_line,
        "rtt": rtt_line,
        "loss": loss_match.group(1) if loss_match else "?",
        "avg_ms": avg_match.group(2) if avg_match else "?",
    }


def check_clients() -> int:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    runner = getattr(ctx, "run_args", run_args)
    count = 0
    wlan = cfg.get("interface_wlan", "wlan0")
    for dev in dict.fromkeys([wlan, "wlan1", "ap0"]):
        for bin_cmd in [["sudo", "iw"], ["/usr/sbin/iw"], ["iw"]]:
            ok, out, _ = runner(bin_cmd + ["dev", dev, "station", "dump"])
            if ok:
                count = sum(
                    1 for line in out.splitlines() if line.startswith("Station ")
                )
                if count > 0:
                    return count
    get_clients = getattr(ctx, "get_connected_clients_detailed", None)
    return len(get_clients()) if get_clients else count


def check_hotspot() -> bool:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    runner = getattr(ctx, "run_args", run_args)
    if cfg.get("ap_mode") == "router":
        router_if = cfg.get("router_ap_if", "eth1")
        ok, out, _ = runner(["ip", "link", "show", router_if])
        return ok and ("state UP" in out or "UP" in out)
    for dev in dict.fromkeys([cfg.get("interface_wlan", "wlan0"), "wlan1", "ap0"]):
        for bin_cmd in [["sudo", "iw"], ["/usr/sbin/iw"], ["iw"]]:
            ok, out, _ = runner(bin_cmd + ["dev", dev, "info"])
            if ok and any(line.strip() == "type AP" for line in out.splitlines()):
                return True
    ok, out, _ = runner(["systemctl", "is-active", "hostapd"])
    return ok and out.strip() == "active"


def get_hotspot_ssid() -> str:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    try:
        with open(cfg.get("hostapd_conf", "/etc/hostapd/hostapd.conf")) as conf:
            for line in conf:
                if line.startswith("ssid="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return cfg.get("default_hotspot_ssid", "GoodWifi")


def fix_hotspot() -> bool:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    rst_vpn = getattr(ctx, "restart_vpn")
    apply_pol = getattr(ctx, "apply_vpn_policy")

    if cfg.get("ap_mode") == "router":
        logger("Router AP mode active; hostapd restart bypassed.")
    else:
        ok, out, _ = runner(["systemctl", "is-active", "hostapd"])
        if not ok or out.strip() != "active":
            logger("Hostapd AP inactive; restarting hostapd...")
            runner(["sudo", "systemctl", "restart", "hostapd"])
        else:
            logger("Hostapd AP is active and healthy.")

    logger("Restarting dnsmasq and ensuring DNS resilience...")
    runner(["sudo", "systemctl", "restart", "dnsmasq"])
    time.sleep(1)
    ensure_dns = getattr(ctx, "ensure_adguard_resilience", None)
    if ensure_dns:
        ensure_dns()
    vpn_ok = rst_vpn()
    return bool(vpn_ok and apply_pol())


def get_status() -> HotspotStatus:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    chk_cli = getattr(ctx, "check_clients", check_clients)
    chk_vpn = getattr(ctx, "check_vpn")
    get_iface = getattr(ctx, "get_active_vpn_interface")
    chk_vpn_ip = getattr(ctx, "check_vpn_ip")
    chk_ext_ip = getattr(ctx, "check_vpn_external_ip")
    chk_svc = getattr(ctx, "check_service", check_service)
    chk_container = getattr(ctx, "check_docker_container", check_docker_container)
    chk_hotspot = getattr(ctx, "check_hotspot", check_hotspot)
    chk_dns = getattr(ctx, "check_dns", check_dns)
    chk_net = getattr(ctx, "check_internet", check_internet)
    chk_ping = getattr(ctx, "check_ping", check_ping)
    get_ipv6 = getattr(ctx, "get_configured_ipv6_mode", get_configured_ipv6_mode)
    get_wan = getattr(ctx, "get_current_default_wan", get_current_default_wan)

    clients = chk_cli()
    vpn_connected = chk_vpn()
    active_if, backend_name = get_iface()
    _vpn_ip_ok, vpn_ip = chk_vpn_ip() if vpn_connected else (False, None)
    external_ok, external_ip = chk_ext_ip() if vpn_connected else (False, None)
    internet_working = chk_net()
    if active_if == "sing0" and not external_ok and not internet_working:
        vpn_connected = False

    wan_res = get_wan()
    if isinstance(wan_res, tuple):
        wan_if, wan_metric = wan_res
    else:
        wan_if = str(wan_res) if wan_res else None
        wan_metric = 100 if wan_if == "eth0" else 50
    wan_type = (
        "Fiber"
        if wan_if == "eth0"
        else ("Mobile USB" if wan_if == "usb0" else ("WAN" if wan_if else "None"))
    )

    services_status = {s: chk_svc(s) for s in cfg.get("services", [])}
    for svc, candidates in [
        (
            "adguard",
            [cfg.get("adguard_container", "adguardhome"), "adguardhome", "adguard"],
        ),
        (
            "telegrambot",
            [
                os.getenv("TELEGRAM_CONTAINER"),
                cfg.get("telegram_container"),
                "mpxraspberrypibot",
                "telegrambot",
                "vpn-telegrambot-1",
                "vpn_telegrambot_1",
            ],
        ),
    ]:
        for name in dict.fromkeys(c for c in candidates if c):
            st = chk_container(name)
            if st is not None:
                services_status[svc] = st
                break

    return {
        "services": services_status,
        "vpn": {
            "connected": vpn_connected,
            "interface": active_if,
            "backend": backend_name,
            "ip": vpn_ip,
            "external_ip": external_ip,
            "external_ok": external_ok,
        },
        "hotspot": {
            "broadcasting": chk_hotspot(),
            "clients": clients,
            "ap_mode": cfg.get("ap_mode", "internal"),
            "router_ip": cfg.get("router_ap_router_ip", "10.43.0.2"),
        },
        "wan": {
            "interface": wan_if,
            "type": wan_type,
            "metric": wan_metric,
        },
        "dns_working": chk_dns(),
        "internet": internet_working,
        "ping": chk_ping(),
        "ipv6_protection": get_ipv6(),
    }


def ensure_vpn_resilience() -> tuple[bool, str]:
    """Check VPN connection health and automatically rotate candidate IP or recover."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    chk_vpn = getattr(ctx, "check_vpn")
    chk_ext_ip = getattr(ctx, "check_vpn_external_ip")
    chk_net = getattr(ctx, "check_internet", check_internet)
    get_iface = getattr(ctx, "get_active_vpn_interface")
    get_country = getattr(ctx, "get_configured_unlimited_country")
    rotate_ip = getattr(ctx, "rotate_unlimited_country_ip")
    restart_vpn = getattr(ctx, "restart_vpn")

    vpn_connected = chk_vpn()
    active_if, _backend = get_iface()
    if vpn_connected:
        ext_ok, _ = chk_ext_ip()
        if ext_ok or chk_net():
            return True, "vpn_healthy"

    logger(f"VPN on {active_if} down or stalled. Attempting recovery...", "WARN")
    country = get_country()
    if active_if == "sing0" and country and country != "direct":
        logger(f"Rotating candidate IP for [{country.upper()}]...", "INFO")
        if rotate_ip(country):
            return True, "vpn_rotated_ip"

    logger(f"Restarting VPN service for {active_if}...", "INFO")
    return (True, "vpn_recovered") if restart_vpn(active_if) else (False, "vpn_failed")
