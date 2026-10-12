#!/usr/bin/env python3
"""
MAC OUI vendor mapping and device type detection.
"""

OUI_VENDORS: dict[str, str] = {
    # Apple
    "00:03:93": "Apple", "00:05:02": "Apple", "00:0a:95": "Apple", "00:0d:93": "Apple",
    "00:10:fa": "Apple", "00:14:51": "Apple", "00:16:cb": "Apple", "00:17:f2": "Apple",
    "00:19:e3": "Apple", "00:1b:63": "Apple", "00:1c:b3": "Apple", "00:1e:52": "Apple",
    "00:1f:5b": "Apple", "00:1f:f3": "Apple", "00:23:12": "Apple", "00:25:00": "Apple",
    "00:26:08": "Apple", "00:26:b0": "Apple", "04:0c:ce": "Apple", "04:15:52": "Apple",
    "04:48:9a": "Apple", "04:54:53": "Apple", "08:66:98": "Apple", "0c:74:c2": "Apple",
    "10:94:bb": "Apple", "14:7d:c5": "Apple", "20:ee:28": "Apple", "28:0b:5c": "Apple",
    "34:08:bc": "Apple", "34:12:98": "Apple", "38:ca:da": "Apple", "3c:07:54": "Apple",
    "40:6c:8f": "Apple", "58:55:ca": "Apple", "60:03:08": "Apple", "64:a5:c3": "Apple",
    "70:ec:e4": "Apple", "7c:04:d0": "Apple", "80:e6:50": "Apple", "88:66:5a": "Apple",
    "8c:85:90": "Apple", "90:b9:31": "Apple", "98:10:e8": "Apple", "a4:83:e7": "Apple",
    "ac:bc:32": "Apple", "b8:78:26": "Apple", "bc:9f:ef": "Apple", "c8:2a:14": "Apple",
    "d0:23:db": "Apple", "d8:96:95": "Apple", "e0:b9:ba": "Apple", "f0:18:98": "Apple",
    "f8:ff:c2": "Apple",
    # Samsung
    "00:07:ab": "Samsung", "00:12:47": "Samsung", "00:15:99": "Samsung", "00:16:32": "Samsung",
    "00:1a:8a": "Samsung", "00:21:19": "Samsung", "00:23:39": "Samsung", "00:24:90": "Samsung",
    "00:26:5d": "Samsung", "08:fc:52": "Samsung", "14:bb:6e": "Samsung", "1c:5a:3e": "Samsung",
    "24:4b:81": "Samsung", "28:27:bf": "Samsung", "34:14:5f": "Samsung", "38:01:46": "Samsung",
    "40:40:a7": "Samsung", "4c:66:41": "Samsung", "50:56:bf": "Samsung", "5c:f6:dc": "Samsung",
    "64:b3:10": "Samsung", "78:40:e4": "Samsung", "84:25:19": "Samsung", "88:32:9b": "Samsung",
    "90:18:7c": "Samsung", "a8:7b:39": "Samsung", "b0:c4:e7": "Samsung", "bc:44:86": "Samsung",
    "c4:42:02": "Samsung", "cc:07:ab": "Samsung", "d0:22:be": "Samsung", "d8:57:ef": "Samsung",
    "e4:7c:f9": "Samsung", "f4:09:d8": "Samsung",
    # Xiaomi
    "00:ec:0a": "Xiaomi", "04:cf:8c": "Xiaomi", "14:f6:5a": "Xiaomi", "20:34:fb": "Xiaomi",
    "28:6c:07": "Xiaomi", "34:80:0d": "Xiaomi", "50:64:2b": "Xiaomi", "58:44:98": "Xiaomi",
    "64:09:80": "Xiaomi", "74:23:44": "Xiaomi", "78:02:f8": "Xiaomi", "88:c3:97": "Xiaomi",
    "98:fa:e3": "Xiaomi", "a4:3b:35": "Xiaomi", "ac:c1:ee": "Xiaomi", "c4:0b:cb": "Xiaomi",
    "d4:97:0b": "Xiaomi", "e4:46:da": "Xiaomi", "f0:b4:29": "Xiaomi",
    # Huawei
    "00:1e:10": "Huawei", "00:25:9e": "Huawei", "08:19:a6": "Huawei", "10:47:80": "Huawei",
    "24:69:68": "Huawei", "34:2e:b7": "Huawei", "40:4d:8e": "Huawei", "48:46:fb": "Huawei",
    "54:89:98": "Huawei", "70:72:3c": "Huawei", "84:a8:e4": "Huawei", "9c:28:bf": "Huawei",
    "a8:ca:7b": "Huawei", "b4:15:13": "Huawei", "c8:d1:5e": "Huawei", "e0:28:6d": "Huawei",
    "f4:c4:79": "Huawei",
    # Google
    "00:1a:11": "Google", "3c:5a:37": "Google", "48:d6:d5": "Google", "54:60:09": "Google",
    "70:3a:cb": "Google", "94:eb:2c": "Google", "a4:77:33": "Google", "b4:f7:a1": "Google",
    "d8:6c:63": "Google", "f4:03:04": "Google", "f4:f5:e8": "Google",
    # Raspberry Pi
    "b8:27:eb": "Raspberry Pi", "dc:a6:32": "Raspberry Pi", "e4:5f:01": "Raspberry Pi",
    "28:cd:c1": "Raspberry Pi",
    # Espressif (ESP8266/ESP32)
    "24:0a:c4": "Espressif", "24:6f:28": "Espressif", "30:ae:a4": "Espressif",
    "84:f3:eb": "Espressif", "a4:cf:12": "Espressif", "bc:dd:c2": "Espressif",
    "cc:50:e3": "Espressif", "dc:4f:22": "Espressif",
    # Intel & Networking
    "00:1b:21": "Intel", "00:1e:67": "Intel", "00:21:6a": "Intel", "00:23:14": "Intel",
    "00:24:d7": "Intel", "34:13:e8": "Intel", "3c:f0:11": "Intel", "68:05:ca": "Intel",
    "7c:5c:f8": "Intel", "80:86:f2": "Intel", "a0:36:9f": "Intel",
    "00:27:19": "TP-Link", "14:cc:20": "TP-Link", "30:de:4b": "TP-Link", "50:c7:bf": "TP-Link",
    "60:a4:4c": "TP-Link", "70:4f:57": "TP-Link", "98:48:27": "TP-Link", "b0:4e:26": "TP-Link",
    "c0:06:c3": "TP-Link", "e8:48:b8": "TP-Link",
    "00:fc:8b": "Amazon", "38:f7:3d": "Amazon", "40:b4:cd": "Amazon", "44:65:0d": "Amazon",
    "50:f5:da": "Amazon", "68:37:e9": "Amazon", "74:c2:46": "Amazon", "84:d6:d0": "Amazon",
    "ac:63:be": "Amazon", "b4:7c:9c": "Amazon", "f0:27:2d": "Amazon",
    "00:15:5d": "Microsoft", "00:50:f2": "Microsoft", "28:18:78": "Microsoft",
    "50:1a:c5": "Microsoft", "7c:ed:8d": "Microsoft", "dc:98:40": "Microsoft",
    "00:01:4a": "Sony", "00:13:15": "Sony", "00:19:c5": "Sony", "00:24:8d": "Sony",
    "28:0d:fc": "Sony", "70:9e:29": "Sony", "f8:d0:ac": "Sony",
    "94:65:2d": "OnePlus", "c0:ee:fb": "OnePlus", "64:a2:00": "OnePlus",
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
