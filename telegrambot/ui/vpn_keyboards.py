"""VPN backend switcher inline keyboard builder."""

from typing import Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegrambot.constants.emojis import (
    EMOJI_AMNEZIAWG,
    EMOJI_GLOBE,
    EMOJI_OPENVPN,
    EMOJI_REFRESH,
    EMOJI_VLESS,
    EMOJI_WIREGUARD,
)
from telegrambot.core.runner import (
    get_amnezia_profiles,
    get_available_vpn_backends,
    get_openvpn_profiles,
    get_vless_servers,
)


def make_switch_vpn_keyboard(
    available: Optional[Dict[str, bool]] = None,
) -> InlineKeyboardMarkup:
    """Build the inline keyboard for choosing VPN backend category / protocol."""
    if available is None:
        available = get_available_vpn_backends()

    keyboard: List[List[InlineKeyboardButton]] = []
    buttons: List[InlineKeyboardButton] = []

    # 1. Other VPN protocol buttons (AmneziaWG, OpenVPN, WireGuard)
    if available.get("awg0", False):
        awg_profiles = get_amnezia_profiles()
        cb = "menu_awg" if len(awg_profiles) > 1 else f"switch_{awg_profiles[0][0]}"
        buttons.append(
            InlineKeyboardButton(
                "AmneziaWG",
                callback_data=cb,
                icon_custom_emoji_id=EMOJI_AMNEZIAWG,
            )
        )
    if available.get("tun0", False):
        ovpn_profiles = get_openvpn_profiles()
        cb = "menu_ovpn" if len(ovpn_profiles) > 1 else f"switch_{ovpn_profiles[0][0]}"
        buttons.append(
            InlineKeyboardButton(
                "OpenVPN",
                callback_data=cb,
                icon_custom_emoji_id=EMOJI_OPENVPN,
            )
        )
    if available.get("wg0", False):
        buttons.append(
            InlineKeyboardButton(
                "WireGuard",
                callback_data="switch_wg0",
                icon_custom_emoji_id=EMOJI_WIREGUARD,
            )
        )

    # 2. Sing-box / VLESS Reality sub-menu trigger
    if available.get("sing0", False):
        buttons.append(
            InlineKeyboardButton(
                "VLESS Reality",
                callback_data="menu_vless",
                icon_custom_emoji_id=EMOJI_VLESS,
            )
        )

    # 3. Multi-Country detour profiles sub-menu trigger
    if available.get("sing0", False):
        buttons.append(
            InlineKeyboardButton(
                "VPN Profiles",
                callback_data="menu_country",
                icon_custom_emoji_id=EMOJI_GLOBE,
            )
        )

    # 4. Auto (Auto Select)
    buttons.append(
        InlineKeyboardButton(
            "Auto Select",
            callback_data="switch_auto",
            icon_custom_emoji_id=EMOJI_REFRESH,
        )
    )

    back_btn = InlineKeyboardButton("🔙 Back to Status", callback_data="refresh_status")

    # Balance into a neat 2x2 grid without dangling single buttons
    if len(buttons) % 2 == 1:
        last = buttons.pop()
        for i in range(0, len(buttons), 2):
            keyboard.append(buttons[i : i + 2])
        keyboard.append([last, back_btn])
    else:
        for i in range(0, len(buttons), 2):
            keyboard.append(buttons[i : i + 2])
        keyboard.append([back_btn])

    return InlineKeyboardMarkup(keyboard)


def make_vless_keyboard(
    vless_servers: Optional[List[Tuple[str, str]]] = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting VLESS Reality servers."""
    if vless_servers is None:
        vless_servers = get_vless_servers()

    keyboard: List[List[InlineKeyboardButton]] = []
    if vless_servers:
        row: List[InlineKeyboardButton] = []
        for s_num, label in vless_servers:
            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"switch_reality_{s_num}",
                    icon_custom_emoji_id=EMOJI_VLESS,
                )
            )
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "VLESS Reality (sing0)",
                    callback_data="switch_sing0",
                    icon_custom_emoji_id=EMOJI_VLESS,
                )
            ]
        )

    # Navigation: Back to VPN Menu
    keyboard.append(
        [
            InlineKeyboardButton("🔙 Back to VPN Menu", callback_data="menu_switch"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def make_amnezia_keyboard(
    profiles: Optional[List[Tuple[str, str]]] = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for choosing AmneziaWG profile."""
    if profiles is None:
        profiles = get_amnezia_profiles()

    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for iface, label in profiles:
        row.append(
            InlineKeyboardButton(
                label,
                callback_data=f"switch_{iface}",
                icon_custom_emoji_id=EMOJI_AMNEZIAWG,
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton("🔙 Back to VPN Menu", callback_data="menu_switch"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def make_openvpn_keyboard(
    profiles: Optional[List[Tuple[str, str]]] = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for choosing OpenVPN profile."""
    if profiles is None:
        profiles = get_openvpn_profiles()

    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for iface, label in profiles:
        row.append(
            InlineKeyboardButton(
                label,
                callback_data=f"switch_{iface}",
                icon_custom_emoji_id=EMOJI_OPENVPN,
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton("🔙 Back to VPN Menu", callback_data="menu_switch"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)
