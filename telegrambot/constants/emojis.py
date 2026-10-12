"""Telegram custom emojis and HTML formatted emoji tags."""

import os


def _emoji_id(env_name: str, default: str) -> str:
    return os.getenv(env_name, default)


# Premium Custom Emoji IDs (used for button icons)
EMOJI_STATS = _emoji_id("TG_EMOJI_STATS", "6143449494244563627")  # 📶 / 📊 Stats
EMOJI_CLIENTS = _emoji_id("TG_EMOJI_CLIENTS", "6127157759872868272")  # 📡 Clients
EMOJI_REFRESH = _emoji_id("TG_EMOJI_REFRESH", "6057439501377085156")  # 🔄 Refresh
EMOJI_LOCK = _emoji_id("TG_EMOJI_LOCK", "6059947491695008618")  # 🔒 Lock / VPN
EMOJI_TOOLS = _emoji_id("TG_EMOJI_TOOLS", "6141134446742478627")  # 🔧 Tools / Fix
EMOJI_HELP = _emoji_id("TG_EMOJI_HELP", "6307322000033458270")  # 📔 Book / Help
EMOJI_WIREGUARD = _emoji_id("TG_EMOJI_WIREGUARD", "6165512058344318397")  # 🐉 WireGuard
EMOJI_OPENVPN = _emoji_id("TG_EMOJI_OPENVPN", "6165724869678866601")  # 🔐 OpenVPN
EMOJI_AMNEZIAWG = _emoji_id("TG_EMOJI_AMNEZIAWG", "6165519909544534378")  # 🛡 AmneziaWG
EMOJI_VLESS = _emoji_id("TG_EMOJI_VLESS", "6197318808022032017")  # 🛡 VLESS
EMOJI_SINGBOX = _emoji_id("TG_EMOJI_SINGBOX", EMOJI_VLESS)  # 🛡 Sing-box Reality
EMOJI_RPI = _emoji_id("TG_EMOJI_RPI", "6165792622787961093")  # 🍓 Raspberry Pi
EMOJI_ADGUARD = _emoji_id("TG_EMOJI_ADGUARD", "6165657271188594962")  # 🛡 AdGuard
EMOJI_IPV6 = _emoji_id("TG_EMOJI_IPV6", "6165466570345686935")  # 🔒 IPv6
EMOJI_GLOBE = _emoji_id("TG_EMOJI_GLOBE", "6057443049020071219")  # 🌐 Globe


def format_tg_emoji(emoji_id: str, fallback_char: str) -> str:
    """Format custom emoji tag, or fallback to Unicode character."""
    if os.getenv("DISABLE_CUSTOM_EMOJIS", "0") == "1" or not emoji_id:
        return fallback_char
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback_char}</tg-emoji>'


# HTML formatted Telegram Premium Custom Emojis (for in-text messages)
TG_EMOJI_WIREGUARD = format_tg_emoji(EMOJI_WIREGUARD, "🐉")
TG_EMOJI_OPENVPN = format_tg_emoji(EMOJI_OPENVPN, "🔐")
TG_EMOJI_AMNEZIAWG = format_tg_emoji(EMOJI_AMNEZIAWG, "🛡")
TG_EMOJI_VLESS = format_tg_emoji(EMOJI_VLESS, "🛡")
TG_EMOJI_SINGBOX = TG_EMOJI_VLESS
TG_EMOJI_RPI = format_tg_emoji(EMOJI_RPI, "🍓")
TG_EMOJI_ADGUARD = format_tg_emoji(EMOJI_ADGUARD, "🛡")
TG_EMOJI_IPV6 = format_tg_emoji(EMOJI_IPV6, "🔒")
TG_EMOJI_GLOBE = format_tg_emoji(EMOJI_GLOBE, "🌐")
TG_EMOJI_CLIENTS = format_tg_emoji(EMOJI_CLIENTS, "📡")
