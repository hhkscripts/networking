"""Unit tests for bot keyboards and UI builders."""

import unittest

from telegrambot.ui.adguard_keyboards import make_adguard_keyboard
from telegrambot.ui.country_keyboards import (
    make_country_keyboard,
    make_region_keyboard,
)
from telegrambot.ui.ipv6_keyboards import make_ipv6_keyboard
from telegrambot.ui.main_keyboard import MAIN_KEYBOARD
from telegrambot.ui.status_keyboards import make_status_keyboard
from telegrambot.ui.vpn_keyboards import make_switch_vpn_keyboard


class TestTelegramBotUI(unittest.TestCase):
    """Test inline and reply keyboard constructors."""

    def test_main_keyboard_structure(self):
        self.assertIsNotNone(MAIN_KEYBOARD)
        button_texts = [btn.text for row in MAIN_KEYBOARD.keyboard for btn in row]
        self.assertIn("Status", button_texts)
        self.assertIn("Clients", button_texts)
        self.assertIn("Restart", button_texts)
        self.assertIn("Restart VPN", button_texts)
        self.assertIn("Fix", button_texts)
        self.assertIn("Switch VPN", button_texts)
        self.assertIn("IPv6 Mode", button_texts)
        self.assertIn("AdGuard", button_texts)
        self.assertIn("Country", button_texts)
        self.assertIn("Help", button_texts)

    def test_status_keyboard_structure(self):
        kb = make_status_keyboard("Connected to sing0 (VLESS Reality)")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertIn("menu_switch", callbacks)
        self.assertIn("menu_country", callbacks)
        self.assertIn("menu_adguard", callbacks)
        self.assertIn("menu_ipv6", callbacks)
        self.assertIn("refresh_status", callbacks)

    def test_switch_vpn_keyboard(self):
        # Test full available backends
        kb_all = make_switch_vpn_keyboard(
            available={"sing0": True, "awg0": True, "tun0": True, "wg0": True},
            vless_servers=[("1", "VLESS S1"), ("2", "VLESS S2")],
        )
        callbacks_all = [
            btn.callback_data for row in kb_all.inline_keyboard for btn in row
        ]
        self.assertIn("switch_reality_1", callbacks_all)
        self.assertIn("switch_reality_2", callbacks_all)
        self.assertIn("switch_awg0", callbacks_all)
        self.assertIn("switch_tun0", callbacks_all)
        self.assertIn("switch_wg0", callbacks_all)
        self.assertIn("menu_country", callbacks_all)
        self.assertIn("switch_auto", callbacks_all)
        self.assertIn("refresh_status", callbacks_all)

        # Test standard setup (sing0 with 2 servers, awg0, tun0, no wg0)
        kb_std = make_switch_vpn_keyboard(
            available={"sing0": True, "awg0": True, "tun0": True, "wg0": False},
            vless_servers=[("1", "VLESS S1"), ("2", "VLESS S2")],
        )
        self.assertEqual(len(kb_std.inline_keyboard[0]), 2)  # VLESS S1 & S2
        self.assertEqual(len(kb_std.inline_keyboard[1]), 2)  # AmneziaWG & OpenVPN
        self.assertEqual(len(kb_std.inline_keyboard[2]), 2)  # Exit Country & Auto
        self.assertEqual(len(kb_std.inline_keyboard[3]), 1)  # Back to Status

        # Test partial available backends (e.g. only awg0)
        kb_awg_only = make_switch_vpn_keyboard(
            available={"sing0": False, "awg0": True, "tun0": False, "wg0": False}
        )
        callbacks_awg = [
            btn.callback_data for row in kb_awg_only.inline_keyboard for btn in row
        ]
        self.assertIn("switch_awg0", callbacks_awg)
        self.assertNotIn("switch_reality_1", callbacks_awg)
        self.assertNotIn("switch_tun0", callbacks_awg)
        self.assertNotIn("switch_wg0", callbacks_awg)
        self.assertNotIn("menu_country", callbacks_awg)
        self.assertIn("switch_auto", callbacks_awg)
        self.assertIn("refresh_status", callbacks_awg)
        self.assertEqual(len(kb_awg_only.inline_keyboard[0]), 2)  # awg0 + auto
        self.assertEqual(len(kb_awg_only.inline_keyboard[1]), 1)  # Back to status

    def test_adguard_keyboard_toggle(self):
        kb_on = make_adguard_keyboard(adguard_on=True)
        callbacks_on = [
            btn.callback_data for row in kb_on.inline_keyboard for btn in row
        ]
        self.assertIn("adguard_off", callbacks_on)

        kb_off = make_adguard_keyboard(adguard_on=False)
        callbacks_off = [
            btn.callback_data for row in kb_off.inline_keyboard for btn in row
        ]
        self.assertIn("adguard_on", callbacks_off)

    def test_ipv6_keyboard(self):
        kb = make_ipv6_keyboard()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertIn("ipv6_drop", callbacks)
        self.assertIn("ipv6_reject", callbacks)
        self.assertIn("ipv6_off", callbacks)

    def test_region_and_country_keyboards(self):
        reg_kb = make_region_keyboard()
        reg_callbacks = [
            btn.callback_data for row in reg_kb.inline_keyboard for btn in row
        ]
        self.assertIn("region_asia", reg_callbacks)
        self.assertIn("country_direct", reg_callbacks)
        self.assertIn("refresh_status", reg_callbacks)

        country_kb = make_country_keyboard("asia")
        self.assertIsNotNone(country_kb)
        country_callbacks = [
            btn.callback_data for row in country_kb.inline_keyboard for btn in row
        ]
        self.assertIn("region_all", country_callbacks)
        self.assertIn("region_europe", country_callbacks)
        self.assertIn("noop", country_callbacks)
        self.assertIn("country_direct", country_callbacks)
        self.assertIn("menu_country", country_callbacks)


if __name__ == "__main__":
    unittest.main()
