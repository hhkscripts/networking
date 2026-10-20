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
    m = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", out)
    return float(m.group(1)) if m else -1.0


def decode_throttled(hex_val: str) -> tuple[bool, str]:
    """Decode Raspberry Pi vcgencmd get_throttled flags."""
    try:
        val = int(hex_val.replace("throttled=", ""), 16)
    except ValueError:
        return True, "Unknown"
    labels = ["Under-voltage", "Freq Capped", "Throttled", "Soft Temp Limit"]
    issues = [lbl for i, lbl in enumerate(labels) if val & (1 << i)]
    return (bool(issues), ", ".join(issues) if issues else "OK (Normal)")


def get_mem_storage() -> tuple[dict, dict]:
    """Read memory and storage stats via procfs and statvfs."""
    mem = {}
    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as f:
            for line in f:
                if len(p := line.split(":")) == 2:
                    mem[p[0].strip()] = p[1].strip().split()[0]
    m_tot = int(mem.get("MemTotal", 0)) // 1024
    m_avail = int(mem.get("MemAvailable", 0)) // 1024
    s_tot = int(mem.get("SwapTotal", 0)) // 1024
    s_free = int(mem.get("SwapFree", 0)) // 1024

    st = os.statvfs("/")
    d_tot = (st.f_blocks * st.f_frsize) / (1024**3)
    d_avail = (st.f_bavail * st.f_frsize) / (1024**3)

    return {
        "ram_used_mb": m_tot - m_avail,
        "ram_total_mb": m_tot,
        "swap_used_mb": s_tot - s_free,
        "swap_total_mb": s_tot,
    }, {
        "disk_used_gb": round(d_tot - d_avail, 1),
        "disk_total_gb": round(d_tot, 1),
    }


def collect_metrics() -> dict:
    """Gather complete hardware, network, and service metrics."""
    temp_raw = run("vcgencmd measure_temp")
    m_temp = re.search(r"[\d.]+", temp_raw)
    temp_c = float(m_temp.group()) if m_temp else 0.0

    clock_raw = run("vcgencmd measure_clock arm")
    arm_mhz = int(clock_raw.split("=")[-1]) // 1_000_000 if "=" in clock_raw else 0
    is_th, th_msg = decode_throttled(run("vcgencmd get_throttled"))

    fan_files = glob.glob("/sys/devices/platform/cooling_fan/hwmon/hwmon*/fan1_input")
    fan_rpm = int(open(fan_files[0]).read().strip()) if fan_files else 0

    mem_info, disk_info = get_mem_storage()

    smart = run("sudo nvme smart-log /dev/nvme0n1 2>/dev/null")
    nvme_temp = re.search(r"temperature\s*:\s*(\d+)", smart)
    nvme_wear = re.search(r"percentage_used\s*:\s*(\d+)%", smart)
    nvme_written = re.search(r"Data Units Written\s*:\s*[^\(]+\(([^)]+)\)", smart)
    nvme_poh = re.search(r"power_on_hours\s*:\s*([\d,]+)", smart)

    gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
    leases_raw = run("cat /var/lib/misc/dnsmasq.leases 2>/dev/null")
    clients = [
        item.split()[3]
        for item in leases_raw.splitlines()
        if len(item.split()) >= 4 and item.split()[3] != "*"
    ]

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "kernel": run("uname -r"),
        "governor": run(f"cat {gov_path}") or "ondemand",
        "load_avg": [round(x, 2) for x in os.getloadavg()],
        "cpu_temp_c": temp_c,
        "fan_rpm": fan_rpm,
        "arm_mhz": arm_mhz,
        "throttled": th_msg,
        "is_throttled": is_th,
        **mem_info,
        **disk_info,
        "nvme_temp_c": int(nvme_temp.group(1)) if nvme_temp else 0,
        "nvme_wear_pct": int(nvme_wear.group(1)) if nvme_wear else 0,
        "nvme_tb_written": nvme_written.group(1) if nvme_written else "N/A",
        "nvme_poh": nvme_poh.group(1) if nvme_poh else "N/A",
        "ping_tplink_ms": get_ping_avg("10.43.0.2"),
        "ping_fiber_ms": get_ping_avg("192.168.100.1"),
        "ping_google_ms": get_ping_avg("8.8.8.8"),
        "ping_vpn_ms": get_ping_avg("1.1.1.1"),
        "vpn_exit_ip": run("curl -s --connect-timeout 2 https://api.ipify.org")
        or "Offline",
        "hostapd_active": run("systemctl is-active hostapd") == "active",
        "dnsmasq_active": run("systemctl is-active dnsmasq") == "active",
        "docker_count": int(run("docker ps -q 2>/dev/null | wc -l") or 0),
        "clients": clients,
    }


def render_dashboard(d: dict) -> str:
    """Render a clean ANSI dashboard from metrics."""
    th_c = "\033[91m" if d["is_throttled"] else "\033[92m"
    rst, bold, cyan, yellow = "\033[0m", "\033[1m", "\033[96m", "\033[93m"

    r_used, r_tot = d["ram_used_mb"], max(1, d["ram_total_mb"])
    r_pct = (r_used / r_tot) * 100
    d_used, d_tot = d["disk_used_gb"], max(1.0, d["disk_total_gb"])
    d_pct = (d_used / d_tot) * 100

    def fp(ms: float) -> str:
        return f"{ms:.2f} ms" if ms >= 0 else "Unreachable"

    extra = f" (+{len(d['clients'])-6} more)" if len(d["clients"]) > 6 else ""
    cl_names = ", ".join(d["clients"][:6]) + extra
    bar = f"{bold}{cyan}" + "=" * 70 + f"{rst}"
    div = f"{cyan}" + "-" * 70 + f"{rst}"
    gw_off = "❌ Disabled (Offloaded to TP-Link AP)"
    hw_stat = f"{th_c}{d['throttled']}{rst}"

    lines = [
        f"\n{bar}",
        f"{bold}    🚀 RASPBERRY PI 5 ADVANCED TELEMETRY & PERFORMANCE BENCHMARK {rst}",
        f"{bar}",
        f"📅 Time:        {d['timestamp']} | Kernel: {d['kernel']}",
        (
            f"⚡ CPU State:   {d['arm_mhz']} MHz ({d['governor']}) "
            f"| Load: {d['load_avg']} | Health: {hw_stat}"
        ),
        (
            f"🌡️  Temperatures: CPU: {bold}{d['cpu_temp_c']:.1f}°C{rst} "
            f"| Fan: {d['fan_rpm']} RPM | NVMe: {d['nvme_temp_c']}°C"
        ),
        (
            f"💾 NVMe Health: Wear: {d['nvme_wear_pct']}% "
            f"(Health: {100 - d['nvme_wear_pct']}%) "
            f"| Written: {d['nvme_tb_written']}"
        ),
        f"{div}",
        f"{bold}🧠 MEMORY & STORAGE ALLOCATION:{rst}",
        (
            f"  • Physical RAM:  {r_used:,} MB / {r_tot:,} MB "
            f"({r_pct:.1f}% used, {((r_tot-r_used)/1024):.1f} GB free)"
        ),
        f"  • Swap Memory:   {d['swap_used_mb']} MB / {d['swap_total_mb']} MB",
        (
            f"  • NVMe Root (/): {d_used} GB / {d_tot} GB "
            f"({d_pct:.1f}% used, {(d_tot-d_used):.1f} GB free)"
        ),
        f"{div}",
        f"{bold}🌐 NETWORK & LATENCY BENCHMARKS:{rst}",
        f"  • TP-Link AP (10.43.0.2):        {fp(d['ping_tplink_ms'])}",
        f"  • Fiber Gateway (192.168.100.1): {fp(d['ping_fiber_ms'])}",
        f"  • Google DNS Direct (8.8.8.8):   {fp(d['ping_google_ms'])}",
        f"  • Cloudflare via VPN (1.1.1.1):  {fp(d['ping_vpn_ms'])}",
        (
            f"  • VPN Exit IP:                  "
            f"{yellow}{d['vpn_exit_ip']}{rst} (sing0: 10.99.0.1)"
        ),
        f"{div}",
        f"{bold}⚙️  SERVICES, WORKLOAD & CLIENTS:{rst}",
        f"  • GoodWifi (wlan0):  {'✅ Active' if d['hostapd_active'] else gw_off}",
        (
            f"  • DHCP Engine:       "
            f"{'✅ dnsmasq Active' if d['dnsmasq_active'] else '❌ Stopped'}"
        ),
        f"  • Docker Containers: {d['docker_count']} active instances",
        f"  • Connected Clients: {len(d['clients'])} devices [{cl_names or 'None'}]",
        f"{bar}\n",
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

    keys = [
        ("CPU Temp", "cpu_temp_c", "°C", False),
        ("Fan Speed", "fan_rpm", " RPM", True),
        ("RAM Usage", "ram_used_mb", " MB", False),
        ("NVMe Temp", "nvme_temp_c", "°C", False),
        ("TP-Link Ping", "ping_tplink_ms", " ms", False),
        ("Fiber Ping", "ping_fiber_ms", " ms", False),
        ("VPN Ping", "ping_vpn_ms", " ms", False),
    ]

    div = "-" * 70
    lines = [
        f"\n{bold}📊 PERFORMANCE COMPARISON AGAINST BASELINE:{rst}",
        f"  Baseline Date: {base.get('timestamp', 'Unknown')}",
        f"  Current Date:  {current.get('timestamp', 'Unknown')}",
        div,
    ]
    for lbl, k, u, inv in keys:
        c_val, b_val = current.get(k, 0), base.get(k, 0)
        lines.append(f"  {lbl:<16} {diff_num(c_val, b_val, u, inv)}")
    lines.append(
        f"  Docker Active:   {current['docker_count']} "
        f"(Base: {base.get('docker_count', 'N/A')})"
    )
    lines.append(f"{div}\n")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Raspberry Pi 5 Benchmark & Comparison")
    p.add_argument(
        "-s", "--save", action="store_true", help="Save as baseline snapshot"
    )
    p.add_argument(
        "-c",
        "--compare",
        nargs="?",
        const=str(BASELINE_FILE),
        help="Compare with baseline",
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = p.parse_args()

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
        cp = Path(args.compare)
        if not cp.exists():
            print(
                f"\033[91m❌ Baseline not found: {cp}\033[0m\nRun with '--save' first.\n"
            )
            sys.exit(1)
        with open(cp, "r", encoding="utf-8") as f:
            print(render_comparison(metrics, json.load(f)))


if __name__ == "__main__":
    main()
