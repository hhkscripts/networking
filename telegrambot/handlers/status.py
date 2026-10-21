"""Status command and refresh callback query handlers."""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from telegrambot.core.config import check_authorization, logger
from telegrambot.core.runner import get_status_text, ping_router_ap
from telegrambot.ui.status_keyboards import (
    make_router_ap_keyboard,
    make_status_keyboard,
)

ROUTER_AP_INFO_HTML = (
    "<b>📶 Router Access Point (TP-Link TL-WR941ND)</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "• <b>Hardware:</b> TP-Link TL-WR941ND Ver 5.1\n"
    "• <b>Mode:</b> Layer 2 Wireless AP (Wi-Fi 4 N450)\n"
    "• <b>Interface:</b> <code>eth1</code> (Gigabit Ethernet)\n"
    "• <b>Subnet:</b> <code>10.43.0.0/24</code>\n"
    "• <b>Gateway & DNS:</b> <code>10.43.0.1</code> (Raspberry Pi 5)\n"
    "• <b>Router Admin IP:</b> <code>10.43.0.2</code>\n"
    '• <b>Web Dashboard:</b> <a href="http://10.43.0.2">http://10.43.0.2</a>\n'
    '• <b>From Router 1:</b> <a href="http://192.168.100.2">http://192.168.100.2</a>\n'
    "• <b>Security:</b> Fail-Closed VPN + AdGuard DNS"
)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command and show hotspot status with inline keyboard."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return

    status_text = await get_status_text()
    reply_markup = make_status_keyboard(status_text)

    if update.message is not None:
        await update.message.reply_text(
            text=status_text, reply_markup=reply_markup, parse_mode="HTML"
        )


async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button click for refreshing status."""
    query = update.callback_query
    if query is None:
        return
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        try:
            await query.answer("Unauthorized", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer("Refreshing...")
    except Exception:
        pass

    status_text = await get_status_text()
    reply_markup = make_status_keyboard(status_text)

    try:
        await query.edit_message_text(
            text=status_text, reply_markup=reply_markup, parse_mode="HTML"
        )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"Could not edit message: {e}")


async def router_ap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /router command and show Router AP info."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return
    if update.message is not None:
        await update.message.reply_text(
            text=ROUTER_AP_INFO_HTML,
            reply_markup=make_router_ap_keyboard(),
            parse_mode="HTML",
        )


async def router_ap_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline button clicks for router AP sub-menu."""
    query = update.callback_query
    if query is None:
        return
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        try:
            await query.answer("Unauthorized", show_alert=True)
        except Exception:
            pass
        return

    data = query.data or ""
    if data == "ping_router":
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, ping_router_ap, "10.43.0.2")
        try:
            await query.answer(f"🏓 {res}", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer()
    except Exception:
        pass
    try:
        await query.edit_message_text(
            text=ROUTER_AP_INFO_HTML,
            reply_markup=make_router_ap_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"Could not edit router ap message: {e}")
