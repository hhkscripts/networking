#!/usr/bin/env python3
"""
Hotspot Manager Constants, Types, and Configurations.
"""

import os
from typing import Optional, TypedDict


class Config(TypedDict, total=False):
    services: list[str]
    vpn_name: str
    default_hotspot_ssid: str
    hostapd_conf: str
    hotspot_ip: str
    interface_wlan: str
    log_file: str
    ping_target: str
    hotspot_subnet: str
    routing_table: int
    dns_test_domain: str
    adguard_container: str
    telegram_container: str
    adguard_enabled: bool
    ap_mode: str
    router_ap_if: str
    router_ap_subnet: str
    router_ap_ip: str
    router_ap_router_ip: str
    vps_ssh_host: Optional[str]
    vps_ssh_port: Optional[int]
    vps_ssh_user: Optional[str]


class PingStatus(TypedDict):
    ok: bool
    target: str
    summary: str
    rtt: str
    loss: str
    avg_ms: str


class VpnStatus(TypedDict):
    connected: bool
    interface: str
    backend: str
    ip: Optional[str]
    external_ip: Optional[str]
    external_ok: bool


class HotspotInfo(TypedDict, total=False):
    broadcasting: bool
    clients: int
    ap_mode: str
    router_ip: str


class WanStatus(TypedDict, total=False):
    interface: Optional[str]
    type: str
    metric: int


class HotspotStatus(TypedDict, total=False):
    services: dict[str, bool]
    vpn: VpnStatus
    hotspot: HotspotInfo
    dns_working: bool
    internet: bool
    ping: PingStatus
    ipv6_protection: str
    wan: WanStatus


CONFIG: Config = {
    "services": ["hostapd", "dnsmasq"],
    "vpn_name": "",
    "default_hotspot_ssid": "GoodWifi",
    "hostapd_conf": "/etc/hostapd/hostapd.conf",
    "hotspot_ip": os.getenv("HOTSPOT_IP", "10.42.0.1"),
    "interface_wlan": os.getenv("HOTSPOT_IFACE", "wlan0"),
    "log_file": "/var/log/hotspot-manager.log",
    "ping_target": os.getenv("PING_TARGET", "8.8.8.8"),
    "hotspot_subnet": os.getenv("HOTSPOT_SUBNET", "10.42.0.0/24"),
    "routing_table": int(os.getenv("HOTSPOT_ROUTING_TABLE", "100")),
    "dns_test_domain": os.getenv("DNS_TEST_DOMAIN", "google.com"),
    "adguard_container": os.getenv("ADGUARD_CONTAINER", "adguardhome"),
    "telegram_container": os.getenv("TELEGRAM_CONTAINER", "mpxraspberrypibot"),
    "adguard_enabled": True,
    "ap_mode": os.getenv("AP_MODE", "router"),
    "router_ap_if": os.getenv("ROUTER_AP_IF", "eth1"),
    "router_ap_subnet": os.getenv("ROUTER_AP_SUBNET", "10.43.0.0/24"),
    "router_ap_ip": os.getenv("ROUTER_AP_IP", "10.43.0.1"),
    "router_ap_router_ip": os.getenv("ROUTER_AP_ROUTER_IP", "10.43.0.2"),
}

GITHUB_ROUTE_SCRIPT = "/usr/local/bin/github-vpn-routes.sh"
APPLY_ROUTE_SCRIPT = "/usr/local/bin/apply-routes.sh"
POLICY_SCRIPT = "/etc/NetworkManager/dispatcher.d/90-hotspot-vpn-policy"
GOODWIFI_CONF = "/etc/goodwifi/goodwifi.conf"


def _get_tg_emoji(key: str, default_id: str, char: str) -> str:
    eid = os.getenv(f"TG_EMOJI_{key.upper()}", default_id)
    if os.getenv("DISABLE_CUSTOM_EMOJIS", "0") == "1" or not eid:
        return char
    return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'


CUSTOM_EMOJIS = {
    "signal": _get_tg_emoji("signal", "6127157759872868272", "📡"),
    "tools": _get_tg_emoji("tools", "6141134446742478627", "🔧"),
    "check": _get_tg_emoji("check", "6114156013399579882", "✅"),
    "lock": _get_tg_emoji("lock", "6059947491695008618", "🔒"),
    "stats": _get_tg_emoji("stats", "6143449494244563627", "📶"),
    "globe": _get_tg_emoji("globe", "6057443049020071219", "🌐"),
    "cross": _get_tg_emoji("cross", "6111658378247806635", "❌"),
    "ping": _get_tg_emoji("ping", "6060045064762039982", "⏲"),
    "wireguard": _get_tg_emoji("wireguard", "6165512058344318397", "🐉"),
    "openvpn": _get_tg_emoji("openvpn", "6165724869678866601", "🔐"),
    "amneziawg": _get_tg_emoji("amneziawg", "6165519909544534378", "🛡"),
    "vless": _get_tg_emoji("vless", "6197318808022032017", "🛡"),
    "singbox": _get_tg_emoji("singbox", "6197318808022032017", "🛡"),
    "raspberrypi": _get_tg_emoji("raspberrypi", "6165792622787961093", "🍓"),
    "adguard": _get_tg_emoji("adguard", "6165657271188594962", "🛡"),
    "ipv6": _get_tg_emoji("ipv6", "6165466570345686935", "🔒"),
    "clients": _get_tg_emoji("clients", "6127157759872868272", "📡"),
}

EMOJI_SIGNAL = CUSTOM_EMOJIS["signal"]
EMOJI_CLIENTS = CUSTOM_EMOJIS["clients"]
EMOJI_TOOLS = CUSTOM_EMOJIS["tools"]
EMOJI_CHECK = CUSTOM_EMOJIS["check"]
EMOJI_LOCK = CUSTOM_EMOJIS["lock"]
EMOJI_STATS = CUSTOM_EMOJIS["stats"]
EMOJI_GLOBE = CUSTOM_EMOJIS["globe"]
EMOJI_CROSS = CUSTOM_EMOJIS["cross"]
EMOJI_PING = CUSTOM_EMOJIS["ping"]
EMOJI_WIREGUARD = CUSTOM_EMOJIS["wireguard"]
EMOJI_OPENVPN = CUSTOM_EMOJIS["openvpn"]
EMOJI_AMNEZIAWG = CUSTOM_EMOJIS["amneziawg"]
EMOJI_VLESS = CUSTOM_EMOJIS["vless"]
EMOJI_SINGBOX = CUSTOM_EMOJIS["singbox"]
EMOJI_RPI = CUSTOM_EMOJIS["raspberrypi"]
EMOJI_ADGUARD = CUSTOM_EMOJIS["adguard"]
EMOJI_IPV6 = CUSTOM_EMOJIS["ipv6"]

FLAG_MAP = {
    "sg": "🇸🇬",
    "jp": "🇯🇵",
    "us": "🇺🇸",
    "uk": "🇬🇧",
    "gb": "🇬🇧",
    "de": "🇩🇪",
    "fr": "🇫🇷",
    "ca": "🇨🇦",
    "au": "🇦🇺",
    "nl": "🇳🇱",
    "hk": "🇭🇰",
    "in": "🇮🇳",
    "kr": "🇰🇷",
    "th": "🇹🇭",
    "at": "🇦🇹",
    "ba": "🇧🇦",
    "br": "🇧🇷",
    "ch": "🇨🇭",
    "se": "🇸🇪",
    "no": "🇳🇴",
    "fi": "🇫🇮",
    "es": "🇪🇸",
    "it": "🇮🇹",
    "pl": "🇵🇱",
    "ie": "🇮🇪",
    "nz": "🇳🇿",
    "mx": "🇲🇽",
    "za": "🇿🇦",
    "my": "🇲🇾",
    "vn": "🇻🇳",
    "id": "🇮🇩",
    "ph": "🇵🇭",
    "tw": "🇹🇼",
    "cl": "🇨🇱",
    "cz": "🇨🇿",
    "dk": "🇩🇰",
    "gr": "🇬🇷",
    "hr": "🇭🇷",
    "il": "🇮🇱",
    "lt": "🇱🇹",
    "lux": "🇱🇺",
    "lu": "🇱🇺",
    "ae": "🇦🇪",
    "ng": "🇳🇬",
    "ua": "🇺🇦",
}

COUNTRY_NAME_MAP: dict[str, str] = {
    "sg": "Singapore",
    "jp": "Japan",
    "us": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "de": "Germany",
    "fr": "France",
    "ca": "Canada",
    "au": "Australia",
    "nl": "Netherlands",
    "hk": "Hong Kong",
    "in": "India",
    "kr": "South Korea",
    "th": "Thailand",
    "at": "Austria",
    "ba": "Bosnia",
    "br": "Brazil",
    "ch": "Switzerland",
    "se": "Sweden",
    "no": "Norway",
    "fi": "Finland",
    "es": "Spain",
    "it": "Italy",
    "pl": "Poland",
    "ie": "Ireland",
    "nz": "New Zealand",
    "mx": "Mexico",
    "za": "South Africa",
    "my": "Malaysia",
    "vn": "Vietnam",
    "id": "Indonesia",
    "ph": "Philippines",
    "tw": "Taiwan",
    "cl": "Chile",
    "cz": "Czech Republic",
    "dk": "Denmark",
    "gr": "Greece",
    "hr": "Croatia",
    "il": "Israel",
    "lt": "Lithuania",
    "lux": "Luxembourg",
    "lu": "Luxembourg",
    "ae": "United Arab Emirates",
    "ng": "Nigeria",
    "ua": "Ukraine",
}

REGION_MAP: dict[str, list[str]] = {
    "asia": "ae il in jp kr sg hk th my vn id ph tw".split(),
    "europe": (
        "at ba ch cz de dk es fr gr hr it lt lux lu nl no pl se ua uk gb fi ie"
    ).split(),
    "americas": "br ca cl mx us".split(),
    "oceania-africa": "au nz ng za".split(),
}


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
