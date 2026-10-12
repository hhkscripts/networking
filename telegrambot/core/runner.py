"""Execution wrapper for hotspot-manager.py and config state inspection."""

import asyncio
import os
import subprocess
from typing import List, Tuple

from telegrambot.constants.emojis import (
    TG_EMOJI_AMNEZIAWG,
    TG_EMOJI_OPENVPN,
    TG_EMOJI_VLESS,
    TG_EMOJI_WIREGUARD,
)
from telegrambot.core.dynamic_emojis import (
    enrich_status_text_with_custom_emojis,
    format_country_badge,
)


def run_hotspot_command(args: List[str]) -> Tuple[str, str, int]:
    """Run hotspot-manager.py in the host namespaces."""
    try:
        script_path = os.environ.get(
            "HOTSPOT_MANAGER_HOST_PATH", "/usr/local/bin/hotspot-manager.py"
        )
        cmd = [
            "nsenter",
            "--target",
            "1",
            "--mount",
            "--uts",
            "--ipc",
            "--net",
            "--pid",
            "--",
            "python3",
            script_path,
        ] + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1


async def get_status_text() -> str:
    """Fetch current hotspot and VPN status output formatted as HTML."""
    loop = asyncio.get_running_loop()
    stdout, stderr, code = await loop.run_in_executor(
        None, run_hotspot_command, ["--status", "--html"]
    )
    if code != 0 and not stdout:
        return f"Error getting status:\n{stderr}"
    text = stdout if stdout else "No output from hotspot manager."
    return enrich_status_text_with_custom_emojis(text, get_current_unlimited_country())


def get_current_unlimited_country() -> str:
    """Read the configured UNLIMITED_COUNTRY from goodwifi.conf."""
    conf_path = "/host/etc/goodwifi/goodwifi.conf"
    if not os.path.exists(conf_path):
        conf_path = "/etc/goodwifi/goodwifi.conf"
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("UNLIMITED_COUNTRY="):
                        return (
                            line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                        )
        except Exception:
            pass
    return "direct"


def get_current_backend_name() -> str:
    """Resolve and format the currently active VPN backend name."""
    conf_path = "/host/etc/goodwifi/goodwifi.conf"
    if not os.path.exists(conf_path):
        conf_path = "/etc/goodwifi/goodwifi.conf"
    backend = "auto"
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VPN_BACKEND="):
                        backend = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    # Detect currently active network interface
    active_iface = None
    for iface in ["sing0", "awg0", "tun0", "wg0"]:
        if os.path.exists(f"/host/sys/class/net/{iface}") or os.path.exists(
            f"/sys/class/net/{iface}"
        ):
            active_iface = iface
            break

    target_backend = backend
    if target_backend == "auto" and active_iface:
        target_backend = active_iface

    unlimited_c = get_current_unlimited_country()
    vless_label = f"{TG_EMOJI_VLESS} VLESS Reality (sing0)"
    if unlimited_c and unlimited_c not in ["direct", "off", "none"]:
        badge = format_country_badge(unlimited_c)
        vless_label += f" [{badge} {unlimited_c.upper()}]"

    names = {
        "sing0": vless_label,
        "awg0": f"{TG_EMOJI_AMNEZIAWG} AmneziaWG (awg0)",
        "tun0": f"{TG_EMOJI_OPENVPN} OpenVPN (tun0)",
        "wg0": f"{TG_EMOJI_WIREGUARD} WireGuard (wg0)",
    }
    resolved = names.get(target_backend)
    if resolved:
        return resolved
    if backend == "auto":
        return "Auto (Disconnected)"
    return backend


def get_current_ipv6_mode() -> str:
    """Read the configured IPV6_LEAK_PROTECTION mode."""
    conf_path = "/host/etc/goodwifi/goodwifi.conf"
    if not os.path.exists(conf_path):
        conf_path = "/etc/goodwifi/goodwifi.conf"

    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("IPV6_LEAK_PROTECTION="):
                        val = (
                            line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                        )
                        if val in ["drop", "reject", "off"]:
                            return val
        except Exception:
            pass
    return "drop"


def get_current_adguard_state() -> bool:
    """Check whether AdGuard Home DNS protection is enabled."""
    conf_path = "/host/etc/goodwifi/goodwifi.conf"
    if not os.path.exists(conf_path):
        conf_path = "/etc/goodwifi/goodwifi.conf"

    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ADGUARD_ENABLED="):
                        val = (
                            line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                        )
                        if val in ["false", "0", "off", "no", "disable", "disabled"]:
                            return False
                        elif val in ["true", "1", "on", "yes", "enable", "enabled"]:
                            return True
        except Exception:
            pass
    return True


def get_available_vpn_backends() -> dict[str, bool]:
    """Inspect configured and available VPN backends on the host.

    Returns dict mapping backend keys ('sing0', 'awg0', 'tun0', 'wg0')
    to their availability status.
    """
    backends = {"sing0": False, "awg0": False, "tun0": False, "wg0": False}

    # Check sing-box / xray
    for base in ["/host", ""]:
        if (
            os.path.exists(f"{base}/etc/sing-box/config.json")
            or os.path.exists(f"{base}/etc/xray/config.json")
            or os.path.exists(f"{base}/sys/class/net/sing0")
        ):
            backends["sing0"] = True
            break

    # Check AmneziaWG
    for base in ["/host", ""]:
        if (
            os.path.exists(f"{base}/etc/amnezia/amneziawg/awg0.conf")
            or os.path.exists(f"{base}/sys/class/net/awg0")
            or os.path.isdir(f"{base}/etc/amnezia/amneziawg")
        ):
            backends["awg0"] = True
            break

    # Check WireGuard
    for base in ["/host", ""]:
        if os.path.exists(f"{base}/etc/wireguard/wg0.conf") or os.path.exists(
            f"{base}/sys/class/net/wg0"
        ):
            backends["wg0"] = True
            break

    # Check OpenVPN (tun0)
    for base in ["/host", ""]:
        if (
            os.path.exists(f"{base}/sys/class/net/tun0")
            or os.path.isdir(f"{base}/etc/openvpn/client")
            or os.path.isdir(f"{base}/etc/NetworkManager/system-connections")
        ):
            backends["tun0"] = True
            break

    # If completely unconfigured/zero detected (e.g. fresh environment or CI),
    # fallback to standard defaults so UI remains functional
    if not any(backends.values()):
        return {"sing0": True, "awg0": True, "tun0": True, "wg0": False}

    return backends


def get_amnezia_profiles() -> list[tuple[str, str]]:
    """Detect available AmneziaWG configs on host."""
    profiles: list[tuple[str, str]] = []
    for base in ["/host", ""]:
        awg_dir = f"{base}/etc/amnezia/amneziawg"
        if os.path.isdir(awg_dir):
            try:
                for fname in sorted(os.listdir(awg_dir)):
                    if fname.endswith(".conf"):
                        iface = fname.replace(".conf", "")
                        profiles.append((iface, f"AmneziaWG ({iface})"))
            except Exception:
                pass
        if profiles:
            return profiles
    return [("awg0", "AmneziaWG (awg0)")]


def get_openvpn_profiles() -> list[tuple[str, str]]:
    """Detect available OpenVPN client configs on host."""
    profiles: list[tuple[str, str]] = []
    seen: set[str] = set()
    for base in ["/host", ""]:
        for d in [f"{base}/etc/openvpn/client", f"{base}/etc/openvpn"]:
            if os.path.isdir(d):
                try:
                    for fname in sorted(os.listdir(d)):
                        if fname.endswith((".ovpn", ".conf")):
                            name = fname.rsplit(".", 1)[0]
                            if name not in seen and name != "update-resolv-conf":
                                seen.add(name)
                                profiles.append((name, f"OpenVPN ({name})"))
                except Exception:
                    pass
        if profiles:
            return profiles
    return [("tun0", "OpenVPN (tun0)")]


def get_vless_servers() -> list[tuple[str, str]]:
    """Detect configured VLESS Reality outbounds from xray config."""
    import json

    for base in ["/host", ""]:
        xray_path = f"{base}/etc/xray/config.json"
        if os.path.exists(xray_path):
            try:
                with open(xray_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                servers = []
                for o in cfg.get("outbounds", []):
                    tag = o.get("tag", "")
                    if tag.startswith("server-"):
                        s_num = tag.replace("server-", "")
                        addr = (
                            o.get("settings", {})
                            .get("vnext", [{}])[0]
                            .get("address", "")
                        )
                        label = f"VLESS S{s_num}"
                        if addr:
                            short_ip = (
                                ".".join(addr.split(".")[:2]) if "." in addr else addr
                            )
                            label += f" ({short_ip})"
                        servers.append((s_num, label))
                if servers:
                    return servers
            except Exception:
                pass
    return [("1", "VLESS S1 (198.71)"), ("2", "VLESS S2 (5.183)")]
