"""Backward-compatible test runner for modular telegram bot tests."""

import unittest

from tests.bot.test_app import TestTelegramBotAppCreation
from tests.bot.test_clients import TestTelegramBotClients
from tests.bot.test_config import TestTelegramBotConfig
from tests.bot.test_dynamic_emojis import TestDynamicEmojis
from tests.bot.test_health import TestTelegramBotHealthServer
from tests.bot.test_router import TestTelegramBotTextRouter
from tests.bot.test_runner import (
    TestTelegramBotRunnerConfigParsers,
    TestTelegramBotStatusHandler,
)
from tests.bot.test_ui import TestTelegramBotUI

__all__ = [
    "TestTelegramBotConfig",
    "TestTelegramBotUI",
    "TestTelegramBotClients",
    "TestTelegramBotRunnerConfigParsers",
    "TestTelegramBotStatusHandler",
    "TestTelegramBotHealthServer",
    "TestTelegramBotAppCreation",
    "TestTelegramBotTextRouter",
    "TestDynamicEmojis",
]

if __name__ == "__main__":
    unittest.main()
