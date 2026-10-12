"""Exit country (VPN Unlimited detour) command and callback handlers."""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from telegrambot.constants.emojis import TG_EMOJI_GLOBE
from telegrambot.constants.profiles import get_bot_country_profiles
from telegrambot.core.config import check_authorization, logger
from telegrambot.core.dynamic_emojis import (
    format_country_badge,
    format_region_badge,
)
from telegrambot.core.runner import (
    get_current_unlimited_country,
    get_status_text,
    run_hotspot_command,
)
from telegrambot.ui.country_keyboards import (
    make_country_keyboard,
    make_region_keyboard,
)
from telegrambot.ui.status_keyboards import make_status_keyboard


def _get_current_display() -> str:
    """Format active exit country text."""
    profiles = get_bot_country_profiles()
    current_c = get_current_unlimited_country()
    if current_c in profiles:
        p = profiles[current_c]
        cname = p.get("country_name", current_c.upper())
        flag = p.get("flag", "🌐")
        badge = format_country_badge(current_c, fallback_flag=flag)
        return f"{badge} {cname} ({current_c.upper()})"
    elif current_c in ["direct", "off", "none"]:
        return "🌐 Direct VPS (No Detour)"
    return current_c.upper()


async def country_menu_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show region selection menu for switching exit country."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return

    profiles = get_bot_country_profiles()
    current_display = _get_current_display()
    reply_markup = make_region_keyboard()
    hdr = (
        f"<b>{TG_EMOJI_GLOBE} Select VPN Profile Region "
        f"({len(profiles)} Countries):</b>"
    )
    text = (
        f"{hdr}\n\n"
        f"Active Profile: <b>{current_display}</b>\n\n"
        f"Traffic detours through your VLESS Reality VPS first (bypassing DPI), "
        f"then exits through VPN profile in the selected country.\n\n"
        f"Choose a region below:"
    )
    if update.message:
        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )


async def country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle region selection and country button callbacks."""
    query = update.callback_query
    if query is None or query.data is None:
        return
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        try:
            await query.answer("Unauthorized", show_alert=True)
        except Exception:
            pass
        return

    data = query.data
    if data == "noop":
        try:
            await query.answer()
        except Exception:
            pass
        return

    profiles = get_bot_country_profiles()
    current_display = _get_current_display()

    if data == "menu_country":
        reply_markup = make_region_keyboard()
        hdr = (
            f"<b>{TG_EMOJI_GLOBE} Select VPN Profile Region "
            f"({len(profiles)} Countries):</b>"
        )
        text = (
            f"{hdr}\n\n"
            f"Active Profile: <b>{current_display}</b>\n\n"
            f"Traffic detours through your VLESS Reality VPS first (bypassing DPI), "
            f"then exits through VPN profile in the selected country.\n\n"
            f"Choose a region below:"
        )
        try:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
            await query.answer()
        except Exception:
            pass
        return

    if data.startswith("region_"):
        reg = data.replace("region_", "")
        region_titles = {
            "asia": "Asia & Mideast",
            "europe": "Europe",
            "americas": "Americas",
            "oceania-africa": "Oceania & Africa",
            "all": "All Countries",
        }
        raw_title = region_titles.get(reg, reg.capitalize())
        title = format_region_badge(reg, raw_title)
        reply_markup = make_country_keyboard(selected_region=reg)

        if reg != "all":
            filtered = {cc: p for cc, p in profiles.items() if p.get("region") == reg}
        else:
            filtered = profiles

        country_lines = []
        for cc, p in sorted(filtered.items()):
            flag = p.get("flag", "🌐")
            badge = format_country_badge(cc, fallback_flag=flag)
            cname = p.get("country_name", cc.upper())
            country_lines.append(f"• {badge} <b>{cc.upper()}</b> — {cname}")

        if len(country_lines) <= 25:
            dest_header = f"<b>Available Destinations ({len(country_lines)}):</b>"
            dest_body = "\n".join(country_lines)
        else:
            dest_header = f"<b>Available Destinations ({len(country_lines)}):</b>"
            dest_body = (
                "\n".join(country_lines[:25])
                + f"\n<i>... and {len(country_lines) - 25} more (use ◀️ ▶️ tabs)</i>"
            )

        text = (
            f"<b>{title}:</b>\n\n"
            f"Active Exit: <b>{current_display}</b>\n\n"
            f"{dest_header}\n"
            f"{dest_body}\n\n"
            f"Choose an exit country below:"
        )
        try:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
            await query.answer()
        except Exception:
            pass
        return

    country = data.replace("country_", "")
    profiles = get_bot_country_profiles()
    if country in profiles:
        p = profiles[country]
        flag = p.get("flag", "🌐")
        badge = format_country_badge(country, fallback_flag=flag)
        cname = p.get("country_name", country.upper())
        target_name = f"{badge} {cname} ({country.upper()})"
    elif country == "direct":
        target_name = "Direct VPS (No Detour)"
    else:
        target_name = country.upper()

    wait_msg = f"Switching exit country to {target_name}..."
    try:
        await query.answer(wait_msg)
    except Exception:
        pass

    try:
        await query.edit_message_text(f"⏳ <i>{wait_msg}</i>", parse_mode="HTML")
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    _, _, code = await loop.run_in_executor(
        None, run_hotspot_command, ["--unlimited-country", country]
    )
    await asyncio.sleep(2)
    status_text = await get_status_text()
    reply_markup = make_status_keyboard(status_text)

    try:
        if code == 0:
            await query.edit_message_text(
                text=f"<b>Switched VPN Profile to {target_name}!</b>\n\n{status_text}",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            fail_text = (
                f"⚠️ <b>Failed to switch to {target_name}</b>\n"
                f"<i>Server did not respond to handshake "
                f"(auto-reverted to Direct VLESS).</i>\n\n"
                f"{status_text}"
            )
            await query.edit_message_text(
                text=fail_text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"Could not edit message after country switch: {e}")


async def country_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /country command with country code argument."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return

    args = context.args if context.args else []
    if not args:
        await country_menu_command(update, context)
        return

    target = args[0].lower()
    loop = asyncio.get_running_loop()
    if update.message:
        await update.message.reply_text(
            f"⏳ <i>Switching exit country to {target.upper()}...</i>",
            parse_mode="HTML",
        )
    await loop.run_in_executor(
        None, run_hotspot_command, ["--unlimited-country", target]
    )
    await asyncio.sleep(2)
    status_text = await get_status_text()
    reply_markup = make_status_keyboard(status_text)
    if update.message:
        await update.message.reply_text(
            text=status_text, reply_markup=reply_markup, parse_mode="HTML"
        )
