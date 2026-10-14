"""Unit tests for dynamic custom emoji loader and resolver."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegrambot.core.dynamic_emojis import (
    country_to_unicode_flag,
    fetch_sticker_set_emojis,
    format_country_badge,
    format_region_badge,
    get_country_emoji_id,
    get_region_emoji_id,
    load_cached_emojis,
)


class TestDynamicEmojis(unittest.TestCase):
    """Test dynamic emoji resolution and sticker set fetching."""

    def setUp(self):
        import telegrambot.core.dynamic_emojis as de

        self._orig_cache = dict(de._EMOJI_CACHE)
        self._orig_init = de._INITIALIZED
        de._INITIALIZED = False
        de._EMOJI_CACHE.clear()
        de.load_cached_emojis()

    def tearDown(self):
        import telegrambot.core.dynamic_emojis as de

        de._EMOJI_CACHE.clear()
        de._EMOJI_CACHE.update(self._orig_cache)
        de._INITIALIZED = self._orig_init

    def test_country_to_unicode_flag(self):
        self.assertEqual(country_to_unicode_flag("jp"), "🇯🇵")
        self.assertEqual(country_to_unicode_flag("us"), "🇺🇸")
        self.assertEqual(country_to_unicode_flag("uk-cv"), "🇬🇧")
        self.assertEqual(country_to_unicode_flag("uk-lon"), "🇬🇧")
        self.assertEqual(country_to_unicode_flag("lux"), "🇱🇺")
        self.assertEqual(country_to_unicode_flag("invalid-xxx"), "🌐")

    def test_get_country_emoji_id_cached(self):
        # We pre-loaded emoji_cache.json in telegrambot/data/
        load_cached_emojis()
        jp_id = get_country_emoji_id("jp")
        self.assertIsNotNone(jp_id)
        self.assertEqual(jp_id, "5456261908069885892")

        us_id = get_country_emoji_id("us")
        self.assertIsNotNone(us_id)

    def test_get_region_emoji_id_cached(self):
        asia_id = get_region_emoji_id("asia")
        self.assertIsNotNone(asia_id)
        self.assertEqual(asia_id, "5397753673130463064")

        europe_id = get_region_emoji_id("europe")
        self.assertIsNotNone(europe_id)
        self.assertEqual(europe_id, "5429403746696189687")

    def test_format_badges(self):
        c_badge = format_country_badge("jp")
        self.assertIn("tg-emoji", c_badge)
        self.assertIn("5456261908069885892", c_badge)

        r_badge = format_region_badge("asia", "Asia")
        self.assertIn("tg-emoji", r_badge)
        self.assertIn("5397753673130463064", r_badge)

    @patch("telegrambot.core.dynamic_emojis.save_cached_emojis")
    def test_fetch_sticker_set_emojis_mock(self, mock_save):
        mock_bot = MagicMock()
        mock_sticker1 = MagicMock()
        mock_sticker1.emoji = "🇯🇵"
        mock_sticker1.custom_emoji_id = 99998888
        mock_set = MagicMock()
        mock_set.stickers = [mock_sticker1]
        mock_bot.get_sticker_set = AsyncMock(return_value=mock_set)

        import asyncio

        res = asyncio.run(fetch_sticker_set_emojis(mock_bot, "RestrictedEmoji"))
        self.assertEqual(res.get("🇯🇵"), "99998888")
        mock_save.assert_called_once()

    def test_format_tg_emoji_fallback(self):
        from telegrambot.constants.emojis import format_tg_emoji

        # Normal case
        tag = format_tg_emoji("123456", "🐉")
        self.assertEqual(tag, '<tg-emoji emoji-id="123456">🐉</tg-emoji>')

        # Disabled case
        with patch.dict("os.environ", {"DISABLE_CUSTOM_EMOJIS": "1"}):
            self.assertEqual(format_tg_emoji("123456", "🐉"), "🐉")

        # Empty id case
        self.assertEqual(format_tg_emoji("", "🐉"), "🐉")

    def test_enrich_status_text_with_custom_emojis(self):
        from telegrambot.core.dynamic_emojis import (
            enrich_status_text_with_custom_emojis,
        )

        load_cached_emojis()
        sample = (
            "• Connected: <code>True</code> (⚡ VLESS [🇯🇵 JP] / <code>sing0</code>)"
        )
        enriched = enrich_status_text_with_custom_emojis(sample, "jp")
        self.assertIn("tg-emoji", enriched)
        self.assertIn("5456261908069885892", enriched)
        self.assertIn("JP", enriched)

        # Direct / none / empty should return unchanged
        self.assertEqual(
            enrich_status_text_with_custom_emojis(sample, "direct"), sample
        )
        self.assertEqual(enrich_status_text_with_custom_emojis("", "jp"), "")


if __name__ == "__main__":
    unittest.main()
