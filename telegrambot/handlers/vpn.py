"""VPN backend switching command and callback handlers."""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from telegrambot.constants.emojis import (
    TG_EMOJI_AMNEZIAWG,
    TG_EMOJI_OPENVPN,
    TG_EMOJI_VLESS,
    TG_EMOJI_WIREGUARD,
)
from telegrambot.core.config import check_authorization, logger
from telegrambot.core.runner import (
    get_amnezia_profiles,
    get_current_backend_name,
    get_openvpn_profiles,
    get_status_text,
    get_vless_servers,
    run_hotspot_command,
)
from telegrambot.ui.status_keyboards import make_status_keyboard
from telegrambot.ui.vpn_keyboards import (
    make_amnezia_keyboard,
    make_openvpn_keyboard,
    make_switch_vpn_keyboard,
    make_vless_keyboard,
)


async def switch_menu_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show the VPN backend selection menu."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return

    current = get_current_backend_name()
    reply_markup = make_switch_vpn_keyboard()
    text = (
        f"<b>Select VPN Backend:</b>\n\n"
        f"Active: {current}\n\n"
        f"Choose an option below to switch:"
    )
    if update.message:
        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )


async def switch_vpn_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle VPN backend switch button callbacks."""
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
    if data == "menu_switch":
        current = get_current_backend_name()
        text = (
            f"<b>Select VPN Backend:</b>\n\n"
            f"Active: {current}\n\n"
            f"Choose an option below to switch:"
        )
        try:
            await query.edit_message_text(
                text, reply_markup=make_switch_vpn_keyboard(), parse_mode="HTML"
            )
            await query.answer()
        except Exception:
            pass
        return

    if data == "menu_vless":
        current = get_current_backend_name()
        vless_servers = get_vless_servers()
        count = len(vless_servers)
        text = (
            f"<b>{TG_EMOJI_VLESS} VLESS Reality Servers:</b>\n\n"
            f"Active: {current}\n\n"
            f"Select a server below ({count} available):"
        )
        try:
            await query.edit_message_text(
                text,
                reply_markup=make_vless_keyboard(vless_servers),
                parse_mode="HTML",
            )
            await query.answer()
        except Exception:
            pass
        return

    if data == "menu_awg":
        current = get_current_backend_name()
        profiles = get_amnezia_profiles()
        count = len(profiles)
        text = (
            f"<b>{TG_EMOJI_AMNEZIAWG} AmneziaWG Profiles:</b>\n\n"
            f"Active: {current}\n\n"
            f"Select an AmneziaWG profile below ({count} available):"
        )
        try:
            await query.edit_message_text(
                text,
                reply_markup=make_amnezia_keyboard(profiles),
                parse_mode="HTML",
            )
            await query.answer()
        except Exception:
            pass
        return

    if data == "menu_ovpn":
        current = get_current_backend_name()
        profiles = get_openvpn_profiles()
        count = len(profiles)
        text = (
            f"<b>{TG_EMOJI_OPENVPN} OpenVPN Profiles:</b>\n\n"
            f"Active: {current}\n\n"
            f"Select an OpenVPN profile below ({count} available):"
        )
        try:
            await query.edit_message_text(
                text,
                reply_markup=make_openvpn_keyboard(profiles),
                parse_mode="HTML",
            )
            await query.answer()
        except Exception:
            pass
        return

    loop = asyncio.get_running_loop()

    if data.startswith("switch_reality_"):
        server_num = data.replace("switch_reality_", "")
        server_ip = "198.71.50.129" if server_num == "1" else "5.183.9.86"
        target_name = f"{TG_EMOJI_VLESS} VLESS Server {server_num} ({server_ip})"
        try:
            await query.answer(f"Switching to VLESS Server {server_num}...")
        except Exception:
            pass

        await loop.run_in_executor(None, run_hotspot_command, ["--switch-vpn", "sing0"])
        _, _, code = await loop.run_in_executor(
            None, run_hotspot_command, ["--reality-server", server_num]
        )
    else:
        target = data.replace("switch_", "")
        ovpn_profs = [p[0] for p in get_openvpn_profiles()]
        awg_profs = [p[0] for p in get_amnezia_profiles()]
        backend_target = target
        if target in ovpn_profs or target.startswith("tun"):
            backend_target = "tun0"
        elif target in awg_profs or target.startswith("awg"):
            backend_target = "awg0"

        names = {
            "sing0": f"{TG_EMOJI_VLESS} VLESS (sing0)",
            "awg0": f"{TG_EMOJI_AMNEZIAWG} AmneziaWG (awg0)",
            "tun0": f"{TG_EMOJI_OPENVPN} OpenVPN (tun0)",
            "wg0": f"{TG_EMOJI_WIREGUARD} WireGuard (wg0)",
            "auto": "Auto",
        }
        target_name = names.get(backend_target, target)
        try:
            await query.answer(f"Switching to {target_name}...")
        except Exception:
            pass

        _, _, code = await loop.run_in_executor(
            None, run_hotspot_command, ["--switch-vpn", backend_target]
        )
    await asyncio.sleep(2)
    status_text = await get_status_text()
    reply_markup = make_status_keyboard(status_text)

    try:
        if code == 0:
            await query.edit_message_text(
                text=f"<b>Switched to {target_name}!</b>\n\n{status_text}",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            fail_text = (
                f"⚠️ <b>Failed to switch to {target_name}</b> "
                f"(reverted to active backend)\n\n{status_text}"
            )
            await query.edit_message_text(
                text=fail_text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"Could not edit message after switch: {e}")


async def switch_vpn_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /switch_vpn command with text argument."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return

    target = context.args[0].lower() if context.args else "auto"
    if target not in ["sing0", "awg0", "tun0", "auto", "wg0"]:
        if update.message:
            await update.message.reply_text(
                "Usage: <code>/switch_vpn &lt;sing0|awg0|tun0|wg0|auto&gt;</code>",
                parse_mode="HTML",
            )
        return

    target_names = {
        "sing0": f"{TG_EMOJI_VLESS} VLESS Reality (sing0)",
        "awg0": f"{TG_EMOJI_AMNEZIAWG} AmneziaWG (awg0)",
        "tun0": f"{TG_EMOJI_OPENVPN} OpenVPN (tun0)",
        "wg0": f"{TG_EMOJI_WIREGUARD} WireGuard (wg0)",
        "auto": "Auto",
    }
    target_display = target_names.get(target, target)

    if update.message:
        await update.message.reply_text(
            f"Switching VPN backend to <b>{target_display}</b>...", parse_mode="HTML"
        )

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, run_hotspot_command, ["--switch-vpn", target])
    await asyncio.sleep(2)
    status_text = await get_status_text()
    reply_markup = make_status_keyboard(status_text)

    if update.message:
        await update.message.reply_text(
            text=status_text, reply_markup=reply_markup, parse_mode="HTML"
        )
