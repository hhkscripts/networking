"""Maintenance and diagnostics command handlers (restart, fix, clients)."""

import asyncio
import html
from telegram import Update
from telegram.ext import ContextTypes

from telegrambot.constants.emojis import TG_EMOJI_AMNEZIAWG, TG_EMOJI_RPI
from telegrambot.core.config import check_authorization, logger
from telegrambot.core.runner import run_hotspot_command
from telegrambot.ui.clients_keyboards import make_clients_keyboard
from telegrambot.ui.main_keyboard import MAIN_KEYBOARD


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restart hotspot services."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return
    if update.message is None:
        return
    msg = await update.message.reply_text(
        f"{TG_EMOJI_RPI} <i>Restarting Hotspot...</i>",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="HTML",
    )
    loop = asyncio.get_running_loop()
    stdout, stderr, _ = await loop.run_in_executor(
        None, run_hotspot_command, ["--restart"]
    )
    response = (stdout if stdout else stderr).strip()
    if not response:
        response = "Hotspot services and VPN restarted."
    await asyncio.sleep(2)
    res_text = (
        f"<b>{TG_EMOJI_RPI} Restart Result:</b>\n<pre>{html.escape(response)}</pre>"
    )
    try:
        await msg.edit_text(res_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not edit restart message, sending new reply: {e}")
        try:
            await update.message.reply_text(
                res_text,
                reply_markup=MAIN_KEYBOARD,
                parse_mode="HTML",
            )
        except Exception as e2:
            logger.error(f"Failed to send restart reply: {e2}")


async def restart_vpn_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Restart active VPN connection."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return
    if update.message is None:
        return
    msg = await update.message.reply_text(
        f"{TG_EMOJI_AMNEZIAWG} <i>Restarting VPN connection...</i>",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="HTML",
    )
    loop = asyncio.get_running_loop()
    stdout, stderr, _ = await loop.run_in_executor(
        None, run_hotspot_command, ["--restart-vpn"]
    )
    response = (stdout if stdout else stderr).strip()
    if not response:
        response = "VPN connection restarted."
    await asyncio.sleep(2)
    res_text = (
        f"<b>{TG_EMOJI_AMNEZIAWG} Restart VPN Result:</b>\n"
        f"<pre>{html.escape(response)}</pre>"
    )
    try:
        await msg.edit_text(res_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not edit restart vpn message, sending new reply: {e}")
        try:
            await update.message.reply_text(
                res_text,
                reply_markup=MAIN_KEYBOARD,
                parse_mode="HTML",
            )
        except Exception as e2:
            logger.error(f"Failed to send restart vpn reply: {e2}")


async def fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run hotspot self-healing auto-fix."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return
    if update.message is None:
        return
    msg = await update.message.reply_text(
        "🔧 <i>Running auto-fix for hotspot and VPN...</i>",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="HTML",
    )
    loop = asyncio.get_running_loop()
    stdout, stderr, _ = await loop.run_in_executor(None, run_hotspot_command, ["--fix"])
    response = (stdout if stdout else stderr).strip()
    if not response:
        response = "Auto-fix completed."
    await asyncio.sleep(2)
    try:
        await msg.edit_text(
            f"<b>🔧 Fix Result:</b>\n<pre>{html.escape(response)}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not edit fix message, sending new reply: {e}")
        try:
            await update.message.reply_text(
                f"<b>🔧 Fix Result:</b>\n<pre>{html.escape(response)}</pre>",
                reply_markup=MAIN_KEYBOARD,
                parse_mode="HTML",
            )
        except Exception as e2:
            logger.error(f"Failed to send fix reply: {e2}")


async def clients_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List connected hotspot clients with detailed information."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return
    if update.message is None:
        return
    loop = asyncio.get_running_loop()
    stdout, stderr, _ = await loop.run_in_executor(
        None, run_hotspot_command, ["--clients", "--html"]
    )
    response = (stdout if stdout else stderr).strip()
    if not response:
        response = "<b>📱 Connected Clients: 0</b>\n<i>No connected devices.</i>"
    await update.message.reply_text(
        response, reply_markup=make_clients_keyboard(), parse_mode="HTML"
    )


async def refresh_clients_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline button click for refreshing connected clients."""
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
        await query.answer("Refreshing clients...")
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    stdout, stderr, _ = await loop.run_in_executor(
        None, run_hotspot_command, ["--clients", "--html"]
    )
    response = (stdout if stdout else stderr).strip()
    if not response:
        response = "<b>📱 Connected Clients: 0</b>\n<i>No connected devices.</i>"

    try:
        await query.edit_message_text(
            text=response,
            reply_markup=make_clients_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"Could not edit clients message: {e}")

