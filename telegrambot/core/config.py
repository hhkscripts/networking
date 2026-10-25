"""Configuration settings and authorization logic."""

import os
import logging
from typing import List

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
logger = logging.getLogger("telegrambot")

# Environment variables
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS: str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
ALLOWED_USER_IDS: List[int] = (
    [int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip().isdigit()]
    if ALLOWED_USERS
    else []
)

BOT_HEALTH_HOST: str = os.getenv("BOT_HEALTH_HOST", "0.0.0.0")
BOT_HEALTH_PORT: int = int(os.getenv("BOT_HEALTH_PORT", "8081"))
BOT_SERVICE_NAME: str = os.getenv("BOT_SERVICE_NAME", "mpxraspberrypibot")
ALLOW_ALL_USERS: bool = os.getenv("TELEGRAM_ALLOW_ALL_USERS", "false").lower() in (
    "true",
    "1",
)


def check_authorization(user_id: int) -> bool:
    """Check if the user is authorized to interact with the bot.

    Enforces default-deny for security unless ALLOWED_USER_IDS contains the user
    or TELEGRAM_ALLOW_ALL_USERS=true is explicitly enabled.
    """
    if ALLOWED_USER_IDS:
        return user_id in ALLOWED_USER_IDS
    return ALLOW_ALL_USERS
