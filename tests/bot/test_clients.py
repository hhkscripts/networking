"""Unit tests for Telegram Bot clients handler and inline keyboard."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegrambot.handlers.maintenance import (
    clients_command,
    refresh_clients_callback,
)
from telegrambot.ui.clients_keyboards import make_clients_keyboard


class TestTelegramBotClients(unittest.IsolatedAsyncioTestCase):
    def test_make_clients_keyboard(self):
        kb = make_clients_keyboard()
        buttons = kb.inline_keyboard[0]
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0].callback_data, "refresh_clients")
        self.assertEqual(buttons[1].callback_data, "refresh_status")

    @patch("telegrambot.handlers.maintenance.check_authorization", return_value=True)
    @patch(
        "telegrambot.handlers.maintenance.run_hotspot_command",
        return_value=("<b>CONNECTED CLIENTS (1)</b>", "", 0),
    )
    async def test_clients_command_success(self, mock_run, mock_auth):
        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await clients_command(update, context)

        mock_run.assert_called_with(["--clients", "--html"])
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("CONNECTED CLIENTS (1)", args[0])
        self.assertEqual(kwargs.get("parse_mode"), "HTML")
        self.assertIsNotNone(kwargs.get("reply_markup"))

    @patch("telegrambot.handlers.maintenance.check_authorization", return_value=True)
    @patch(
        "telegrambot.handlers.maintenance.run_hotspot_command",
        return_value=("<b>CONNECTED CLIENTS (2)</b>", "", 0),
    )
    async def test_refresh_clients_callback(self, mock_run, mock_auth):
        update = MagicMock()
        update.effective_user.id = 12345
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        context = MagicMock()

        await refresh_clients_callback(update, context)

        query.answer.assert_called_with("Refreshing clients...")
        mock_run.assert_called_with(["--clients", "--html"])
        query.edit_message_text.assert_called_once()
        _, kwargs = query.edit_message_text.call_args
        self.assertIn("CONNECTED CLIENTS (2)", kwargs["text"])
        self.assertEqual(kwargs.get("parse_mode"), "HTML")


if __name__ == "__main__":
    unittest.main()
