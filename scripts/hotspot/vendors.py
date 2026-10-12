#!/usr/bin/env python3
"""
MAC OUI vendor mapping, device type detection, and formatting helpers.
"""

VENDOR_PREFIXES: dict[str, tuple[str, ...]] = {
    "Apple": (
        "00:03:93",
        "00:05:02",
        "00:0a:95",
        "00:0d:93",
        "00:10:fa",
        "00:14:51",
        "00:16:cb",
        "00:17:f2",
        "00:19:e3",
        "00:1b:63",
        "00:1c:b3",
        "00:1e:52",
        "00:1f:5b",
        "00:1f:f3",
        "00:23:12",
        "00:25:00",
        "00:26:08",
        "00:26:b0",
        "04:0c:ce",
        "04:15:52",
        "04:48:9a",
        "04:54:53",
        "08:66:98",
        "0c:74:c2",
        "10:94:bb",
        "14:7d:c5",
        "20:ee:28",
        "28:0b:5c",
        "34:08:bc",
        "34:12:98",
        "38:ca:da",
        "3c:07:54",
        "40:6c:8f",
        "58:55:ca",
        "60:03:08",
        "64:a5:c3",
        "70:ec:e4",
        "7c:04:d0",
        "80:e6:50",
        "88:66:5a",
        "8c:85:90",
        "90:b9:31",
        "98:10:e8",
        "a4:83:e7",
        "ac:bc:32",
        "b8:78:26",
        "bc:9f:ef",
        "c8:2a:14",
        "d0:23:db",
        "d8:96:95",
        "e0:b9:ba",
        "f0:18:98",
        "f8:ff:c2",
    ),
    "Samsung": (
        "00:07:ab",
        "00:12:47",
        "00:15:99",
        "00:16:32",
        "00:1a:8a",
        "00:21:19",
        "00:23:39",
        "00:24:90",
        "00:26:5d",
        "08:fc:52",
        "14:bb:6e",
        "1c:5a:3e",
        "24:4b:81",
        "28:27:bf",
        "34:14:5f",
        "38:01:46",
        "40:40:a7",
        "4c:66:41",
        "50:56:bf",
        "5c:f6:dc",
        "64:b3:10",
        "78:40:e4",
        "84:25:19",
        "88:32:9b",
        "90:18:7c",
        "a8:7b:39",
        "b0:c4:e7",
        "bc:44:86",
        "c4:42:02",
        "cc:07:ab",
        "d0:22:be",
        "d8:57:ef",
        "e4:7c:f9",
        "f4:09:d8",
    ),
    "Xiaomi": (
        "00:ec:0a",
        "04:cf:8c",
        "14:f6:5a",
        "20:34:fb",
        "28:6c:07",
        "34:80:0d",
        "50:64:2b",
        "58:44:98",
        "64:09:80",
        "74:23:44",
        "78:02:f8",
        "88:c3:97",
        "98:fa:e3",
        "a4:3b:35",
        "ac:c1:ee",
        "c4:0b:cb",
        "d4:97:0b",
        "e4:46:da",
        "f0:b4:29",
    ),
    "Huawei": (
        "00:1e:10",
        "00:25:9e",
        "08:19:a6",
        "10:47:80",
        "24:69:68",
        "34:2e:b7",
        "40:4d:8e",
        "48:46:fb",
        "54:89:98",
        "70:72:3c",
        "84:a8:e4",
        "9c:28:bf",
        "a8:ca:7b",
        "b4:15:13",
        "c8:d1:5e",
        "e0:28:6d",
        "f4:c4:79",
    ),
    "Google": (
        "00:1a:11",
        "3c:5a:37",
        "48:d6:d5",
        "54:60:09",
        "70:3a:cb",
        "94:eb:2c",
        "a4:77:33",
        "b4:f7:a1",
        "d8:6c:63",
        "f4:03:04",
        "f4:f5:e8",
    ),
    "Raspberry Pi": ("b8:27:eb", "dc:a6:32", "e4:5f:01", "28:cd:c1"),
    "Espressif": (
        "24:0a:c4",
        "24:6f:28",
        "30:ae:a4",
        "84:f3:eb",
        "a4:cf:12",
        "bc:dd:c2",
        "cc:50:e3",
        "dc:4f:22",
    ),
    "Intel": (
        "00:1b:21",
        "00:1e:67",
        "00:21:6a",
        "00:23:14",
        "00:24:d7",
        "34:13:e8",
        "3c:f0:11",
        "68:05:ca",
        "7c:5c:f8",
        "80:86:f2",
        "a0:36:9f",
    ),
    "TP-Link": (
        "00:27:19",
        "14:cc:20",
        "30:de:4b",
        "50:c7:bf",
        "60:a4:4c",
        "70:4f:57",
        "98:48:27",
        "b0:4e:26",
        "c0:06:c3",
        "e8:48:b8",
    ),
    "Amazon": (
        "00:fc:8b",
        "38:f7:3d",
        "40:b4:cd",
        "44:65:0d",
        "50:f5:da",
        "68:37:e9",
        "74:c2:46",
        "84:d6:d0",
        "ac:63:be",
        "b4:7c:9c",
        "f0:27:2d",
    ),
    "Microsoft": (
        "00:15:5d",
        "00:50:f2",
        "28:18:78",
        "50:1a:c5",
        "7c:ed:8d",
        "dc:98:40",
    ),
    "Sony": (
        "00:01:4a",
        "00:13:15",
        "00:19:c5",
        "00:24:8d",
        "28:0d:fc",
        "70:9e:29",
        "f8:d0:ac",
    ),
    "OnePlus": ("94:65:2d", "c0:ee:fb", "64:a2:00"),
}

OUI_VENDORS: dict[str, str] = {
    p: v for v, prefixes in VENDOR_PREFIXES.items() for p in prefixes
}


def get_mac_vendor(mac: str) -> str:
    """Resolve vendor from MAC address or identify randomized private MAC."""
    if not mac or ":" not in mac:
        return "Unknown"
    parts = mac.lower().split(":")
    if len(parts) < 3:
        return "Unknown"
    try:
        first_byte = int(parts[0], 16)
        if (first_byte & 0x02) != 0:
            return "Private MAC"
    except ValueError:
        pass
    prefix = ":".join(parts[:3])
    return OUI_VENDORS.get(prefix, "Unknown")


def get_device_icon(hostname: str, vendor: str) -> str:
    """Guess an appropriate emoji icon for the device."""
    combined = f"{hostname.lower()} {vendor.lower()}"
    if any(k in combined for k in ["iphone", "ipad", "apple"]):
        return "🍎"
    elif any(k in combined for k in ["laptop", "pc", "desktop", "macbook", "windows"]):
        return "💻"
    elif any(k in combined for k in ["tv", "roku", "chromecast", "firetv", "bravia"]):
        return "📺"
    elif any(k in combined for k in ["watch"]):
        return "⌚"
    elif any(k in combined for k in ["raspberry", "rpi"]):
        return "🍓"
    elif any(k in combined for k in ["esp", "iot", "tuya", "sonoff"]):
        return "📟"
    return "📱"


def format_bytes(n: int) -> str:
    """Format bytes to human readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def format_duration(sec: int) -> str:
    """Format seconds into readable duration (e.g. 1h 24m)."""
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60}s"
    if sec < 86400:
        return f"{sec // 3600}h {(sec % 3600) // 60}m"
    return f"{sec // 86400}d {(sec % 86400) // 3600}h"


def get_signal_info(signal: int) -> tuple[str, str]:
    """Return signal icon and descriptive quality."""
    if signal >= -50:
        return "🟢", f"{signal} dBm (Excellent)"
    if signal >= -65:
        return "🟢", f"{signal} dBm (Good)"
    if signal >= -75:
        return "🟡", f"{signal} dBm (Fair)"
    return "🔴", f"{signal} dBm (Weak)"
