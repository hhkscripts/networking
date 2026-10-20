#!/usr/bin/env python3
"""
AdGuard Home and DNS security management.
"""

import os
import tempfile
import time

from .constants import CONFIG, GOODWIFI_CONF
from .context import Context
from .runner import (
    check_docker_container,
    check_service,
    get_host_path,
    log,
    run_args,
    update_goodwifi_conf,
)


def _find_adguard_target(ctx) -> tuple[str, str, bool]:
    cfg = getattr(ctx, "CONFIG", CONFIG)
    chk_c = getattr(ctx, "check_docker_container", check_docker_container)
    chk_s = getattr(ctx, "check_service", check_service)
    configured_name = cfg.get("adguard_container", "adguardhome")

    st = chk_c(configured_name)
    if st is True:
        return "docker", configured_name, True
    if st is False:
        return "docker", configured_name, False

    # Default container name not found; check compose and service alternatives
    for alt in ["vpn-adguardhome-1", "vpn_adguardhome_1", "adguard"]:
        st_alt = chk_c(alt)
        if st_alt is True:
            return "docker", alt, True
        if st_alt is False:
            return "docker", alt, False

    if chk_s("AdGuardHome"):
        return "systemd", "AdGuardHome", True

    return "docker", configured_name, False


def get_adguard_enabled() -> bool:
    ctx = Context.get()
    get_path = getattr(ctx, "get_host_path", get_host_path)

    conf_path = get_path(GOODWIFI_CONF)
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
    _, _, running = _find_adguard_target(ctx)
    return running


def configure_dnsmasq_fallback(enable_fallback: bool) -> bool:
    ctx = Context.get()
    get_path = getattr(ctx, "get_host_path", get_host_path)
    runner = getattr(ctx, "run_args", run_args)
    logger = getattr(ctx, "log", log)

    conf_path = get_path("/etc/dnsmasq.conf")
    if not os.path.exists(conf_path):
        return False
    try:
        with open(conf_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        new_lines = []
        if enable_fallback:
            has_fallback_server = False
            for line in lines:
                stripped = line.strip()
                if stripped == "port=0":
                    new_lines.append("#port=0")
                    new_lines.append("server=8.8.8.8")
                    new_lines.append("server=9.9.9.9")
                    has_fallback_server = True
                elif (
                    stripped.startswith("server=8.8.8.8")
                    or stripped.startswith("server=9.9.9.9")
                    or stripped.startswith("server=1.1.1.1")
                ):
                    has_fallback_server = True
                    new_lines.append(line)
                else:
                    new_lines.append(line)
            if not has_fallback_server:
                new_lines.append("server=8.8.8.8")
                new_lines.append("server=9.9.9.9")
        else:
            has_port_zero = False
            for line in lines:
                stripped = line.strip()
                if (
                    stripped.startswith("server=1.1.1.1")
                    or stripped.startswith("server=8.8.8.8")
                    or stripped.startswith("server=9.9.9.9")
                ):
                    continue
                if stripped == "#port=0":
                    new_lines.append("port=0")
                    has_port_zero = True
                else:
                    if stripped == "port=0":
                        has_port_zero = True
                    new_lines.append(line)
            if not has_port_zero:
                new_lines.insert(0, "port=0")

        new_content = "\n".join(new_lines) + "\n"
        if new_content == content:
            return True
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write(new_content)
            temp_path = tf.name
        runner(["sudo", "cp", temp_path, conf_path])
        runner(["sudo", "chmod", "0644", conf_path])
        os.unlink(temp_path)
        return True
    except Exception as e:
        logger(f"Could not update dnsmasq config: {e}", "WARN")
        return False


def set_adguard_state(enable: bool) -> bool:
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    upd_conf = getattr(ctx, "update_goodwifi_conf", update_goodwifi_conf)
    cfg_dnsmasq = getattr(ctx, "configure_dnsmasq_fallback", configure_dnsmasq_fallback)

    tgt_type, tgt_name, _ = _find_adguard_target(ctx)
    if enable:
        logger("Enabling AdGuard Home DNS service...")
        upd_conf("ADGUARD_ENABLED", "true")
        cfg_dnsmasq(enable_fallback=False)
        runner(["sudo", "systemctl", "restart", "dnsmasq"], timeout=30)
        if tgt_type == "docker":
            ok, _, _ = runner(["docker", "start", tgt_name], timeout=30)
            if not ok:
                project_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                compose_file = os.path.join(
                    project_dir, "adguard", "docker-compose.yml"
                )
                if os.path.exists(compose_file):
                    runner(
                        [
                            "docker",
                            "compose",
                            "-f",
                            compose_file,
                            "up",
                            "-d",
                        ],
                        timeout=60,
                    )
        else:
            runner(["sudo", "systemctl", "start", tgt_name], timeout=30)
        time.sleep(2)
        _, _, running = _find_adguard_target(ctx)
        if running:
            logger("AdGuard Home is now running and handling DNS.")
            return True
        else:
            logger("Could not start AdGuard Home service.", "WARN")
            return False
    else:
        logger("Disabling AdGuard Home DNS service (switching to fallback DNS)...")
        upd_conf("ADGUARD_ENABLED", "false")
        if tgt_type == "docker":
            runner(["docker", "stop", tgt_name], timeout=30)
        else:
            runner(["sudo", "systemctl", "stop", tgt_name], timeout=30)
        cfg_dnsmasq(enable_fallback=True)
        runner(["sudo", "systemctl", "restart", "dnsmasq"], timeout=30)
        time.sleep(1)
        chk_dns = getattr(ctx, "check_dns")
        dns_ok = chk_dns()
        if dns_ok:
            logger("AdGuard Home disabled. Fallback DNS is active and working.")
        else:
            logger("AdGuard Home disabled, but fallback DNS check failed.", "WARN")
        return True


def set_ipv6_mode(mode: str) -> bool:
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    upd_conf = getattr(ctx, "update_goodwifi_conf", update_goodwifi_conf)
    apply_pol = getattr(ctx, "apply_vpn_policy")

    mode = mode.lower()
    if mode not in ["drop", "reject", "off"]:
        logger(f"Invalid mode: {mode}. Choose from: drop, reject, off", "ERROR")
        return False
    upd_conf("IPV6_LEAK_PROTECTION", mode)
    logger(f"Set IPV6_LEAK_PROTECTION to {mode}")
    return apply_pol()


def ensure_adguard_resilience() -> tuple[bool, str]:
    """Check AdGuard status and automatically failover to dnsmasq if unhealthy.

    Returns (success, state_description).
    """
    ctx = Context.get()
    logger = getattr(ctx, "log", log)
    runner = getattr(ctx, "run_args", run_args)
    cfg_dnsmasq = getattr(ctx, "configure_dnsmasq_fallback", configure_dnsmasq_fallback)
    get_enabled = getattr(ctx, "get_adguard_enabled", get_adguard_enabled)

    is_enabled = get_enabled()
    if not is_enabled:
        cfg_dnsmasq(enable_fallback=True)
        return True, "fallback_active"

    tgt_type, tgt_name, running = _find_adguard_target(ctx)
    if running:
        cfg_dnsmasq(enable_fallback=False)
        return True, "adguard_healthy"

    logger(
        f"AdGuard Home ({tgt_name}) is stopped. Attempting recovery...",
        "WARN",
    )
    cfg_dnsmasq(enable_fallback=False)
    runner(["sudo", "systemctl", "restart", "dnsmasq"], timeout=15)
    if tgt_type == "docker":
        runner(["docker", "start", tgt_name], timeout=20)
    else:
        runner(["sudo", "systemctl", "start", tgt_name], timeout=20)
    time.sleep(1)

    _, _, running = _find_adguard_target(ctx)
    if running:
        logger(f"AdGuard Home ({tgt_name}) recovered and active.", "SUCCESS")
        return True, "adguard_recovered"

    if tgt_type == "docker":
        proj_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        compose_file = os.path.join(proj_dir, "adguard", "docker-compose.yml")
        if os.path.exists(compose_file):
            runner(["docker", "compose", "-f", compose_file, "up", "-d"], timeout=30)
            time.sleep(2)
            _, _, running = _find_adguard_target(ctx)
            if running:
                logger("AdGuard Home recovered via docker compose.", "SUCCESS")
                return True, "adguard_recovered"

    logger(
        f"AdGuard Home ({tgt_name}) could not be started! "
        "Activating emergency DNS fallback via dnsmasq...",
        "WARN",
    )
    cfg_dnsmasq(enable_fallback=True)
    runner(["sudo", "systemctl", "restart", "dnsmasq"], timeout=30)
    return True, "fallback_activated"
