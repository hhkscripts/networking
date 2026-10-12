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
from .runner import run_args
from .vendors import (
    format_bytes,
    format_duration,
    get_device_icon,
    get_mac_vendor,
    get_signal_info,
)


def parse_station_dump_text(text: str) -> dict[str, dict]:
    """Parse `iw dev <wlan> station dump` output into stations dict keyed by MAC."""
    stations: dict[str, dict] = {}
    cur_mac: Optional[str] = None
    data: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Station "):
            if cur_mac:
                stations[cur_mac.lower()] = data
            parts = line.split()
            cur_mac = parts[1].lower() if len(parts) > 1 else None
            data = {}
        elif cur_mac and ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            num = re.search(r"(-?\d+)", v)
            if k in ("signal", "connected time", "rx bytes", "tx bytes") and num:
                data[k.replace(" ", "_")] = int(num.group(1))
            elif k in ("tx bitrate", "rx bitrate"):
                data[k.replace(" ", "_")] = v
    if cur_mac:
        stations[cur_mac.lower()] = data
    return stations


def get_wifi_stations() -> dict[str, dict]:
    """Query iw dev station dump for active wireless clients."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    wlan = getattr(ctx, "CONFIG", CONFIG).get("interface_wlan", "wlan0")
    for dev in dict.fromkeys([wlan, "wlan0", "wlan1", "ap0"]):
        for bin_cmd in ["sudo iw", "/usr/sbin/iw", "iw"]:
            ok, out, _ = runner(bin_cmd.split() + ["dev", dev, "station", "dump"])
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
    rx_b, tx_b = st.get("rx_bytes"), st.get("tx_bytes")
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
        "connected_time_str": format_duration(conn_time) if conn_time else None,
        "rx_bytes": rx_b,
        "tx_bytes": tx_b,
        "rx_bytes_str": format_bytes(rx_b) if rx_b else None,
        "tx_bytes_str": format_bytes(tx_b) if tx_b else None,
        "tx_bitrate": st.get("tx_bitrate"),
        "rx_bitrate": st.get("rx_bitrate"),
        "lease_expiry": expiry,
        "lease_remaining_str": lease_str,
        "icon": get_device_icon(hostname or "Unknown", vendor),
    }


def get_connected_clients_detailed() -> list[dict]:
    """Return enriched list of connected client device details."""
    ctx = Context.get()
    now = int(time.time())

    lease_files = [
        "/var/lib/misc/dnsmasq.leases",
        "/host/var/lib/misc/dnsmasq.leases",
    ]
    if hasattr(ctx, "get_host_path"):
        lease_files.insert(0, ctx.get_host_path("/var/lib/misc/dnsmasq.leases"))

    leases_by_mac: dict[str, dict] = {}
    for lfile in lease_files:
        if os.path.exists(lfile):
            try:
                with open(lfile, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            exp = int(parts[0]) if parts[0].isdigit() else 0
                            mac = parts[1].lower()
                            leases_by_mac[mac] = {
                                "expiry": exp,
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
                mac,
                ip,
                hname,
                get_mac_vendor(mac),
                st,
                lease.get("expiry"),
                now,
            )
        )

    if not devices:
        for mac, lease in leases_by_mac.items():
            if mac not in seen:
                seen.add(mac)
                devices.append(
                    _build_client_entry(
                        mac,
                        lease["ip"],
                        lease["hostname"],
                        get_mac_vendor(mac),
                        None,
                        lease.get("expiry"),
                        now,
                    )
                )

    if not devices:
        for mac, neigh in neigh_by_mac.items():
            if mac not in seen:
                seen.add(mac)
                devices.append(
                    _build_client_entry(
                        mac,
                        neigh["ip"],
                        "Unknown",
                        get_mac_vendor(mac),
                        None,
                        None,
                        now,
                    )
                )

    return devices


def format_clients(clients: list[dict], telegram_format: bool = False) -> str:
    """Format connected client devices for Telegram HTML or Terminal."""
    count = len(clients)
    if telegram_format:
        lines = [
            f"<b>{EMOJI_CLIENTS} CONNECTED CLIENTS ({count})</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]
        if not clients:
            return "\n".join(lines + ["<i>No connected devices found.</i>"])

        for dev in clients:
            hname = html.escape(str(dev.get("hostname", "Unknown")))
            vname = html.escape(str(dev.get("vendor", "Unknown")))
            ip_val = html.escape(str(dev.get("ip", "N/A")))
            mac_val = html.escape(str(dev.get("mac", "N/A")))
            lines.extend(
                [
                    f"{dev.get('icon', '📱')} <b>{hname}</b>",
                    f"• IP: <code>{ip_val}</code>",
                    f"• MAC: <code>{mac_val}</code> <i>({vname})</i>",
                ]
            )
            if dev.get("signal_quality"):
                lines.append(f"• Signal: {dev['signal_quality']}")
            rx, tx = dev.get("rx_bytes_str"), dev.get("tx_bytes_str")
            if rx or tx:
                traffic = (
                    f"⬇️ <code>{rx or '0 B'}</code> | ⬆️ <code>{tx or '0 B'}</code>"
                )
                lines.append(f"• Traffic: {traffic}")
            if dev.get("tx_bitrate"):
                lines.append(f"• Rate: <code>{dev['tx_bitrate']}</code>")
            if dev.get("connected_time_str"):
                lines.append(f"• Duration: ⏱️ <code>{dev['connected_time_str']}</code>")
            if dev.get("lease_remaining_str"):
                lines.append(f"• Lease: ⏳ <code>{dev['lease_remaining_str']}</code>")
            lines.append("")

        footer = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📶 Total Active Devices: <code>{count}</code>",
        ]
        return "\n".join(lines + footer)

    out = [
        "\n" + "=" * 55,
        f"{Colors.BOLD}   CONNECTED CLIENTS ({count}){Colors.RESET}",
        "=" * 55,
    ]
    if not clients:
        return "\n".join(out + ["No connected devices found.\n"])

    for i, dev in enumerate(clients, 1):
        hname = dev.get("hostname", "Unknown")
        mac = dev.get("mac", "N/A")
        vname = dev.get("vendor", "Unknown")
        rx, tx = dev.get("rx_bytes_str"), dev.get("tx_bytes_str")
        out.extend(
            [
                f"\n[{i}] {Colors.BOLD}{hname}{Colors.RESET}",
                f"    IP:       {dev.get('ip', 'N/A')}",
                f"    MAC:      {mac} ({vname})",
            ]
        )
        if dev.get("signal_quality"):
            out.append(f"    Signal:   {dev['signal_quality']}")
        if rx or tx:
            out.append(f"    Traffic:  RX: {rx or '0 B'} | TX: {tx or '0 B'}")
        if dev.get("tx_bitrate"):
            out.append(f"    Rate:     {dev['tx_bitrate']}")
        if dev.get("connected_time_str"):
            out.append(f"    Duration: {dev['connected_time_str']}")
        if dev.get("lease_remaining_str"):
            out.append(f"    Lease:    {dev['lease_remaining_str']}")

    return "\n".join(out + ["\n" + "=" * 55, f"Total Active Devices: {count}\n"])
