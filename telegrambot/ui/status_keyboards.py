"""Status menu inline keyboard builder."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegrambot.constants.emojis import (
    EMOJI_ADGUARD,
    EMOJI_CLIENTS,
    EMOJI_GLOBE,
    EMOJI_IPV6,
    EMOJI_REFRESH,
    EMOJI_STATS,
    EMOJI_TOOLS,
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
    clients_btn = InlineKeyboardButton(
        "Clients",
        callback_data="refresh_clients",
        icon_custom_emoji_id=EMOJI_CLIENTS,
    )
    refresh_btn = InlineKeyboardButton(
        "Refresh Status",
        callback_data="refresh_status",
        icon_custom_emoji_id=EMOJI_REFRESH,
    )

    rows = [
        [switch_btn, country_btn],
        [adguard_btn, ipv6_btn],
    ]
    if "Router AP" in status_text:
        router_btn = InlineKeyboardButton(
            "Router AP",
            callback_data="menu_router_ap",
            icon_custom_emoji_id=EMOJI_STATS,
        )
        rows.append([clients_btn, router_btn])
    else:
        rows.append([clients_btn])
    rows.append([refresh_btn])

    return InlineKeyboardMarkup(rows)


def make_router_ap_keyboard() -> InlineKeyboardMarkup:
    """Build the inline keyboard for the Router AP sub-menu."""
    ping_btn = InlineKeyboardButton(
        "Ping Router (10.43.0.2)",
        callback_data="ping_router",
        icon_custom_emoji_id=EMOJI_TOOLS,
    )
    clients_btn = InlineKeyboardButton(
        "Clients",
        callback_data="refresh_clients",
        icon_custom_emoji_id=EMOJI_CLIENTS,
    )
    status_btn = InlineKeyboardButton(
        "Hotspot Status",
        callback_data="refresh_status",
        icon_custom_emoji_id=EMOJI_STATS,
    )
    return InlineKeyboardMarkup(
        [
            [ping_btn],
            [clients_btn, status_btn],
        ]
    )
