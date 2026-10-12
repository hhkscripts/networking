#!/usr/bin/env python3
"""
VPN interface detection, NMCLI connections, and network interface queries.
"""

import os
import time

from .constants import CONFIG
from .context import Context
from .runner import (
    get_configured_backend,
    get_host_path,
    get_vless_display_name,
    run_args,
)


def get_active_vpn_interface() -> tuple[str, str]:
    """Returns (interface_name, display_name)."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    vless_name_fn = getattr(ctx, "get_vless_display_name", get_vless_display_name)
    get_backend = getattr(ctx, "get_configured_backend", get_configured_backend)
    cfg = getattr(ctx, "CONFIG", CONFIG)
    table = str(cfg.get("routing_table", 100))

    ok, out, _ = runner(["ip", "route", "show", "table", table])
    if ok:
        for line in out.splitlines():
            if line.startswith("default dev "):
                parts = line.split()
                if len(parts) >= 3:
                    dev = parts[2]
                    if dev == "sing0":
                        return "sing0", vless_name_fn()
                    elif dev == "awg0":
                        return "awg0", "AmneziaWG"
                    elif dev == "wg0":
                        return "wg0", "WireGuard"
                    elif dev == "tun0":
                        return "tun0", "OpenVPN"

    configured = get_backend()
    if configured in ["sing0", "awg0", "wg0", "tun0"]:
        if configured == "sing0":
            name = vless_name_fn()
        elif configured == "awg0":
            name = "AmneziaWG"
        elif configured == "wg0":
            name = "WireGuard"
        else:
            name = "OpenVPN"
        return configured, name

    for iface, name in [
        ("sing0", vless_name_fn()),
        ("awg0", "AmneziaWG"),
        ("wg0", "WireGuard"),
        ("tun0", "OpenVPN"),
    ]:
        ok, out, _ = runner(["ip", "-4", "addr", "show", iface])
        if ok and "inet " in out:
            return iface, name

    ok, _, _ = runner(["ip", "link", "show", "sing0"])
    if ok:
        return "sing0", vless_name_fn()
    ok, _, _ = runner(["ip", "link", "show", "awg0"])
    if ok:
        return "awg0", "AmneziaWG"
    return "tun0", "OpenVPN"


def get_vpn_connection_name() -> str:
    """Return configured or auto-detected NetworkManager VPN connection name."""
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    runner = getattr(ctx, "run_args", run_args)
    configured = cfg.get("vpn_name", "")

    ok, out, _ = runner(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    if not ok or not out:
        return configured or "pi"

    lines = out.splitlines()
    if configured:
        for line in lines:
            if line.split(":", 1)[0] == configured:
                return configured

    ok_act, out_act, _ = runner(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"]
    )
    if ok_act and out_act:
        for line in out_act.splitlines():
            if ":" in line:
                name, ctype = line.split(":", 1)
                if ctype in ["vpn", "wireguard"] and name:
                    return name

    for line in lines:
        if ":" in line:
            name, ctype = line.split(":", 1)
            if ctype in ["vpn", "wireguard"] and name:
                return name

    return configured or "pi"


def check_vpn() -> bool:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    get_iface = getattr(ctx, "get_active_vpn_interface", get_active_vpn_interface)

    iface, _ = get_iface()
    ok, out, _ = runner(["ip", "-4", "addr", "show", iface])
    if ok and "inet " in out:
        return True

    for fallback in ["sing0", "awg0", "wg0", "tun0"]:
        ok, out, _ = runner(["ip", "-4", "addr", "show", fallback])
        if ok and "inet " in out:
            return True

    ok, out, _ = runner(
        [
            "nmcli",
            "-t",
            "-f",
            "TYPE,STATE",
            "connection",
            "show",
            "--active",
        ]
    )
    if ok and "vpn:activated" in out.lower():
        return True

    return False


def check_vpn_ip() -> tuple[bool, str]:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    get_iface = getattr(ctx, "get_active_vpn_interface", get_active_vpn_interface)

    iface, _ = get_iface()
    for candidate in [iface, "sing0", "awg0", "wg0", "tun0"]:
        ok, out, _ = runner(["ip", "-4", "-o", "addr", "show", candidate])
        if ok:
            for line in out.splitlines():
                parts = line.split()
                if "inet" in parts:
                    cidr = parts[parts.index("inet") + 1]
                    return True, cidr.split("/", 1)[0]
    return False, "None"


def check_vpn_external_ip() -> tuple[bool, str]:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    get_iface = getattr(ctx, "get_active_vpn_interface", get_active_vpn_interface)

    echo_env = os.getenv("IP_ECHO_SERVICES", "")
    custom_services = [s.strip() for s in echo_env.split(",") if s.strip()]
    urls = custom_services or [
        "https://api.ipify.org",
        "https://ifconfig.me",
        "https://icanhazip.com",
    ]

    iface, _ = get_iface()
    candidates = [
        c
        for i, c in enumerate([iface, "sing0", "awg0", "wg0", "tun0"])
        if c and c not in [iface, "sing0", "awg0", "wg0", "tun0"][:i]
    ]
    for candidate in candidates:
        for url in urls:
            ok, out, _ = runner(
                [
                    "curl",
                    "-4",
                    "-s",
                    "--max-time",
                    "5",
                    "--interface",
                    candidate,
                    url,
                ]
            )
            if ok and out and out.strip():
                return True, out.strip()
    return False, "None"


def wait_for_interface(interface: str, timeout: int = 60) -> bool:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, _, _ = runner(["ip", "link", "show", "dev", interface])
        if ok:
            return True
        time.sleep(1)
    return False


def get_connected_clients() -> list[dict]:
    """Parse dnsmasq leases and station dump to return connected client device details."""
    from .clients import get_connected_clients_detailed

    ctx = Context.get()
    get_clients_fn = getattr(
        ctx, "get_connected_clients_detailed", get_connected_clients_detailed
    )
    return get_clients_fn()

