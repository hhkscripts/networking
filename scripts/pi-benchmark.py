#!/usr/bin/env python3
"""Raspberry Pi 5 Performance Benchmark & Comparison Utility.

Collects CPU temp, clock, fan RPM, NVMe health, RAM, ping metrics, and VPN status.
Supports saving snapshots and calculating deltas against previous baseline runs.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import glob
import json
import os
from pathlib import Path
import re
import subprocess
import sys

DEFAULT_STORE = Path.home() / ".pi-benchmarks"
BASELINE_FILE = DEFAULT_STORE / "baseline.json"


def run(cmd: str, timeout: float = 4.0) -> str:
    """Run a shell command and return trimmed output."""
    try:
        res = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_ping_avg(ip: str) -> float:
    """Get average ping round-trip time in milliseconds."""
    out = run(f"ping -c 2 -W 1 {ip} 2>/dev/null")
    match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", out)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return -1.0


def decode_throttled(hex_val: str) -> tuple[bool, str]:
    """Decode Raspberry Pi vcgencmd get_throttled flags."""
    try:
        val = int(hex_val.replace("throttled=", ""), 16)
    except ValueError:
        return True, "Unknown"
    active_issues = []
    if val & 0x1:
        active_issues.append("Under-voltage")
    if val & 0x2:
        active_issues.append("Freq Capped")
    if val & 0x4:
        active_issues.append("Throttled")
    if val & 0x8:
        active_issues.append("Soft Temp Limit")
    if not active_issues:
        return False, "OK (No active throttling)"
    return True, ", ".join(active_issues)


def collect_metrics() -> dict:
    """Gather complete hardware, network, and service metrics."""
    temp_raw = run("vcgencmd measure_temp")
    match_temp = re.search(r"[\d.]+", temp_raw)
    temp_c = float(match_temp.group()) if match_temp else 0.0

    clock_raw = run("vcgencmd measure_clock arm")
    arm_mhz = int(clock_raw.split("=")[-1]) // 1_000_000 if "=" in clock_raw else 0

    throttled_raw = run("vcgencmd get_throttled")
    is_throttled, throttled_msg = decode_throttled(throttled_raw)

    fan_files = glob.glob("/sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input")
    fan_rpm = int(open(fan_files[0]).read().strip()) if fan_files else 0

    mem_total, mem_avail, mem_used = 0, 0, 0
    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    mem[parts[0].strip()] = parts[1].strip().split()[0]
            mem_total = int(mem.get("MemTotal", 0)) // 1024
            mem_avail = int(mem.get("MemAvailable", 0)) // 1024
            mem_used = mem_total - mem_avail

    nvme_smart = run("sudo nvme smart-log /dev/nvme0n1 2>/dev/null")
    nvme_temp, nvme_wear = 0, 0
    for line in nvme_smart.splitlines():
        if "temperature" in line and not nvme_temp:
            m = re.search(r"(\d+)\s*°?C", line)
            if m:
                nvme_temp = int(m.group(1))
        if "percentage_used" in line:
            m = re.search(r"(\d+)%", line)
            if m:
                nvme_wear = int(m.group(1))

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_temp_c": temp_c,
        "fan_rpm": fan_rpm,
        "arm_mhz": arm_mhz,
        "throttled": throttled_msg,
        "is_throttled": is_throttled,
        "ram_used_mb": mem_used,
        "ram_total_mb": mem_total,
        "nvme_temp_c": nvme_temp,
        "nvme_wear_pct": nvme_wear,
        "ping_tplink_ms": get_ping_avg("10.43.0.2"),
        "ping_fiber_ms": get_ping_avg("192.168.100.1"),
        "ping_vpn_ms": get_ping_avg("1.1.1.1"),
        "hostapd_active": run("systemctl is-active hostapd") == "active",
        "dnsmasq_active": run("systemctl is-active dnsmasq") == "active",
        "vpn_exit_ip": run("curl -s --connect-timeout 2 https://api.ipify.org")
        or "Offline",
        "docker_count": int(run("docker ps -q 2>/dev/null | wc -l") or 0),
        "dhcp_clients": int(
            run("cat /var/lib/misc/dnsmasq.leases 2>/dev/null | wc -l") or 0
        ),
    }


def render_dashboard(data: dict) -> str:
    """Render a clean ANSI dashboard from metrics."""
    th_color = "\033[91m" if data["is_throttled"] else "\033[92m"
    rst, bold, cyan = "\033[0m", "\033[1m", "\033[96m"
    ram_pct = (data["ram_used_mb"] / max(1, data["ram_total_mb"])) * 100

    def fmt_ping(ms: float) -> str:
        return f"{ms:.2f} ms" if ms >= 0 else "Unreachable"

    lines = [
        f"\n{bold}{cyan}======================================================={rst}",
        f"{bold}    🚀 RASPBERRY PI 5 PERFORMANCE BENCHMARK {rst}",
        f"{cyan}======================================================={rst}",
        f"📅 Time:        {data['timestamp']}",
        (
            f"🌡️  CPU Temp:    {bold}{data['cpu_temp_c']:.1f}°C{rst}  |  "
            f"Fan: {data['fan_rpm']} RPM"
        ),
        (
            f"⚡ Arm Clock:   {data['arm_mhz']} MHz  |  "
            f"Health: {th_color}{data['throttled']}{rst}"
        ),
        (
            f"🧠 Memory:      {data['ram_used_mb']} MB / "
            f"{data['ram_total_mb']} MB ({ram_pct:.1f}%)"
        ),
        f"💾 NVMe SSD:    {data['nvme_temp_c']}°C  |  Wear: {data['nvme_wear_pct']}%",
        f"{cyan}-------------------------------------------------------{rst}",
        f"{bold}🌐 NETWORK & LATENCY BENCHMARKS:{rst}",
        f"  • TP-Link AP (`10.43.0.2`):        {fmt_ping(data['ping_tplink_ms'])}",
        f"  • Fiber Gateway (`192.168.100.1`): {fmt_ping(data['ping_fiber_ms'])}",
        f"  • Cloudflare via VPN (`1.1.1.1`):  {fmt_ping(data['ping_vpn_ms'])}",
        f"  • VPN Exit IP:                    {data['vpn_exit_ip']}",
        f"{cyan}-------------------------------------------------------{rst}",
        f"{bold}⚙️  SERVICES & WORKLOAD:{rst}",
        (
            f"  • GoodWifi (wlan0):  "
            f"{'✅ Running' if data['hostapd_active'] else '❌ Disabled'}"
        ),
        (
            f"  • DHCP (dnsmasq):    "
            f"{'✅ Running' if data['dnsmasq_active'] else '❌ Stopped'}"
        ),
        f"  • Wi-Fi Clients:     {data['dhcp_clients']} tracked devices",
        f"  • Docker Containers: {data['docker_count']} active containers",
        f"{cyan}======================================================={rst}\n",
    ]
    return "\n".join(lines)


def render_comparison(current: dict, base: dict) -> str:
    """Render side-by-side comparison with deltas."""
    rst, bold, green, red = "\033[0m", "\033[1m", "\033[92m", "\033[91m"

    def diff_num(curr: float, prev: float, unit: str = "", inv: bool = False) -> str:
        delta = curr - prev
        if abs(delta) < 0.01:
            return f"{curr:.1f}{unit} (no change)"
        sign = "+" if delta > 0 else ""
        col = red if (delta > 0 if not inv else delta < 0) else green
        return (
            f"{prev:.1f}{unit} ➔ {curr:.1f}{unit} ({col}{sign}{delta:.1f}{unit}{rst})"
        )

    items = [
        ("CPU Temp", current["cpu_temp_c"], base["cpu_temp_c"], "°C", False),
        ("Fan Speed", current["fan_rpm"], base["fan_rpm"], " RPM", True),
        ("RAM Usage", current["ram_used_mb"], base["ram_used_mb"], " MB", False),
        ("NVMe Temp", current["nvme_temp_c"], base["nvme_temp_c"], "°C", False),
        (
            "TP-Link Ping",
            current["ping_tplink_ms"],
            base["ping_tplink_ms"],
            " ms",
            False,
        ),
        (
            "Fiber Ping",
            current["ping_fiber_ms"],
            base["ping_fiber_ms"],
            " ms",
            False,
        ),
        ("VPN Ping", current["ping_vpn_ms"], base["ping_vpn_ms"], " ms", False),
    ]

    lines = [
        f"\n{bold}📊 PERFORMANCE COMPARISON AGAINST BASELINE:{rst}",
        f"  Baseline Date: {base.get('timestamp', 'Unknown')}",
        f"  Current Date:  {current.get('timestamp', 'Unknown')}",
        "-------------------------------------------------------",
    ]
    for label, c, b, u, inv in items:
        lines.append(f"  {label:<14} {diff_num(c, b, u, inv)}")
    lines.append(
        f"  Docker Active: {current['docker_count']} "
        f"(Base: {base.get('docker_count', 'N/A')})"
    )
    lines.append("-------------------------------------------------------\n")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raspberry Pi 5 Performance Benchmark & Comparison"
    )
    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="Save current run as baseline for future comparisons",
    )
    parser.add_argument(
        "-c",
        "--compare",
        nargs="?",
        const=str(BASELINE_FILE),
        help="Compare against saved baseline (or specified file)",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    metrics = collect_metrics()

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    print(render_dashboard(metrics))

    if args.save:
        DEFAULT_STORE.mkdir(parents=True, exist_ok=True)
        with open(BASELINE_FILE, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"\033[92m✅ Saved baseline to: {BASELINE_FILE}\033[0m\n")

    if args.compare:
        compare_path = Path(args.compare)
        if not compare_path.exists():
            print(f"\033[91m❌ Baseline file not found: {compare_path}\033[0m")
            print("Run with '--save' first to establish a baseline snapshot.\n")
            sys.exit(1)
        with open(compare_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        print(render_comparison(metrics, baseline_data))


if __name__ == "__main__":
    main()
