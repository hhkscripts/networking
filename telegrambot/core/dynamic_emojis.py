"""Dynamic Telegram Premium custom emoji loader and resolver."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("goodwifi-bot")

_EMOJI_CACHE: Dict[str, str] = {}
_INITIALIZED: bool = False

COUNTRY_ISO_ALIASES: Dict[str, str] = {
    "uk": "gb",
    "lux": "lu",
}

REGION_EMOJIS: Dict[str, str] = {
    "asia": "🌏",
    "europe": "🏰",
    "americas": "🌎",
    "oceania-africa": "🌍",
    "all": "📋",
    "direct": "🌐",
}

_CACHE_LOCATIONS = [
    Path(__file__).parent.parent / "data" / "emoji_cache.json",
    Path("/var/run/goodwifi/emoji_cache.json"),
    Path("/tmp/goodwifi_emoji_cache.json"),
    Path("/host/var/run/goodwifi/emoji_cache.json"),
    Path("/host/tmp/goodwifi_emoji_cache.json"),
]


def load_cached_emojis() -> Dict[str, str]:
    """Load cached custom emoji IDs from disk if available."""
    global _INITIALIZED
    if _INITIALIZED and _EMOJI_CACHE:
        return _EMOJI_CACHE

    for loc in _CACHE_LOCATIONS:
        if loc.exists():
            try:
                with open(loc, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        _EMOJI_CACHE.update(data)
                        _INITIALIZED = True
                        logger.info(
                            "Loaded %d dynamic custom emojis from %s",
                            len(_EMOJI_CACHE),
                            loc,
                        )
                        return _EMOJI_CACHE
            except Exception as e:
                logger.warning("Could not read emoji cache from %s: %s", loc, e)

    return _EMOJI_CACHE


def save_cached_emojis(data: Dict[str, str]) -> None:
    """Save resolved custom emoji mapping to local cache files."""
    saved = False
    for loc in _CACHE_LOCATIONS:
        try:
            loc.parent.mkdir(parents=True, exist_ok=True)
            with open(loc, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info("Saved %d emojis to %s", len(data), loc)
            saved = True
        except Exception:
            continue
    if not saved:
        logger.warning("Could not save emoji cache to any location.")


async def fetch_sticker_set_emojis(
    bot, pack_name: Optional[str] = None
) -> Dict[str, str]:
    """Fetch custom emoji sticker set from Telegram API and update cache."""
    global _INITIALIZED
    pack = pack_name or os.getenv("TELEGRAM_EMOJI_PACK", "RestrictedEmoji")
    try:
        sticker_set = await bot.get_sticker_set(pack)
        if sticker_set and sticker_set.stickers:
            mapping: Dict[str, str] = {}
            for st in sticker_set.stickers:
                if st.emoji and st.custom_emoji_id:
                    mapping[st.emoji] = str(st.custom_emoji_id)

            _EMOJI_CACHE.update(mapping)
            _INITIALIZED = True
            logger.info(
                "Successfully fetched %d custom emojis from Telegram pack '%s'",
                len(mapping),
                pack,
            )
            save_cached_emojis(_EMOJI_CACHE)
            return _EMOJI_CACHE
    except Exception as e:
        logger.warning(
            "Could not fetch custom emoji pack '%s' from Telegram: %s", pack, e
        )

    # Fallback to local cache if network fetch failed
    return load_cached_emojis()


def country_to_unicode_flag(country_code: str) -> str:
    """Convert a country code (e.g. 'jp', 'uk-cv') to its Unicode flag."""
    code = country_code.split("-")[0].lower()
    iso = COUNTRY_ISO_ALIASES.get(code, code).upper()
    if len(iso) == 2 and all("A" <= c <= "Z" for c in iso):
        return "".join(chr(127397 + ord(c)) for c in iso)
    return "🌐"


def get_country_emoji_id(country_code: str) -> Optional[str]:
    """Return custom emoji ID for a country flag."""
    load_cached_emojis()
    flag = country_to_unicode_flag(country_code)
    return _EMOJI_CACHE.get(flag)


def get_region_emoji_id(region_key: str) -> Optional[str]:
    """Return custom emoji ID for a region/continent."""
    load_cached_emojis()
    symbol = REGION_EMOJIS.get(region_key.lower())
    if symbol:
        return _EMOJI_CACHE.get(symbol)
    return None


def format_country_badge(country_code: str, fallback_flag: Optional[str] = None) -> str:
    """Return HTML formatted custom emoji badge or unicode flag."""
    flag = fallback_flag or country_to_unicode_flag(country_code)
    emoji_id = get_country_emoji_id(country_code)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{flag}</tg-emoji>'
    return flag


def format_region_badge(region_key: str, label: str) -> str:
    """Return HTML formatted region header badge with custom emoji."""
    symbol = REGION_EMOJIS.get(region_key.lower(), "🌐")
    emoji_id = get_region_emoji_id(region_key)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{symbol}</tg-emoji> {label}'
    return f"{symbol} {label}"


def enrich_status_text_with_custom_emojis(
    text: str, country_code: Optional[str] = None
) -> str:
    """Enrich status text by replacing plain Unicode country flags with custom
    emoji badges."""
    if not text:
        return text
    if not country_code or country_code.lower() in ["direct", "off", "none"]:
        return text

    code = country_code.lower()
    flag = country_to_unicode_flag(code)
    badge = format_country_badge(code, fallback_flag=flag)
    if badge == flag:
        return text

    upper_code = code.upper()
    text = text.replace(f"[{flag} {upper_code}]", f"[{badge} {upper_code}]")
    base_iso = code.split("-")[0].upper()
    if base_iso != upper_code:
        text = text.replace(f"[{flag} {base_iso}]", f"[{badge} {base_iso}]")

    return text
