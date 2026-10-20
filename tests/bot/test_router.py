"""Unit tests for plain text command router."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegrambot.handlers.text_router import handle_text_message


class TestTelegramBotTextRouter(unittest.TestCase):
    """Test message routing for plain text inputs."""

    def setUp(self):
        self.update = MagicMock()
        self.update.effective_user.id = 12345
        self.context = MagicMock()
        self.context.args = []

    def _make_update(self, text: str):
        update = MagicMock()
        update.effective_user.id = 12345
        update.message.text = text
        return update

    @patch("telegrambot.handlers.text_router.check_authorization", return_value=True)
    @patch(
        "telegrambot.handlers.text_router.switch_menu_command", new_callable=AsyncMock
    )
    def test_routes_vpn_text_to_switch_menu(self, mock_switch, mock_auth):
        for text in ["vpn", "VPN", "Vpn", "/vpn", "switch vpn", "switch"]:
            mock_switch.reset_mock()
            update = self._make_update(text)
            import asyncio

            asyncio.run(handle_text_message(update, self.context))
            mock_switch.assert_called_once_with(update, self.context)

    @patch("telegrambot.handlers.text_router.check_authorization", return_value=True)
    @patch(
        "telegrambot.handlers.text_router.country_menu_command", new_callable=AsyncMock
    )
    def test_routes_country_text_to_country_menu(self, mock_country_menu, mock_auth):
        for text in [
            "country",
            "Country",
            "countries",
            "region",
            "Region",
            "regions",
            "VPN Profiles",
            "vpn profiles",
            "profiles",
        ]:
            mock_country_menu.reset_mock()
            update = self._make_update(text)
            import asyncio

            asyncio.run(handle_text_message(update, self.context))
            mock_country_menu.assert_called_once_with(update, self.context)

    @patch("telegrambot.handlers.text_router.check_authorization", return_value=True)
    @patch(
        "telegrambot.handlers.text_router.switch_vpn_command", new_callable=AsyncMock
    )
    def test_routes_vpn_arg_to_switch_vpn(self, mock_switch_vpn, mock_auth):
        update = self._make_update("vpn awg0")
        import asyncio

        asyncio.run(handle_text_message(update, self.context))
        mock_switch_vpn.assert_called_once_with(update, self.context)
        self.assertEqual(self.context.args, ["awg0"])

    @patch("telegrambot.handlers.text_router.check_authorization", return_value=True)
    @patch("telegrambot.handlers.text_router.country_command", new_callable=AsyncMock)
    def test_routes_country_arg_to_country_command(self, mock_country, mock_auth):
        update = self._make_update("country jp")
        import asyncio

        asyncio.run(handle_text_message(update, self.context))
        mock_country.assert_called_once_with(update, self.context)
        self.assertEqual(self.context.args, ["jp"])

    @patch("telegrambot.handlers.text_router.check_authorization", return_value=True)
    @patch("telegrambot.handlers.text_router.router_ap_command", new_callable=AsyncMock)
    def test_routes_router_text_to_router_ap_command(self, mock_router, mock_auth):
        for text in ["router", "Router", "router ap", "router_ap", "/router", "ap"]:
            mock_router.reset_mock()
            update = self._make_update(text)
            import asyncio

            asyncio.run(handle_text_message(update, self.context))
            mock_router.assert_called_once_with(update, self.context)


if __name__ == "__main__":
    unittest.main()
