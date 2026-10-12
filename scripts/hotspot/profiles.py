#!/usr/bin/env python3
"""
Country profiles scanning and metadata mapping for WireGuard and OpenVPN.
"""

import configparser
import os
import re
import socket
import subprocess
from typing import Optional

from .constants import COUNTRY_NAME_MAP, FLAG_MAP, REGION_MAP


def get_country_profiles(
    profiles_dir: Optional[str] = None,
) -> dict[str, dict[str, str]]:
    """Scan profiles folder for WireGuard (.conf) and OpenVPN (.ovpn) files."""
    if not profiles_dir:
        candidates = [
            "/host/etc/goodwifi/profiles",
            "/etc/goodwifi/profiles",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "..", "profiles"
            ),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles"),
            "/app/profiles",
            os.path.join(os.getcwd(), "profiles"),
            "profiles",
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                has_files = any(
                    f.endswith((".ovpn", ".conf"))
                    for _, _, fnames in os.walk(c)
                    for f in fnames
                )
                if has_files:
                    profiles_dir = c
                    break

    if not profiles_dir or not os.path.exists(profiles_dir):
        return {}

    profiles = {}
    name_map = COUNTRY_NAME_MAP
    region_map = REGION_MAP
    found_files = []
    for root, _, fnames in os.walk(profiles_dir):
        for fname in fnames:
            if fname.endswith((".ovpn", ".conf")):
                found_files.append((root, fname))

    for root, fname in sorted(found_files, key=lambda x: x[1]):
        m = re.match(
            r"^([a-z]{2,3}(?:-[a-z]{2,3})?)(?:[-_].*)?\.(?:ovpn|conf)$", fname.lower()
        )
        if m:
            cc = m.group(1)
        else:
            m2 = re.search(r"[-_]([a-z]{2,3}(?:-[a-z]{2,3})?)[-_.]", fname.lower())
            cc = m2.group(1) if m2 else fname.split(".")[0].lower()

        base_cc = cc.split("-")[0]
        flag = FLAG_MAP.get(base_cc, "🌐")
        cname = name_map.get(base_cc, base_cc.upper())
        if "-" in cc:
            cname += " (" + cc.split("-")[1].upper() + ")"

        rel_dir = os.path.basename(root).lower()
        if rel_dir in region_map:
            region = rel_dir
        else:
            region = "other"
            for r_name, r_ccs in region_map.items():
                if base_cc in r_ccs:
                    region = r_name
                    break

        profiles[cc] = {
            "filename": fname,
            "country_code": cc,
            "country_name": cname,
            "flag": flag,
            "region": region,
            "path": os.path.join(root, fname),
        }
    return profiles


def resolve_server_ips(server_host: str) -> list[str]:
    """Resolve all IPv4 addresses for a remote server host using DNS and getaddrinfo."""
    if not server_host or server_host in ["127.0.0.1", "localhost"]:
        return [server_host] if server_host else []

    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", server_host):
        return [server_host]

    ips: list[str] = []
    # 1. Local DNS resolver query via dig
    try:
        res = subprocess.run(
            ["dig", "@127.0.0.1", "-p", "53", server_host, "+short"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if (
                line
                and not line.startswith(";")
                and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", line)
            ):
                ips.append(line)
    except Exception:
        pass

    # 2. Python standard socket.getaddrinfo
    try:
        infos = socket.getaddrinfo(server_host, None, socket.AF_INET)
        for item in infos:
            ip = item[4][0]
            if ip and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                ips.append(ip)
    except Exception:
        pass

    # 3. Upstream fallback query
    if not ips:
        try:
            res = subprocess.run(
                ["dig", "@8.8.8.8", server_host, "+short"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in res.stdout.splitlines():
                line = line.strip()
                if (
                    line
                    and not line.startswith(";")
                    and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", line)
                ):
                    ips.append(line)
        except Exception:
            pass

    unique = list(dict.fromkeys(ips))
    return unique or [server_host]


def get_profile_candidate_ips(profile_path: str) -> list[str]:
    """Extract and resolve candidate server IPs for a given VPN profile."""
    if not profile_path or not os.path.exists(profile_path):
        return []
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            content = f.read()
        if profile_path.endswith(".ovpn"):
            m = re.search(r"^\s*remote\s+([^\s]+)", content, re.MULTILINE)
            if m:
                return resolve_server_ips(m.group(1).strip())
        elif profile_path.endswith(".conf"):
            cp = configparser.ConfigParser()
            cp.read(profile_path)
            endpoint = cp.get("Peer", "endpoint", fallback="")
            host = endpoint.rsplit(":", 1)[0] if ":" in endpoint else endpoint
            if host:
                return resolve_server_ips(host.strip("[]"))
    except Exception:
        pass
    return []


def get_next_profile_ip(
    profile_path: str, current_ip: Optional[str] = None
) -> Optional[str]:
    """Return the next candidate IP from the profile pool for rotation/failover."""
    ips = get_profile_candidate_ips(profile_path)
    if not ips:
        return None
    if current_ip and current_ip in ips:
        idx = (ips.index(current_ip) + 1) % len(ips)
        return ips[idx]
    return ips[0]


def parse_ovpn_endpoint(content: str, target_ip: Optional[str] = None) -> dict:
    """Parse an OpenVPN profile and generate a Sing-box openvpn-client endpoint dict."""

    def _tag(t: str) -> str:
        m = re.search(rf"<{t}>\s*(.*?)\s*</{t}>", content, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _opt(pat: str, default: str = "") -> str:
        m = re.search(pat, content, re.MULTILINE)
        return m.group(1).strip() if m else default

    ca, cert, key = _tag("ca"), _tag("cert"), _tag("key")
    remote_m = re.search(r"^\s*remote\s+([^\s]+)(?:\s+(\d+))?", content, re.MULTILINE)
    server_host = remote_m.group(1).strip() if remote_m else "127.0.0.1"
    server_port = (
        int(remote_m.group(2))
        if (remote_m and remote_m.group(2))
        else int(_opt(r"^\s*port\s+(\d+)", "1194"))
    )
    cipher = _opt(r"^\s*cipher\s+([^\s]+)")
    data_ciphers = list(
        dict.fromkeys([c for c in [cipher, "AES-256-GCM", "AES-256-CBC"] if c])
    )
    auth_val = _opt(r"^\s*auth\s+([^\s]+)", "SHA512").upper()

    tls_name = (
        os.getenv("OPENVPN_TLS_SERVER_NAME")
        or os.getenv("OPENVPN_SERVER_NAME")
        or _opt(r'^\s*(?:verify-x509-name|tls-remote)\s+["\']?([^"\'\s]+)["\']?')
    )
    if not tls_name and re.search(r"[a-zA-Z]", server_host):
        tls_name = (
            "server.ironnodes.com"
            if "vpnunlimitedapp.com" in server_host.lower()
            else server_host
        )

    server_ip = target_ip or (
        resolve_server_ips(server_host)[0] if server_host else "127.0.0.1"
    )
    tls_dict: dict = {
        "certificate": [ca] if ca else [],
        "client_certificate": [cert] if cert else [],
        "client_key": [key] if key else [],
    }
    if tls_name:
        tls_dict["server_name"] = tls_name

    ping_val = _opt(r"^\s*ping\s+(\d+)", "5")
    ping_restart_val = os.getenv("OPENVPN_PING_RESTART", "20s")
    ep_dict = {
        "type": "openvpn-client",
        "tag": "ovpn-out",
        "server": server_ip,
        "server_port": server_port,
        "data_ciphers": data_ciphers,
        "auth": auth_val,
        "tls": tls_dict,
        "ping_interval": f"{ping_val}s" if ping_val else "5s",
        "ping_restart": ping_restart_val,
        "handshake_window": "30s",
        "tls_timeout": "10s",
        "detour": "xray-socks",
    }
    if _opt(r"^\s*reneg-sec\s+(\d+)") == "0":
        ep_dict["renegotiate_disabled"] = True
    return ep_dict


def parse_wg_endpoint(profile_path: str, target_ip: Optional[str] = None) -> dict:
    """Parse a WireGuard profile and generate a Sing-box wireguard endpoint dict."""
    cp = configparser.ConfigParser()
    cp.read(profile_path)
    iface, peer = cp["Interface"], cp["Peer"]
    endpoint = peer.get("endpoint", "")
    server_ip, port_val = (
        endpoint.rsplit(":", 1) if ":" in endpoint else (endpoint, "51820")
    )
    if target_ip:
        server_ip = target_ip
    else:
        ips = resolve_server_ips(server_ip.strip("[]"))
        if ips:
            server_ip = ips[0]
    ep = {
        "type": "wireguard",
        "tag": "wg-out",
        "system": False,
        "address": [
            a.strip() for a in iface.get("address", "").split(",") if a.strip()
        ],
        "private_key": iface.get("privatekey", ""),
        "peers": [
            {
                "address": server_ip.strip().strip("[]"),
                "port": int(str(port_val).strip()),
                "public_key": peer.get("publickey", ""),
                "allowed_ips": ["0.0.0.0/0"],
                "persistent_keepalive_interval": 25,
            }
        ],
        "detour": "xray-socks",
    }
    psk = peer.get("presharedkey")
    if psk:
        ep["peers"][0]["pre_shared_key"] = psk.strip()
    return ep
