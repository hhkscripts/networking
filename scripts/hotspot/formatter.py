#!/usr/bin/env python3
"""
Status output formatting for Terminal and Telegram HTML.
"""

import html
import json
import os
import urllib.request

from .constants import (
    CONFIG,
    Colors,
    EMOJI_AMNEZIAWG,
    EMOJI_CHECK,
    EMOJI_CROSS,
    EMOJI_GLOBE,
    EMOJI_IPV6,
    EMOJI_LOCK,
    EMOJI_OPENVPN,
    EMOJI_PING,
    EMOJI_RPI,
    EMOJI_SINGBOX,
    EMOJI_STATS,
    EMOJI_TOOLS,
    EMOJI_WIREGUARD,
    HotspotStatus,
)
from .context import Context
from .runner import get_vless_display_name


def print_status(status: HotspotStatus, telegram_format: bool = False) -> str:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    get_adg = getattr(ctx, "get_adguard_enabled")
    get_vless = getattr(ctx, "get_vless_display_name", get_vless_display_name)
    get_ssid = getattr(ctx, "get_hotspot_ssid")

    if telegram_format:
        lines = []
        ssid = get_ssid()
        lines.append(f"<b>{EMOJI_RPI} {ssid} Hotspot Manager</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("<b>📊 HOTSPOT STATUS</b>")
        lines.append("")

        lines.append(f"<b>{EMOJI_TOOLS} SERVICES:</b>")
        adguard_enabled = get_adg()
        ap_mode = status.get("hotspot", {}).get("ap_mode", "internal")
        for service, ok in status["services"].items():
            if service == "adguard" and not adguard_enabled:
                icon, state = "⏸️", "Disabled"
            elif service == "hostapd" and ap_mode == "router":
                icon, state = "⏸️", "Standby (Router AP)"
            else:
                icon = EMOJI_CHECK if ok else EMOJI_CROSS
                state = "Running" if ok else "Stopped"
            lines.append(f"{icon} <code>{service}</code>: {state}")
        lines.append("")

        vpn_connected = status["vpn"]["connected"]
        icon = EMOJI_CHECK if vpn_connected else EMOJI_CROSS
        backend = status["vpn"].get("backend", "VPN")
        iface = status["vpn"].get("interface", "unknown")

        vpn_header_emoji = EMOJI_LOCK
        conn_badge = backend
        if (
            "sing" in backend.lower()
            or "reality" in backend.lower()
            or "vless" in backend.lower()
            or iface == "sing0"
        ):
            vpn_header_emoji = EMOJI_SINGBOX
            conn_badge = f"{EMOJI_SINGBOX} {get_vless()}"
        elif "amnezia" in backend.lower() or iface == "awg0":
            vpn_header_emoji = EMOJI_AMNEZIAWG
            conn_badge = f"{EMOJI_AMNEZIAWG} AmneziaWG"
        elif "wireguard" in backend.lower() or iface == "wg0":
            vpn_header_emoji = EMOJI_WIREGUARD
            conn_badge = f"{EMOJI_WIREGUARD} WireGuard"
        elif "openvpn" in backend.lower() or iface == "tun0":
            vpn_header_emoji = EMOJI_OPENVPN
            conn_badge = f"{EMOJI_OPENVPN} OpenVPN"

        lines.append(f"<b>{vpn_header_emoji} VPN:</b>")
        conn_info = f"({conn_badge} / <code>{iface}</code>)"
        lines.append(f"{icon} Connected: <code>{vpn_connected}</code> {conn_info}")
        if vpn_connected:
            if status["vpn"].get("ip"):
                ip = status["vpn"]["ip"]
                lines.append(f"• Tunnel IP: <tg-spoiler><code>{ip}</code></tg-spoiler>")
            if status["vpn"].get("external_ip"):
                ext_ip = status["vpn"]["external_ip"]
                lines.append(
                    f"• VPN Exit IP: <tg-spoiler><code>{ext_ip}</code></tg-spoiler>"
                )
        lines.append("")

        lines.append(f"<b>{EMOJI_STATS} HOTSPOT:</b>")
        hotspot_active = status["hotspot"]["broadcasting"]
        icon = EMOJI_CHECK if hotspot_active else EMOJI_CROSS
        ssid = get_ssid()
        if ap_mode == "router":
            router_ip = status["hotspot"].get("router_ip", "10.43.0.2")
            alias_ip = status["hotspot"].get("router_alias_ip", "192.168.100.2")
            lines.append(f"{icon} Mode: <b>Router AP</b> (TP-Link via eth1)")
            dash = f'• Dashboard: <a href="http://{router_ip}">http://{router_ip}</a>'
            if alias_ip:
                dash += f' | Via R1: <a href="http://{alias_ip}">http://{alias_ip}</a>'
            lines.append(dash)
        else:
            lines.append(f"{icon} SSID: <code>{ssid}</code>")
        lines.append(f"• Clients: <code>{status['hotspot']['clients']}</code>")
        lines.append("")

        lines.append(f"<b>{EMOJI_GLOBE} NETWORK:</b>")
        wan_info = status.get("wan")
        if wan_info:
            wan_if = wan_info.get("interface")
            wan_type = wan_info.get("type", "WAN")
            wan_icon = (
                "🌐" if wan_if == "eth0" else ("📱" if wan_if == "usb0" else "⚠️")
            )
            wan_desc = f"{wan_type} ({wan_if})" if wan_if else "Disconnected"
            lines.append(f"{wan_icon} Uplink: <code>{wan_desc}</code>")

        dns_ok = status["dns_working"]
        internet_ok = status["internet"]
        ping = status.get("ping", {})
        ping_result = ping.get("summary") if ping else None

        dns_status = "Working" if dns_ok else "Failed"
        dns_icon = EMOJI_CHECK if dns_ok else EMOJI_CROSS
        lines.append(f"{dns_icon} DNS: <code>{dns_status}</code>")
        net_status = "Available" if internet_ok else "Down"
        net_icon = EMOJI_CHECK if internet_ok else EMOJI_CROSS
        lines.append(f"{net_icon} Internet: <code>{net_status}</code>")
        ipv6_mode = status.get("ipv6_protection", "drop")
        lines.append(f"{EMOJI_IPV6} IPv6 Protection: <code>{ipv6_mode.upper()}</code>")

        ping_target = (
            ping.get("target", cfg.get("ping_target", "8.8.8.8"))
            if ping
            else cfg.get("ping_target", "8.8.8.8")
        )

        if ping_result and ping_result != "No ping result":
            safe_ping = html.escape(ping_result)
            lines.append(
                f"{EMOJI_PING} Ping <code>{ping_target}</code>: "
                f"<tg-spoiler><code>{safe_ping}</code></tg-spoiler>"
            )
            if ping.get("avg_ms") and ping.get("avg_ms") != "?":
                loss = ping.get("loss", "?")
                lines.append(
                    f"  └─ <code>RTT avg: {ping['avg_ms']} ms | Loss: {loss}%</code>"
                )
        else:
            ping_icon = EMOJI_CHECK if internet_ok else EMOJI_CROSS
            lines.append(
                f"{ping_icon} Ping <code>{ping_target}</code>: "
                f"<tg-spoiler><code>No ping result</code></tg-spoiler>"
            )

        return "\n".join(lines)

    output = []
    output.append("\n" + "=" * 55)
    output.append(f"{Colors.BOLD}   HOTSPOT STATUS{Colors.RESET}")
    output.append("=" * 55)

    output.append(f"\n{Colors.BOLD}SERVICES:{Colors.RESET}")
    adguard_enabled = get_adg()
    ap_mode = status.get("hotspot", {}).get("ap_mode", "internal")
    for service, ok in status["services"].items():
        if service == "adguard" and not adguard_enabled:
            icon, state = "⏸️", "Disabled"
        elif service == "hostapd" and ap_mode == "router":
            icon, state = "⏸️", "Standby (Router AP)"
        else:
            icon = "✅" if ok else "❌"
            state = "Running" if ok else "Stopped"
        output.append(f"  {icon} {service:<12} {state}")

    output.append(f"\n{Colors.BOLD}VPN:{Colors.RESET}")
    icon = "✅" if status["vpn"]["connected"] else "❌"
    backend = status["vpn"].get("backend", "VPN")
    iface = status["vpn"].get("interface", "unknown")
    output.append(
        f"  {icon} Connected: {status['vpn']['connected']} ({backend} - {iface})"
    )
    if status["vpn"].get("ip"):
        output.append(f"    Tunnel IP: {status['vpn']['ip']}")
    if status["vpn"].get("external_ip"):
        output.append(f"    VPN Exit IP: {status['vpn']['external_ip']}")

    output.append(f"\n{Colors.BOLD}HOTSPOT:{Colors.RESET}")
    icon = "✅" if status["hotspot"]["broadcasting"] else "❌"
    if ap_mode == "router":
        router_ip = status["hotspot"].get("router_ip", "10.43.0.2")
        alias_ip = status["hotspot"].get("router_alias_ip", "192.168.100.2")
        output.append(f"  {icon} Mode: Router AP (TP-Link via eth1)")
        dash = f"    Dashboard: http://{router_ip}"
        output.append(f"{dash} (Via Router 1: http://{alias_ip})" if alias_ip else dash)
    else:
        output.append(f"  {icon} SSID: {get_ssid()}")
    output.append(f"    Clients: {status['hotspot']['clients']}")

    output.append(f"\n{Colors.BOLD}NETWORK:{Colors.RESET}")
    wan_info = status.get("wan")
    if wan_info:
        wan_if = wan_info.get("interface")
        wan_type = wan_info.get("type", "WAN")
        wan_icon = "🌐" if wan_if == "eth0" else ("📱" if wan_if == "usb0" else "⚠️")
        wan_desc = f"{wan_type} ({wan_if})" if wan_if else "Disconnected"
        output.append(f"  {wan_icon} Uplink: {wan_desc}")

    dns_icon = "✅" if status["dns_working"] else "❌"
    output.append(
        f"  {dns_icon} DNS: {'Working' if status['dns_working'] else 'Failed'}"
    )

    internet_icon = "✅" if status["internet"] else "❌"
    internet_state = "Available" if status["internet"] else "Down"
    output.append(f"  {internet_icon} Internet: {internet_state}")
    ipv6_mode = status.get("ipv6_protection", "drop")
    output.append(f"  🛡 IPv6 Protection: {ipv6_mode.upper()}")

    ping = status.get("ping", {})
    ping_icon = "✅" if ping.get("ok") else "❌"
    ping_target = ping.get("target", cfg.get("ping_target", "8.8.8.8"))
    ping_summary = ping.get("summary", "No ping result")
    output.append(f"  {ping_icon} Ping {ping_target}: {ping_summary}")
    if ping.get("avg_ms") and ping.get("avg_ms") != "?":
        output.append(
            f"    RTT avg: {ping['avg_ms']} ms | Loss: {ping.get('loss', '?')}%"
        )

    output.append("=" * 55 + "\n")
    return "\n".join(output)


def send_telegram_notification(message: str) -> bool:
    """Send alert to Telegram admin users if bot credentials are configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
    if not token or not allowed:
        for env_path in [
            "/home/hhk/Projects/networking/telegrambot/.env",
            "/opt/goodwifi/telegrambot/.env",
            "/etc/goodwifi/telegram.env",
        ]:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("TELEGRAM_BOT_TOKEN="):
                                val = line.split("=", 1)[1].strip().strip("\"'")
                                token = token or val
                            elif line.startswith("TELEGRAM_ALLOWED_USERS="):
                                val = line.split("=", 1)[1].strip().strip("\"'")
                                allowed = allowed or val
                except Exception:
                    pass
    if not token or not allowed:
        return False
    uids = [u.strip() for u in allowed.split(",") if u.strip().isdigit()]
    sent = False
    for uid in uids:
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=json.dumps(
                    {"chat_id": uid, "text": message, "parse_mode": "HTML"}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=3)
            sent = True
        except Exception:
            pass
    return sent
