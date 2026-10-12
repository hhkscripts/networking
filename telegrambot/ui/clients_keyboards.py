"""Connected clients inline keyboard builder."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegrambot.constants.emojis import EMOJI_REFRESH, EMOJI_STATS


def make_clients_keyboard() -> InlineKeyboardMarkup:
    """Build the inline keyboard displayed under the clients output."""
    refresh_btn = InlineKeyboardButton(
        "Refresh Clients",
        callback_data="refresh_clients",
        icon_custom_emoji_id=EMOJI_REFRESH,
    )
    status_btn = InlineKeyboardButton(
        "Hotspot Status",
        callback_data="refresh_status",
        icon_custom_emoji_id=EMOJI_STATS,
    )
    return InlineKeyboardMarkup([[refresh_btn, status_btn]])
