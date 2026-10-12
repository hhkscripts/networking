"""Status menu inline keyboard builder."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegrambot.constants.emojis import (
    EMOJI_ADGUARD,
    EMOJI_GLOBE,
    EMOJI_IPV6,
    EMOJI_REFRESH,
    EMOJI_WIREGUARD,
)
from telegrambot.core.runner import get_current_adguard_state


def make_status_keyboard(status_text: str) -> InlineKeyboardMarkup:
    """Build the inline keyboard displayed under the status output."""
    switch_btn = InlineKeyboardButton(
        "Switch VPN",
        callback_data="menu_switch",
        icon_custom_emoji_id=EMOJI_WIREGUARD,
    )
    country_btn = InlineKeyboardButton(
        "VPN Profiles",
        callback_data="menu_country",
        icon_custom_emoji_id=EMOJI_GLOBE,
    )

    adguard_running = (
        "<code>adguard</code>: Running" in status_text
        or "adguard: Running" in status_text
        or "adguard      Running" in status_text
        or get_current_adguard_state()
    )
    adguard_btn = InlineKeyboardButton(
        f"AdGuard: {'ON' if adguard_running else 'OFF'}",
        callback_data="menu_adguard",
        icon_custom_emoji_id=EMOJI_ADGUARD,
    )
    ipv6_btn = InlineKeyboardButton(
        "IPv6 Mode",
        callback_data="menu_ipv6",
        icon_custom_emoji_id=EMOJI_IPV6,
    )
    refresh_btn = InlineKeyboardButton(
        "Refresh Status",
        callback_data="refresh_status",
        icon_custom_emoji_id=EMOJI_REFRESH,
    )

    return InlineKeyboardMarkup(
        [
            [switch_btn, country_btn],
            [adguard_btn, ipv6_btn],
            [refresh_btn],
        ]
    )
