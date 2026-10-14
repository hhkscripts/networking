"""Unit tests for config state inspection and runner helpers."""

import unittest
from unittest.mock import mock_open, patch

from telegrambot.core.runner import (
    get_current_adguard_state,
    get_current_backend_name,
    get_current_ipv6_mode,
    get_current_unlimited_country,
)


class TestTelegramBotRunnerConfigParsers(unittest.TestCase):
    """Test reading configurations from goodwifi.conf."""

    def test_get_current_unlimited_country(self):
        with patch("os.path.exists", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data='UNLIMITED_COUNTRY="sg"\n'),
            ):
                res = get_current_unlimited_country()
                self.assertEqual(res, "sg")

    def test_get_current_ipv6_mode(self):
        with patch("os.path.exists", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data='IPV6_LEAK_PROTECTION="reject"\n'),
            ):
                res = get_current_ipv6_mode()
                self.assertEqual(res, "reject")

    def test_get_current_adguard_state(self):
        with patch("os.path.exists", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data='ADGUARD_ENABLED="false"\n'),
            ):
                res = get_current_adguard_state()
                self.assertFalse(res)

    def test_get_current_backend_name_explicit(self):
        with patch("os.path.exists", side_effect=lambda p: "goodwifi.conf" in p):
            with patch(
                "builtins.open",
                mock_open(read_data='VPN_BACKEND="awg0"\n'),
            ):
                res = get_current_backend_name()
                self.assertIn("AmneziaWG", res)

    def test_get_current_backend_name_auto_detected(self):
        def mock_exists(p):
            if "goodwifi.conf" in p:
                return True
            if "sing0" in p:
                return True
            return False

        with patch("os.path.exists", side_effect=mock_exists):
            with patch(
                "builtins.open",
                mock_open(read_data='VPN_BACKEND="auto"\nUNLIMITED_COUNTRY="jp"\n'),
            ):
                res = get_current_backend_name()
                self.assertIn("VLESS", res)
                self.assertIn("JP", res)

    def test_get_available_vpn_backends(self):
        from telegrambot.core.runner import get_available_vpn_backends

        def mock_exists(p):
            if "sing-box" in p:
                return True
            if "awg0.conf" in p:
                return True
            return False

        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.path.isdir", return_value=False):
                res = get_available_vpn_backends()
                self.assertTrue(res["sing0"])
                self.assertTrue(res["awg0"])
                self.assertFalse(res["wg0"])
                self.assertFalse(res["tun0"])

    def test_get_vless_servers(self):
        import json
        from telegrambot.core.runner import get_vless_servers

        fake_cfg = json.dumps(
            {
                "outbounds": [
                    {
                        "tag": "server-1",
                        "settings": {"vnext": [{"address": "203.0.113.1"}]},
                    },
                    {
                        "tag": "server-2",
                        "settings": {"vnext": [{"address": "198.51.100.2"}]},
                    },
                ]
            }
        )
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=fake_cfg)):
                servers = get_vless_servers()
                self.assertEqual(len(servers), 2)
                self.assertEqual(servers[0][0], "1")
                self.assertIn("203.0", servers[0][1])
                self.assertEqual(servers[1][0], "2")
                self.assertIn("198.51", servers[1][1])

    def test_get_amnezia_profiles(self):
        from telegrambot.core.runner import get_amnezia_profiles

        with patch("os.path.isdir", return_value=True):
            with patch("os.listdir", return_value=["awg0.conf", "awg1.conf"]):
                profs = get_amnezia_profiles()
                self.assertEqual(len(profs), 2)
                self.assertEqual(profs[0][0], "awg0")
                self.assertEqual(profs[1][0], "awg1")

    def test_get_openvpn_profiles(self):
        from telegrambot.core.runner import get_openvpn_profiles

        with patch("os.path.isdir", return_value=True):
            with patch("os.listdir", return_value=["client1.ovpn", "client2.conf"]):
                profs = get_openvpn_profiles()
                self.assertEqual(len(profs), 2)
                self.assertEqual(profs[0][0], "client1")
                self.assertEqual(profs[1][0], "client2")


class TestTelegramBotStatusHandler(unittest.TestCase):
    """Test status_command handler behavior."""

    @patch("telegrambot.handlers.status.check_authorization", return_value=True)
    @patch("telegrambot.handlers.status.get_status_text")
    def test_status_command_sends_single_bubble(self, mock_status_text, mock_auth):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from telegrambot.handlers.status import status_command

        mock_status_text.return_value = (
            "<b>🍓 GoodWifi Hotspot Manager</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>📊 HOTSPOT STATUS</b>"
        )

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {}

        asyncio.run(status_command(update, context))

        # Must be called once (no extra greeting bubble)
        self.assertEqual(update.message.reply_text.call_count, 1)
        call_kwargs = update.message.reply_text.call_args.kwargs
        self.assertIn("GoodWifi Hotspot Manager", call_kwargs["text"])
        self.assertEqual(call_kwargs["parse_mode"], "HTML")
        self.assertIsNotNone(call_kwargs.get("reply_markup"))


if __name__ == "__main__":
    unittest.main()
