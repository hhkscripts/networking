#!/usr/bin/env python3
"""
Sing-box configuration generator and server/country detour switcher.
"""

import json
import os
import tempfile
import time
from typing import Optional

from .context import Context
from .profiles import (
    get_country_profiles,
    get_profile_candidate_ips,
    parse_ovpn_endpoint,
    parse_wg_endpoint,
)
from .runner import get_host_path, log, run_args, update_goodwifi_conf


def _write_json_config(path: str, data: dict, runner) -> bool:
    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        json.dump(data, tf, indent=2)
        tmp = tf.name
    if "sing-box" in path and runner(["which", "sing-box"])[0]:
        chk_ok, _, err = runner(["sing-box", "check", "-c", tmp])
        if not chk_ok:
            log(f"Sing-box config check failed: {err}", "ERROR")
            os.unlink(tmp)
            return False
    runner(["sudo", "mkdir", "-p", os.path.dirname(path)])
    runner(["sudo", "cp", tmp, path])
    runner(["sudo", "chmod", "0644", path])
    os.unlink(tmp)
    return True


def generate_singbox_config(
    profile_path: Optional[str] = None, target_ip: Optional[str] = None
) -> dict:
    """Generate Sing-box config with WireGuard or OpenVPN endpoint detour via Xray."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    tun_addr = os.getenv("SINGBOX_TUN_ADDR", "10.99.0.1/30")
    socks_port = int(os.getenv("XRAY_SOCKS_PORT", "10808"))
    socks_host = os.getenv("XRAY_SOCKS_HOST", "127.0.0.1")
    tun_mtu = int(os.getenv("SINGBOX_MTU", os.getenv("VPN_MTU", "1380")))
    cfg = {
        "log": {"level": "warn"},
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": "sing0",
                "address": [tun_addr],
                "auto_route": False,
                "strict_route": False,
                "stack": "system",
                "mtu": tun_mtu,
            }
        ],
        "outbounds": [
            {
                "type": "socks",
                "tag": "xray-socks",
                "server": socks_host,
                "server_port": socks_port,
            }
        ],
        "route": {"rules": [{"action": "sniff"}]},
    }

    out_tag = "xray-socks"
    if profile_path and os.path.exists(profile_path):
        try:
            if profile_path.endswith(".ovpn"):
                with open(profile_path, "r", encoding="utf-8") as f:
                    cfg["endpoints"] = [
                        parse_ovpn_endpoint(f.read(), target_ip=target_ip)
                    ]
                out_tag = "ovpn-out"
            elif profile_path.endswith(".conf"):
                cfg["endpoints"] = [
                    parse_wg_endpoint(profile_path, target_ip=target_ip)
                ]
                out_tag = "wg-out"
        except Exception as e:
            logger(f"Error parsing profile {profile_path}: {e}", "ERROR")

    if out_tag != "xray-socks":
        vps = _get_vps_ips()
        if vps:
            cfg["route"]["rules"].append(
                {"ip_cidr": [f"{ip}/32" for ip in vps], "outbound": "xray-socks"}
            )
    cfg["route"]["rules"].append({"inbound": ["tun-in"], "outbound": out_tag})
    return cfg


def _get_vps_ips() -> list[str]:
    ctx = Context.get()
    xp = getattr(ctx, "get_host_path", get_host_path)("/etc/xray/config.json")
    ips = ["5.183.9.86", "198.71.50.129"]
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


def get_current_singbox_endpoint_ip() -> Optional[str]:
    """Read the currently configured outbound/endpoint server IP from config.json."""
    ctx = Context.get()
    get_path = getattr(ctx, "get_host_path", get_host_path)
    config_path = get_path("/etc/sing-box/config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            endpoints = cfg.get("endpoints", [])
            if endpoints:
                return endpoints[0].get("server") or endpoints[0].get("peers", [{}])[
                    0
                ].get("address")
        except Exception:
            pass
    return None


def _try_activate_endpoints(
    ctx, profile_path: str, candidate_ips: list, country: str
) -> bool:
    runner = getattr(ctx, "run_args", run_args)
    get_path = getattr(ctx, "get_host_path", get_host_path)
    gen_config = getattr(ctx, "generate_singbox_config", generate_singbox_config)
    check_ext = getattr(ctx, "check_vpn_external_ip")
    logger = getattr(ctx, "log", log)
    config_path = get_path("/etc/sing-box/config.json")

    for cand_ip in candidate_ips[:4]:
        cfg = gen_config(profile_path, target_ip=cand_ip)
        _write_json_config(config_path, cfg, runner)
        runner(["sudo", "systemctl", "restart", "sing-box"], timeout=20)
        getattr(ctx, "wait_for_interface")("sing0", timeout=12)
        getattr(ctx, "apply_vpn_policy")("sing0")
        getattr(ctx, "refresh_routes", getattr(ctx, "refresh_github_routes"))()
        ensure_adg = getattr(ctx, "ensure_adguard_resilience", None)
        if ensure_adg:
            ensure_adg()

        ok_ext = False
        for _ in range(4):
            time.sleep(2)
            ok_ext, _ = check_ext()
            if ok_ext:
                break
        if ok_ext:
            target_desc = f" via {cand_ip}" if cand_ip else ""
            logger(f"Connected to {country.upper()}{target_desc}", "SUCCESS")
            return True
        logger(
            f"Endpoint {cand_ip} for '{country.upper()}' did not handshake, "
            "trying next...",
            "WARN",
        )
    return False


def rotate_unlimited_country_ip(country: Optional[str] = None) -> bool:
    """Rotate to the next available endpoint IP for the active country exit."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    get_profiles = getattr(ctx, "get_country_profiles", get_country_profiles)
    get_country = getattr(ctx, "get_configured_unlimited_country")

    if not country:
        country = get_country()
    country = str(country or "direct").lower().strip()
    if country in ["direct", "off", "none"]:
        return getattr(ctx, "switch_unlimited_country")("direct")

    profiles = get_profiles()
    if country not in profiles:
        logger(f"Country profile '{country}' not found.", "ERROR")
        return False

    profile_path = profiles[country]["path"]
    candidate_ips = get_profile_candidate_ips(profile_path)
    current_ip = get_current_singbox_endpoint_ip()
    if current_ip and current_ip in candidate_ips and len(candidate_ips) > 1:
        idx = (candidate_ips.index(current_ip) + 1) % len(candidate_ips)
        ordered_ips = candidate_ips[idx:] + candidate_ips[:idx]
    else:
        ordered_ips = candidate_ips or [None]

    if _try_activate_endpoints(ctx, profile_path, ordered_ips, country):
        return True
    logger(f"All tested endpoints for '{country.upper()}' failed to handshake.", "WARN")
    return False


def switch_unlimited_country(country: str, target_ip: Optional[str] = None) -> bool:
    """Switch Sing-box exit country using KeepSolid profile detour."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    get_path = getattr(ctx, "get_host_path", get_host_path)
    upd_conf = getattr(ctx, "update_goodwifi_conf", update_goodwifi_conf)
    get_profiles = getattr(ctx, "get_country_profiles", get_country_profiles)
    gen_config = getattr(ctx, "generate_singbox_config", generate_singbox_config)

    country = country.lower().strip()
    if country in ["direct", "off", "none"]:
        cfg = gen_config(None)
        config_path = get_path("/etc/sing-box/config.json")
        _write_json_config(config_path, cfg, runner)
        upd_conf("UNLIMITED_COUNTRY", "direct")
        runner(["sudo", "systemctl", "restart", "sing-box"], timeout=20)
        getattr(ctx, "wait_for_interface")("sing0", timeout=10)
        getattr(ctx, "apply_vpn_policy")("sing0")
        getattr(ctx, "refresh_routes", getattr(ctx, "refresh_github_routes"))()
        ensure_adg = getattr(ctx, "ensure_adguard_resilience", None)
        if ensure_adg:
            ensure_adg()
        logger("Switched Multi-Country exit to DIRECT", "SUCCESS")
        return True

    profiles = get_profiles()
    if country not in profiles:
        logger(f"Country profile '{country}' not found.", "ERROR")
        return False

    profile_path = profiles[country]["path"]
    candidate_ips = get_profile_candidate_ips(profile_path)
    if target_ip:
        ordered_ips = [target_ip] + [ip for ip in candidate_ips if ip != target_ip]
    else:
        ordered_ips = candidate_ips or [None]

    upd_conf("UNLIMITED_COUNTRY", country)
    backend = getattr(ctx, "get_configured_backend")()
    if backend != "sing0":
        getattr(ctx, "switch_vpn")("sing0")

    if _try_activate_endpoints(ctx, profile_path, ordered_ips, country):
        return True

    logger(
        f"Country profile '{country.upper()}' did not handshake. "
        "Reverting to Direct VLESS...",
        "WARN",
    )
    switch_unlimited_country("direct")
    return False


def switch_reality_server(server_num: str) -> bool:
    """Switch primary Xray Reality outbound between server-1 and server-2."""
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    get_path = getattr(ctx, "get_host_path", get_host_path)

    config_path = get_path("/etc/xray/config.json")
    if not os.path.exists(config_path):
        logger(f"Xray config not found at {config_path}", "ERROR")
        return False

    target_tag = (
        f"server-{server_num}" if not server_num.startswith("server-") else server_num
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
        _write_json_config(config_path, cfg, runner)

        runner(["sudo", "systemctl", "restart", "xray"], timeout=15)
        logger(f"Switched Reality primary to {target_tag}", "SUCCESS")
        return True
    except Exception as e:
        logger(f"Failed to switch Reality server: {e}", "ERROR")
        return False
