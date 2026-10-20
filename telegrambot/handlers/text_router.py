"""Router for plain text messages without command slashes."""

import re
from telegram import Update
from telegram.ext import ContextTypes

from telegrambot.core.config import check_authorization
from telegrambot.handlers.adguard import adguard_command, adguard_menu_command
from telegrambot.handlers.common import help_command
from telegrambot.handlers.country import country_command, country_menu_command
from telegrambot.handlers.ipv6 import ipv6_command, ipv6_menu_command
from telegrambot.handlers.maintenance import (
    clients_command,
    fix_command,
    restart_command,
    restart_vpn_command,
)
from telegrambot.handlers.status import router_ap_command, status_command
from telegrambot.handlers.vpn import switch_menu_command, switch_vpn_command


async def handle_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain text commands (e.g. 'status' instead of '/status')."""
    if update.effective_user is None or not check_authorization(
        update.effective_user.id
    ):
        return
    if update.message is None or update.message.text is None:
        return

    raw_text = update.message.text.strip().lower()
    text = re.sub(r"^[^\w/]+", "", raw_text).strip()
    normalized = text.replace(" ", "_")

    if text in ["status", "stat"] or normalized == "status":
        await status_command(update, context)
    elif text in [
        "router",
        "router ap",
        "router_ap",
        "ap",
        "/router",
    ] or normalized in ["router", "router_ap", "ap"]:
        await router_ap_command(update, context)
    elif text in [
        "switch vpn",
        "switch_vpn",
        "switch",
        "vpn",
        "/vpn",
    ] or normalized in [
        "switch_vpn",
        "switch",
        "vpn",
    ]:
        await switch_menu_command(update, context)
    elif text.startswith("vpn ") or text.startswith("/vpn "):
        parts = text.split()
        if len(parts) > 1 and parts[1] in ["profile", "profiles"]:
            await country_menu_command(update, context)
        elif len(parts) > 1:
            context.args = [parts[1]]
            await switch_vpn_command(update, context)
        else:
            await switch_menu_command(update, context)
    elif text in ["adguard", "adguard home", "adguard_home"] or normalized in [
        "adguard",
        "adguard_home",
    ]:
        await adguard_menu_command(update, context)
    elif text.startswith("adguard") or text.startswith("/adguard"):
        parts = text.split()
        if len(parts) > 1 and parts[1] in [
            "on",
            "off",
            "enable",
            "disable",
            "restart",
            "status",
        ]:
            context.args = [parts[1]]
            await adguard_command(update, context)
        else:
            await adguard_menu_command(update, context)
    elif text in ["ipv6", "ipv6 mode", "ipv6_mode", "/ipv6"] or normalized in [
        "ipv6",
        "ipv6_mode",
    ]:
        await ipv6_menu_command(update, context)
    elif text.startswith("ipv6") or text.startswith("/ipv6"):
        parts = text.split()
        if len(parts) > 1 and parts[1] in ["drop", "reject", "off"]:
            context.args = [parts[1]]
            await ipv6_command(update, context)
        else:
            await ipv6_menu_command(update, context)
    elif text in ["restart"] or normalized == "restart":
        await restart_command(update, context)
    elif text in [
        "restart vpn",
        "restart_vpn",
        "vpn restart",
        "rotate ip",
        "rotate_ip",
        "rotate vpn",
        "reload",
        "reload vpn",
        "reload_vpn",
    ] or normalized in ["restart_vpn", "rotate_ip", "reload_vpn"]:
        await restart_vpn_command(update, context)
    elif text in [
        "fix",
        "auto fix",
        "autofix",
        "watchdog",
        "/watchdog",
    ] or normalized in ["fix", "watchdog"]:
        await fix_command(update, context)
    elif text in ["clients", "client"] or normalized == "clients":
        await clients_command(update, context)
    elif text in ["help"] or normalized == "help":
        await help_command(update, context)
    elif text in [
        "country",
        "countries",
        "region",
        "regions",
        "exit country",
        "exit_country",
        "profile",
        "profiles",
        "vpn profile",
        "vpn profiles",
        "vpn_profiles",
        "/country",
        "/countries",
        "/region",
        "/regions",
        "/profiles",
    ] or normalized in [
        "country",
        "countries",
        "region",
        "regions",
        "exit_country",
        "profile",
        "profiles",
        "vpn_profiles",
    ]:
        await country_menu_command(update, context)
    elif (
        text.startswith("country")
        or text.startswith("/country")
        or text.startswith("region")
        or text.startswith("/region")
    ):
        parts = text.split()
        if len(parts) > 1:
            context.args = [parts[1]]
            await country_command(update, context)
        else:
            await country_menu_command(update, context)
    elif (
        text.startswith("switch_vpn")
        or text.startswith("switch ")
        or text in ["switch", "switch_awg", "switch_tun"]
    ):
        parts = text.split()
        if len(parts) > 1:
            context.args = [parts[1]]
        elif text == "switch_awg":
            context.args = ["awg0"]
        elif text == "switch_tun":
            context.args = ["tun0"]
        elif text == "switch_wg":
            context.args = ["wg0"]
        else:
            context.args = ["auto"]
        await switch_vpn_command(update, context)
