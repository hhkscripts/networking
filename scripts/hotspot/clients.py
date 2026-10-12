#!/usr/bin/env python3
"""
Connected clients detection, station dump parsing, and formatting.
"""

import html
import os
import re
import time
from typing import Optional

from .constants import CONFIG, Colors, EMOJI_CLIENTS
from .context import Context
from .runner import get_host_path, run_args
from .vendors import get_device_icon, get_mac_vendor


def format_bytes(n: int) -> str:
    """Format bytes to human readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def format_duration(seconds: int) -> str:
    """Format seconds into readable duration (e.g. 1h 24m)."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def get_signal_info(signal: int) -> tuple[str, str]:
    """Return signal icon and descriptive quality."""
    if signal >= -50:
        return "🟢", f"{signal} dBm (Excellent)"
    if signal >= -65:
        return "🟢", f"{signal} dBm (Good)"
    if signal >= -75:
        return "🟡", f"{signal} dBm (Fair)"
    return "🔴", f"{signal} dBm (Weak)"


def parse_station_dump_text(text: str) -> dict[str, dict]:
    """Parse `iw dev <wlan> station dump` output into stations dict keyed by MAC."""
    stations: dict[str, dict] = {}
    current_mac: Optional[str] = None
    data: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Station "):
            if current_mac:
                stations[current_mac.lower()] = data
            parts = line.split()
            current_mac = parts[1].lower() if len(parts) > 1 else None
            data = {}
        elif current_mac and ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            num = re.search(r"(-?\d+)", v)
            if k in ("signal", "connected time", "rx bytes", "tx bytes") and num:
                data[k.replace(" ", "_")] = int(num.group(1))
            elif k in ("tx bitrate", "rx bitrate"):
                data[k.replace(" ", "_")] = v
    if current_mac:
        stations[current_mac.lower()] = data
    return stations


def get_wifi_stations() -> dict[str, dict]:
    """Query iw dev station dump for active wireless clients."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    wlan = getattr(ctx, "CONFIG", CONFIG).get("interface_wlan", "wlan0")
    for dev in dict.fromkeys([wlan, "wlan0", "wlan1", "ap0"]):
        for bin_path in ["sudo iw", "/usr/sbin/iw", "iw"]:
            ok, out, _ = runner(bin_path.split() + ["dev", dev, "station", "dump"])
            if ok and out:
                parsed = parse_station_dump_text(out)
                if parsed:
                    for val in parsed.values():
                        val["interface"] = dev
                    return parsed
    return {}


def _build_client_entry(
    mac: str,
    ip: str,
    hostname: str,
    vendor: str,
    st: Optional[dict] = None,
    expiry: Optional[int] = None,
    now: int = 0,
) -> dict:
    st = st or {}
    sig = st.get("signal")
    sig_badge = get_signal_info(sig)[1] if sig is not None else None
    conn_time = st.get("connected_time")
    rx_b = st.get("rx_bytes")
    tx_b = st.get("tx_bytes")
    lease_str = None
    if expiry is not None:
        if expiry == 0:
            lease_str = "Static"
        elif expiry > now:
            lease_str = f"{format_duration(expiry - now)} remaining"
        else:
            lease_str = "Expired"

    return {
        "mac": mac,
        "ip": ip or "Unknown",
        "hostname": hostname or "Unknown",
        "vendor": vendor,
        "interface": st.get("interface", "wlan0"),
        "signal": sig,
        "signal_quality": sig_badge,
        "connected_time": conn_time,
        "connected_time_str": (
            format_duration(conn_time) if conn_time is not None else None
        ),
        "rx_bytes": rx_b,
        "tx_bytes": tx_b,
        "rx_bytes_str": format_bytes(rx_b) if rx_b is not None else None,
        "tx_bytes_str": format_bytes(tx_b) if tx_b is not None else None,
        "tx_bitrate": st.get("tx_bitrate"),
        "rx_bitrate": st.get("rx_bitrate"),
        "lease_expiry": expiry,
        "lease_remaining_str": lease_str,
        "icon": get_device_icon(hostname or "Unknown", vendor),
    }


def get_connected_clients_detailed() -> list[dict]:
    """Return enriched list of connected client device details."""
    ctx = Context.get()
    get_path = getattr(ctx, "get_host_path", get_host_path)
    now = int(time.time())

    lease_files = [
        get_path("/var/lib/misc/dnsmasq.leases"),
        "/var/lib/misc/dnsmasq.leases",
        "/host/var/lib/misc/dnsmasq.leases",
    ]
    leases_by_mac: dict[str, dict] = {}
    for lfile in lease_files:
        if os.path.exists(lfile):
            try:
                with open(lfile, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            expiry = int(parts[0]) if parts[0].isdigit() else 0
                            mac = parts[1].lower()
                            leases_by_mac[mac] = {
                                "expiry": expiry,
                                "ip": parts[2],
                                "hostname": parts[3] if parts[3] != "*" else "Unknown",
                            }
                if leases_by_mac:
                    break
            except Exception:
                pass

    wifi_stations = get_wifi_stations()
    neigh_by_mac: dict[str, dict] = {}
    runner = getattr(ctx, "run_args", run_args)
    ok, out, _ = runner(["ip", "neigh", "show"])
    if ok and out:
        for line in out.splitlines():
            parts = line.strip().split()
            if (
                len(parts) >= 5
                and "lladdr" in parts
                and parts[-1] in ("REACHABLE", "DELAY", "STALE")
            ):
                idx = parts.index("lladdr")
                if idx + 1 < len(parts):
                    neigh_by_mac[parts[idx + 1].lower()] = {"ip": parts[0]}

    devices = []
    seen = set()
    for mac, st in wifi_stations.items():
        seen.add(mac)
        lease = leases_by_mac.get(mac, {})
        ip = lease.get("ip") or neigh_by_mac.get(mac, {}).get("ip") or "Unknown"
        hname = lease.get("hostname", "Unknown")
        devices.append(
            _build_client_entry(
                mac, ip, hname, get_mac_vendor(mac), st, lease.get("expiry"), now
            )
        )

    if not devices:
        for mac, lease in leases_by_mac.items():
            if mac not in seen:
                seen.add(mac)
                devices.append(
                    _build_client_entry(
                        mac, lease["ip"], lease["hostname"], get_mac_vendor(mac),
                        None, lease.get("expiry"), now
                    )
                )

    if not devices:
        for mac, neigh in neigh_by_mac.items():
            if mac not in seen:
                seen.add(mac)
                devices.append(
                    _build_client_entry(
                        mac, neigh["ip"], "Unknown", get_mac_vendor(mac), None, None, now
                    )
                )

    return devices


def format_clients(clients: list[dict], telegram_format: bool = False) -> str:
    """Format connected client devices for Telegram HTML or Terminal."""
    count = len(clients)
    if telegram_format:
        lines = [f"<b>{EMOJI_CLIENTS} CONNECTED CLIENTS ({count})</b>", "━━━━━━━━━━━━━━━━━━━━━━"]
        if not clients:
            lines.append("<i>No connected devices found.</i>")
            return "\n".join(lines)

        for dev in clients:
            hname = html.escape(str(dev.get("hostname", "Unknown")))
            vname = html.escape(str(dev.get("vendor", "Unknown")))
            lines.extend([
                f"{dev.get('icon', '📱')} <b>{hname}</b>",
                f"• IP: <code>{html.escape(str(dev.get('ip', 'N/A')))}</code>",
                f"• MAC: <code>{html.escape(str(dev.get('mac', 'N/A')))}</code> <i>({vname})</i>",
            ])
            if dev.get("signal_quality"):
                lines.append(f"• Signal: {dev['signal_quality']}")
            if dev.get("rx_bytes_str") or dev.get("tx_bytes_str"):
                lines.append(
                    f"• Traffic: ⬇️ <code>{dev.get('rx_bytes_str', '0 B')}</code> | "
                    f"⬆️ <code>{dev.get('tx_bytes_str', '0 B')}</code>"
                )
            if dev.get("tx_bitrate"):
                lines.append(f"• Rate: <code>{dev['tx_bitrate']}</code>")
            if dev.get("connected_time_str"):
                lines.append(f"• Duration: ⏱️ <code>{dev['connected_time_str']}</code>")
            if dev.get("lease_remaining_str"):
                lines.append(f"• Lease: ⏳ <code>{dev['lease_remaining_str']}</code>")
            lines.append("")

        lines.extend(["━━━━━━━━━━━━━━━━━━━━━━", f"📶 Total Active Devices: <code>{count}</code>"])
        return "\n".join(lines)

    out = ["\n" + "=" * 55, f"{Colors.BOLD}   CONNECTED CLIENTS ({count}){Colors.RESET}", "=" * 55]
    if not clients:
        out.append("No connected devices found.\n")
        return "\n".join(out)

    for i, dev in enumerate(clients, 1):
        out.extend([
            f"\n[{i}] {Colors.BOLD}{dev.get('hostname', 'Unknown')}{Colors.RESET}",
            f"    IP:       {dev.get('ip', 'N/A')}",
            f"    MAC:      {dev.get('mac', 'N/A')} ({dev.get('vendor', 'Unknown')})",
        ])
        if dev.get("signal_quality"):
            out.append(f"    Signal:   {dev['signal_quality']}")
        if dev.get("rx_bytes_str") or dev.get("tx_bytes_str"):
            out.append(f"    Traffic:  RX: {dev.get('rx_bytes_str', '0 B')} | TX: {dev.get('tx_bytes_str', '0 B')}")
        if dev.get("tx_bitrate"):
            out.append(f"    Rate:     {dev['tx_bitrate']}")
        if dev.get("connected_time_str"):
            out.append(f"    Duration: {dev['connected_time_str']}")
        if dev.get("lease_remaining_str"):
            out.append(f"    Lease:    {dev['lease_remaining_str']}")

    out.extend(["\n" + "=" * 55, f"Total Active Devices: {count}\n"])
    return "\n".join(out)
