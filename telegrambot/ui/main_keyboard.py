"""Main persistent reply keyboard with custom emojis."""

from telegram import KeyboardButton, ReplyKeyboardMarkup

from telegrambot.constants.emojis import (
    EMOJI_ADGUARD,
    EMOJI_AMNEZIAWG,
    EMOJI_CLIENTS,
    EMOJI_GLOBE,
    EMOJI_HELP,
    EMOJI_IPV6,
    EMOJI_RPI,
    EMOJI_STATS,
    EMOJI_TOOLS,
    EMOJI_WIREGUARD,
)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("Status", icon_custom_emoji_id=EMOJI_STATS),
            KeyboardButton("Clients", icon_custom_emoji_id=EMOJI_CLIENTS),
        ],
        [
            KeyboardButton("Restart", icon_custom_emoji_id=EMOJI_RPI),
            KeyboardButton("Restart VPN", icon_custom_emoji_id=EMOJI_AMNEZIAWG),
        ],
        [
            KeyboardButton("Fix", icon_custom_emoji_id=EMOJI_TOOLS),
            KeyboardButton("Switch VPN", icon_custom_emoji_id=EMOJI_WIREGUARD),
        ],
        [
            KeyboardButton("IPv6 Mode", icon_custom_emoji_id=EMOJI_IPV6),
            KeyboardButton("AdGuard", icon_custom_emoji_id=EMOJI_ADGUARD),
        ],
        [
            KeyboardButton("VPN Profiles", icon_custom_emoji_id=EMOJI_GLOBE),
            KeyboardButton("Help", icon_custom_emoji_id=EMOJI_HELP),
        ],
    ],
    resize_keyboard=True,
    is_persistent=False,
)
