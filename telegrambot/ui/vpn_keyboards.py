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
    get_available_vpn_backends,
    get_vless_servers,
)


def make_switch_vpn_keyboard(
    available: Optional[Dict[str, bool]] = None,
    vless_servers: Optional[List[Tuple[str, str]]] = None,
) -> InlineKeyboardMarkup:
    """Build the inline keyboard dynamically for available VPN backends."""
    if available is None:
        available = get_available_vpn_backends()

    keyboard: List[List[InlineKeyboardButton]] = []

    # 1. Sing-box / VLESS Reality buttons (if available)
    vless_buttons: List[InlineKeyboardButton] = []
    if available.get("sing0", False):
        if vless_servers is None:
            vless_servers = get_vless_servers()

        if vless_servers:
            for s_num, label in vless_servers:
                vless_buttons.append(
                    InlineKeyboardButton(
                        label,
                        callback_data=f"switch_reality_{s_num}",
                        icon_custom_emoji_id=EMOJI_VLESS,
                    )
                )
        else:
            vless_buttons.append(
                InlineKeyboardButton(
                    "VLESS Reality (sing0)",
                    callback_data="switch_sing0",
                    icon_custom_emoji_id=EMOJI_VLESS,
                )
            )

    # 2. Other VPN protocol buttons (AmneziaWG, OpenVPN, WireGuard)
    proto_buttons: List[InlineKeyboardButton] = []
    if available.get("awg0", False):
        proto_buttons.append(
            InlineKeyboardButton(
                "AmneziaWG (awg0)",
                callback_data="switch_awg0",
                icon_custom_emoji_id=EMOJI_AMNEZIAWG,
            )
        )
    if available.get("tun0", False):
        proto_buttons.append(
            InlineKeyboardButton(
                "OpenVPN (tun0)",
                callback_data="switch_tun0",
                icon_custom_emoji_id=EMOJI_OPENVPN,
            )
        )
    if available.get("wg0", False):
        proto_buttons.append(
            InlineKeyboardButton(
                "WireGuard (wg0)",
                callback_data="switch_wg0",
                icon_custom_emoji_id=EMOJI_WIREGUARD,
            )
        )

    # 3. Mode buttons: Exit Country & Auto (Auto Select)
    mode_buttons: List[InlineKeyboardButton] = []
    if available.get("sing0", False):
        mode_buttons.append(
            InlineKeyboardButton(
                "Exit Country",
                callback_data="menu_country",
                icon_custom_emoji_id=EMOJI_GLOBE,
            )
        )
    mode_buttons.append(
        InlineKeyboardButton(
            "Auto (Auto Select)",
            callback_data="switch_auto",
            icon_custom_emoji_id=EMOJI_REFRESH,
        )
    )

    # If VLESS has an odd single button (e.g. single sing0) and Exit Country is available,
    # pair them together gracefully (both are Sing-box features)
    if (
        len(vless_buttons) % 2 == 1
        and mode_buttons
        and mode_buttons[0].callback_data == "menu_country"
    ):
        first_btn = vless_buttons.pop(0)
        country_btn = mode_buttons.pop(0)
        keyboard.append([first_btn, country_btn])

    for i in range(0, len(vless_buttons), 2):
        keyboard.append(vless_buttons[i : i + 2])

    for i in range(0, len(proto_buttons), 2):
        chunk = proto_buttons[i : i + 2]
        if len(chunk) == 2:
            keyboard.append(chunk)
        else:
            if mode_buttons:
                keyboard.append([chunk[0], mode_buttons.pop(0)])
            else:
                keyboard.append(chunk)

    for i in range(0, len(mode_buttons), 2):
        keyboard.append(mode_buttons[i : i + 2])

    # 4. Navigation: Back to Status
    keyboard.append(
        [
            InlineKeyboardButton("🔙 Back to Status", callback_data="refresh_status"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)
