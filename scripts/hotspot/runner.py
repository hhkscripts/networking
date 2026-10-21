#!/usr/bin/env python3
"""
Host execution and system runner helpers.
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Optional, Sequence

from .constants import CONFIG, FLAG_MAP, GOODWIFI_CONF
from .context import Context


def get_host_path(path: str) -> str:
    if not os.path.exists(path) and os.path.exists(f"/host{path}"):
        return f"/host{path}"
    return path


def log(msg: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    log_file = cfg.get("log_file", "/var/log/hotspot-manager.log")
    try:
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] [{level}] {msg}\n")
    except Exception:
        pass
    print(msg)


def run_args(cmd: Sequence[str], timeout: int = 30) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return False, "", str(exc)


def load_goodwifi_conf() -> None:
    conf_path = GOODWIFI_CONF
    if not os.path.exists(conf_path) and os.path.exists(f"/host{GOODWIFI_CONF}"):
        conf_path = f"/host{GOODWIFI_CONF}"

    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)

    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    k_map = {
                        "HOTSPOT_IF": "interface_wlan",
                        "HOTSPOT_IP": "hotspot_ip",
                        "HOTSPOT_SUBNET": "hotspot_subnet",
                        "PING_TARGET": "ping_target",
                        "VPN_UUID": "vpn_name",
                        "ADGUARD_CONTAINER": "adguard_container",
                        "TELEGRAM_CONTAINER": "telegram_container",
                        "AP_MODE": "ap_mode",
                        "ROUTER_AP_IF": "router_ap_if",
                        "ROUTER_AP_SUBNET": "router_ap_subnet",
                        "ROUTER_AP_IP": "router_ap_ip",
                        "ROUTER_AP_ROUTER_IP": "router_ap_router_ip",
                        "ROUTER_AP_ALIAS_IP": "router_ap_alias_ip",
                        "VPS_SSH_HOST": "vps_ssh_host",
                        "VPS_SSH_USER": "vps_ssh_user",
                    }
                    if k in k_map and v:
                        cfg[k_map[k]] = v
                    elif k == "ADGUARD_ENABLED" and v:
                        cfg["adguard_enabled"] = v.lower() not in [
                            "false",
                            "0",
                            "off",
                            "no",
                            "disable",
                            "disabled",
                        ]
                    elif k == "VPS_SSH_PORT" and v:
                        try:
                            cfg["vps_ssh_port"] = int(v)
                        except ValueError:
                            pass
        except Exception:
            pass


def update_goodwifi_conf(key: str, value: str) -> bool:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)
    try:
        runner(["sudo", "mkdir", "-p", os.path.dirname(GOODWIFI_CONF)])
        content = ""
        ok, out, _ = runner(["cat", GOODWIFI_CONF])
        if ok and out:
            lines = out.splitlines()
            found = False
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f'{key}="{value}"')
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f'{key}="{value}"')
            content = "\n".join(new_lines) + "\n"
        else:
            content = f'{key}="{value}"\n'

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write(content)
            temp_path = tf.name

        runner(["sudo", "cp", temp_path, GOODWIFI_CONF])
        runner(["sudo", "chmod", "0644", GOODWIFI_CONF])
        os.unlink(temp_path)
        return True
    except Exception as e:
        logger(f"Could not update {GOODWIFI_CONF}: {e}", "WARN")
        return False


def get_configured_backend() -> str:
    if os.path.exists(GOODWIFI_CONF):
        try:
            with open(GOODWIFI_CONF, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("VPN_BACKEND="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val in ["sing0", "awg0", "tun0", "wg0", "auto"]:
                            return val
        except Exception:
            pass
    return "auto"


def get_configured_ipv6_mode() -> str:
    if os.path.exists(GOODWIFI_CONF):
        try:
            with open(GOODWIFI_CONF, "r") as f:
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
    return "reject"


def get_configured_unlimited_country() -> str:
    """Return currently active Unlimited country code or 'direct'."""
    conf_path = GOODWIFI_CONF
    if not os.path.exists(conf_path) and os.path.exists(f"/host{GOODWIFI_CONF}"):
        conf_path = f"/host{GOODWIFI_CONF}"

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


def get_vless_display_name() -> str:
    ctx = Context.get()
    get_country = getattr(
        ctx, "get_configured_unlimited_country", get_configured_unlimited_country
    )
    unlimited_c = get_country()
    if unlimited_c and unlimited_c not in ["direct", "off", "none"]:
        base_cc = unlimited_c.split("-")[0].lower()
        iso = base_cc.upper()
        if len(iso) == 2 and all("A" <= c <= "Z" for c in iso):
            flag = "".join(chr(127397 + ord(c)) for c in iso)
        else:
            flag = FLAG_MAP.get(base_cc, "🌐")
        return f"VLESS [{flag} {unlimited_c.upper()}]"
    return "VLESS"


def check_service(service: str) -> bool:
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    ok, out, _ = runner(["systemctl", "is-active", service])
    return ok and out == "active"


def check_docker_container(container: str) -> Optional[bool]:
    """Check whether a Docker container is running.

    Returns True if running, False if stopped, or None if Docker/container
    is not available.
    """
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    ok, out, _ = runner(
        ["docker", "inspect", "-f", "{{.State.Running}}", container], timeout=5
    )
    if ok and out.lower() in ["true", "false"]:
        return out.lower() == "true"

    ok_sudo, out_sudo, _ = runner(
        ["sudo", "docker", "inspect", "-f", "{{.State.Running}}", container], timeout=5
    )
    if ok_sudo and out_sudo.lower() in ["true", "false"]:
        return out_sudo.lower() == "true"

    if (
        os.path.exists("/host/bin/docker")
        or os.path.exists("/host/usr/bin/docker")
        or os.path.exists("/host/var/run/docker.sock")
    ):
        ok, out, _ = runner(
            [
                "chroot",
                "/host",
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                container,
            ],
            timeout=5,
        )
        if ok and out.lower() in ["true", "false"]:
            return out.lower() == "true"

    return None


def write_json_file(path: str, data: dict) -> bool:
    """Safely write JSON configuration to a destination file using sudo."""
    ctx = Context.get()
    runner = getattr(ctx, "run_args", run_args)
    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        json.dump(data, tf, indent=2)
        tmp = tf.name
    for cmd in [
        ["mkdir", "-p", os.path.dirname(path)],
        ["cp", tmp, path],
        ["chmod", "0644", path],
    ]:
        runner(["sudo"] + cmd)
    os.unlink(tmp)
    return True
