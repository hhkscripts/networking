"""Telegram Bot entry point for GoodWifi Hotspot Manager."""

import os
import sys

# Ensure telegrambot is resolvable whether run from root, subfolder, or Docker /app
_curr_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_curr_dir, ".."))
if os.path.basename(_curr_dir) == "telegrambot" and _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
elif "telegrambot" not in sys.modules and not os.path.exists(
    os.path.join(_curr_dir, "telegrambot")
):
    import types

    _pkg = types.ModuleType("telegrambot")
    _pkg.__path__ = [_curr_dir]
    sys.modules["telegrambot"] = _pkg
    if _curr_dir not in sys.path:
        sys.path.insert(0, _curr_dir)

# flake8: noqa: E402
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegrambot.core.config import BOT_TOKEN, logger
from telegrambot.core.dynamic_emojis import (
    fetch_sticker_set_emojis,
    load_cached_emojis,
)
from telegrambot.core.health import set_bot_ready, start_bot_health_server
from telegrambot.handlers.adguard import (
    adguard_callback,
    adguard_command,
)
from telegrambot.handlers.common import help_command, start
from telegrambot.handlers.country import (
    country_callback,
    country_command,
    country_menu_command,
)
from telegrambot.handlers.ipv6 import (
    ipv6_callback,
    ipv6_command,
)
from telegrambot.handlers.maintenance import (
    clients_command,
    fix_command,
    refresh_clients_callback,
    restart_command,
    restart_vpn_command,
)
from telegrambot.handlers.status import (
    refresh_callback,
    router_ap_callback,
    router_ap_command,
    status_command,
)
from telegrambot.handlers.text_router import handle_text_message
from telegrambot.handlers.vpn import (
    switch_menu_command,
    switch_vpn_callback,
    switch_vpn_command,
)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error(
        "Exception while handling update: %s", context.error, exc_info=context.error
    )


async def _post_init(app: Application) -> None:
    """Async startup hook to load dynamic emojis before handling updates."""
    try:
        await fetch_sticker_set_emojis(app.bot)
    except Exception as e:
        logger.warning(f"Could not load dynamic emojis on startup: {e}")


def create_application() -> Application:
    """Configure and build the telegram Application with all handlers."""
    load_cached_emojis()
    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("restart_vpn", restart_vpn_command))
    app.add_handler(CommandHandler("vpn", switch_menu_command))
    app.add_handler(CommandHandler("switch_vpn", switch_vpn_command))
    app.add_handler(CommandHandler("switch", switch_menu_command))
    app.add_handler(CommandHandler("country", country_command))
    app.add_handler(CommandHandler("countries", country_command))
    app.add_handler(CommandHandler("region", country_menu_command))
    app.add_handler(CommandHandler("regions", country_menu_command))
    app.add_handler(CommandHandler("fix", fix_command))
    app.add_handler(CommandHandler("clients", clients_command))
    app.add_handler(CommandHandler("router", router_ap_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ipv6", ipv6_command))
    app.add_handler(CommandHandler("adguard", adguard_command))

    # Callback query handlers
    switch_pattern = r"^(switch_.*|menu_switch|menu_vless|menu_awg|menu_ovpn)$"
    app.add_handler(CallbackQueryHandler(switch_vpn_callback, pattern=switch_pattern))
    app.add_handler(
        CallbackQueryHandler(
            country_callback, pattern=r"^(country_|menu_country|region_|noop$)"
        )
    )
    app.add_handler(CallbackQueryHandler(ipv6_callback, pattern="^(ipv6_|menu_ipv6)"))
    app.add_handler(
        CallbackQueryHandler(adguard_callback, pattern="^(adguard_|menu_adguard)")
    )
    app.add_handler(CallbackQueryHandler(refresh_callback, pattern="^refresh_status$"))
    app.add_handler(
        CallbackQueryHandler(refresh_clients_callback, pattern="^refresh_clients$")
    )
    app.add_handler(
        CallbackQueryHandler(
            router_ap_callback, pattern=r"^(menu_router_ap|ping_router)$"
        )
    )

    # Plain text message handler
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    # Global error handler
    app.add_error_handler(_error_handler)

    return app


def main() -> None:
    """Run the telegram bot service."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        sys.exit(1)

    health_server = start_bot_health_server()
    try:
        app = create_application()
        logger.info("Starting bot polling...")
        set_bot_ready(True)
        app.run_polling(drop_pending_updates=True)
    finally:
        set_bot_ready(False)
        health_server.shutdown()
        health_server.server_close()


if __name__ == "__main__":
    main()
