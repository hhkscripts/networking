#!/usr/bin/env python3
"""
Remote VPS execution and exit switcher helper.
Dispatches country switching commands over SSH to remote VPS without hardcoding.
"""

import json
import os
from typing import Optional

from .constants import CONFIG
from .context import Context
from .runner import get_host_path, log, run_args


def get_remote_vps_target() -> tuple[Optional[str], int, str]:
    """Retrieve VPS SSH target details dynamically without hardcoded values.

    Fallback resolution order:
    1. goodwifi.conf (vps_ssh_host, vps_ssh_port, vps_ssh_user)
    2. Environment variables (VPS_SSH_HOST, VPS_SSH_PORT, VPS_SSH_USER)
    3. Active VLESS server address parsed from /etc/xray/config.json
    """
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)

    host = cfg.get("vps_ssh_host") or os.getenv("VPS_SSH_HOST")
    port_val = cfg.get("vps_ssh_port") or os.getenv("VPS_SSH_PORT", 2222)
    user = cfg.get("vps_ssh_user") or os.getenv("VPS_SSH_USER", "root")

    try:
        port = int(port_val)
    except (ValueError, TypeError):
        port = 2222

    if not host:
        get_path = getattr(ctx, "get_host_path", get_host_path)
        xp = get_path("/etc/xray/config.json")
        if os.path.exists(xp):
            try:
                with open(xp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for o in data.get("outbounds", []):
                    if o.get("protocol") == "vless":
                        vnext = o.get("settings", {}).get("vnext", [])
                        if vnext and vnext[0].get("address"):
                            host = vnext[0]["address"]
                            break
            except Exception:
                pass

    return host, port, user


def is_remote_vps_configured() -> bool:
    """Check if a remote VPS target can be resolved."""
    ctx = Context.get()
    get_target = getattr(ctx, "get_remote_vps_target", get_remote_vps_target)
    host, _, _ = get_target()
    return bool(host)


def get_vps_ips() -> list[str]:
    """Retrieve all VLESS outbound server addresses from xray config."""
    ctx = Context.get()
    xp = getattr(ctx, "get_host_path", get_host_path)("/etc/xray/config.json")
    ips: list[str] = []
    if os.path.exists(xp):
        try:
            with open(xp, "r", encoding="utf-8") as f:
                for o in json.load(f).get("outbounds", []):
                    addr = o.get("settings", {}).get("vnext", [{}])[0].get("address")
                    if addr and addr not in ips:
                        ips.append(addr)
        except Exception:
            pass
    return ips


def switch_remote_vps_exit(country: str, timeout: int = 15) -> tuple[bool, str]:
    """Execute switch-exit on remote VPS via SSH without password.

    Returns (success, message_or_stdout).
    """
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    get_target = getattr(ctx, "get_remote_vps_target", get_remote_vps_target)

    host, port, user = get_target()
    if not host:
        return False, "No remote VPS target detected or configured"

    cmd = [
        "ssh",
        "-p",
        str(port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        f"/usr/local/bin/switch-exit {country}",
    ]
    logger(f"Switching remote exit on VPS ({host}:{port}) to '{country}'...", "INFO")
    success, stdout, stderr = runner(cmd, timeout=timeout)
    if success:
        logger(f"Remote VPS switched exit to '{country}': {stdout}", "SUCCESS")
        return True, stdout

    err = stderr or stdout or "SSH connection to remote VPS failed"
    logger(f"Failed to switch remote VPS exit: {err}", "ERROR")
    return False, err


def switch_reality_server(server_num: str) -> bool:
    """Switch primary Xray Reality outbound between server-1 and server-2."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    get_path = getattr(ctx, "get_host_path", get_host_path)
    write_fn = getattr(ctx, "write_json_file", None)
    if not write_fn:
        from .runner import write_json_file

        write_fn = write_json_file

    config_path = get_path("/etc/xray/config.json")
    if not os.path.exists(config_path):
        logger(f"Xray config not found at {config_path}", "ERROR")
        return False

    target_tag = (
        server_num if server_num.startswith("server-") else f"server-{server_num}"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        target = next(
            (o for o in cfg.get("outbounds", []) if o.get("tag") == target_tag), None
        )
        if not target:
            logger(f"Reality server '{target_tag}' not found in config", "ERROR")
            return False

        cfg["outbounds"] = [target] + [
            o for o in cfg.get("outbounds", []) if o.get("tag") != target_tag
        ]
        write_fn(config_path, cfg)

        runner(["sudo", "systemctl", "restart", "xray"], timeout=15)
        logger(f"Switched Reality primary to {target_tag}", "SUCCESS")
        return True
    except Exception as e:
        logger(f"Failed to switch Reality server: {e}", "ERROR")
        return False
