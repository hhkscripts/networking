"""Unit tests for detailed connected clients inspection and formatting."""

import unittest
from unittest.mock import mock_open, patch

from scripts.hotspot.clients import (
    format_bytes,
    format_clients,
    format_duration,
    get_connected_clients_detailed,
    get_signal_info,
    parse_station_dump_text,
)
from scripts.hotspot.vendors import get_device_icon, get_mac_vendor
from tests.hotspot import hotspot_manager


class ConnectedClientsDetailedTests(unittest.TestCase):
    def test_format_helpers(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(2048), "2.0 KB")
        self.assertEqual(format_bytes(5 * 1024 * 1024), "5.0 MB")
        self.assertEqual(format_bytes(2 * 1024 * 1024 * 1024), "2.00 GB")

        self.assertEqual(format_duration(40), "40s")
        self.assertEqual(format_duration(125), "2m 5s")
        self.assertEqual(format_duration(3665), "1h 1m")

        icon, desc = get_signal_info(-45)
        self.assertEqual(icon, "🟢")
        self.assertIn("Excellent", desc)

        icon, desc = get_signal_info(-80)
        self.assertEqual(icon, "🔴")
        self.assertIn("Weak", desc)

    def test_vendor_and_icon_resolution(self):
        # Known OUI
        self.assertEqual(get_mac_vendor("b8:27:eb:12:34:56"), "Raspberry Pi")
        self.assertEqual(get_mac_vendor("00:03:93:ab:cd:ef"), "Apple")
        self.assertEqual(get_mac_vendor("00:07:ab:11:22:33"), "Samsung")

        # Private / Randomized MAC (second hex digit 2, 6, a, e)
        self.assertEqual(get_mac_vendor("da:a1:19:6b:12:44"), "Private MAC")
        self.assertEqual(get_mac_vendor("f2:22:33:44:55:66"), "Private MAC")

        # Unknown
        self.assertEqual(get_mac_vendor("11:22:33:44:55:66"), "Unknown")
        self.assertEqual(get_mac_vendor(""), "Unknown")

        # Device icons
        self.assertEqual(get_device_icon("iPhone-14", "Apple"), "🍎")
        self.assertEqual(get_device_icon("MacBook-Air", "Apple"), "🍎")
        self.assertEqual(get_device_icon("work-pc", "Dell"), "💻")
        self.assertEqual(get_device_icon("my-tv", "LG"), "📺")
        self.assertEqual(get_device_icon("pi-node", "Raspberry Pi"), "🍓")
        self.assertEqual(get_device_icon("sensor", "Espressif"), "📟")
        self.assertEqual(get_device_icon("android-phone", "Samsung"), "📱")

    def test_parse_station_dump_text(self):
        raw_output = """Station b8:27:eb:11:22:33 (on wlan0)
\tinactive time:\t210 ms
\trx bytes:\t1048576
\ttx bytes:\t2097152
\tsignal:\t-48 dBm
\ttx bitrate:\t72.2 MBit/s
\trx bitrate:\t65.0 MBit/s
\tconnected time:\t1500 seconds
Station 00:11:22:33:44:55 (on wlan0)
\tsignal:\t-78 dBm
"""
        stations = parse_station_dump_text(raw_output)
        self.assertIn("b8:27:eb:11:22:33", stations)
        st1 = stations["b8:27:eb:11:22:33"]
        self.assertEqual(st1["signal"], -48)
        self.assertEqual(st1["rx_bytes"], 1048576)
        self.assertEqual(st1["tx_bytes"], 2097152)
        self.assertEqual(st1["tx_bitrate"], "72.2 MBit/s")
        self.assertEqual(st1["connected_time"], 1500)

        self.assertIn("00:11:22:33:44:55", stations)
        self.assertEqual(stations["00:11:22:33:44:55"]["signal"], -78)

    def test_get_connected_clients_with_wifi_stations(self):
        lease_content = (
            "1900000000 b8:27:eb:11:22:33 10.42.0.50 test-pi 01:b8:27:eb:11:22:33\n"
        )
        station_output = """Station b8:27:eb:11:22:33 (on wlan0)
\tsignal:\t-55 dBm
\trx bytes:\t4096
\ttx bytes:\t8192
\ttx bitrate:\t54.0 MBit/s
\tconnected time:\t120 seconds
"""
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=lease_content)),
            patch.object(
                hotspot_manager,
                "run_args",
                side_effect=[
                    (True, station_output, ""),
                    (False, "", ""),
                ],
            ),
        ):
            clients = get_connected_clients_detailed()
            self.assertEqual(len(clients), 1)
            c = clients[0]
            self.assertEqual(c["mac"], "b8:27:eb:11:22:33")
            self.assertEqual(c["ip"], "10.42.0.50")
            self.assertEqual(c["hostname"], "test-pi")
            self.assertEqual(c["vendor"], "Raspberry Pi")
            self.assertEqual(c["signal"], -55)
            self.assertIn("Good", c["signal_quality"])
            self.assertEqual(c["rx_bytes_str"], "4.0 KB")
            self.assertEqual(c["tx_bytes_str"], "8.0 KB")

    def test_format_clients_output(self):
        mock_devices = [
            {
                "hostname": "John-Phone<script>",
                "ip": "10.42.0.100",
                "mac": "00:03:93:ab:cd:ef",
                "vendor": "Apple",
                "icon": "🍎",
                "signal_quality": "🟢 -45 dBm (Excellent)",
                "rx_bytes_str": "12.5 MB",
                "tx_bytes_str": "3.1 MB",
                "tx_bitrate": "72.2 MBit/s",
                "connected_time_str": "1h 15m",
                "lease_remaining_str": "12h remaining",
            }
        ]
        # HTML formatting
        html_out = format_clients(mock_devices, telegram_format=True)
        self.assertIn("CONNECTED CLIENTS (1)", html_out)
        self.assertIn("John-Phone&lt;script&gt;", html_out)
        self.assertIn("10.42.0.100", html_out)
        self.assertIn("00:03:93:ab:cd:ef", html_out)
        self.assertIn("Apple", html_out)
        self.assertIn("Traffic:", html_out)
        self.assertIn("12.5 MB", html_out)

        # Terminal formatting
        term_out = format_clients(mock_devices, telegram_format=False)
        self.assertIn("CONNECTED CLIENTS (1)", term_out)
        self.assertIn("John-Phone<script>", term_out)
        self.assertIn("Apple", term_out)

        # Empty clients
        empty_html = format_clients([], telegram_format=True)
        self.assertIn("No connected devices found", empty_html)
        empty_term = format_clients([], telegram_format=False)
        self.assertIn("No connected devices found", empty_term)


if __name__ == "__main__":
    unittest.main()
