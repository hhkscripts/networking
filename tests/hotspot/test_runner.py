"""Tests for subprocess runner and docker container status inspection."""

import subprocess
import unittest
from unittest.mock import patch

from tests.hotspot import hotspot_manager


class RunArgsTests(unittest.TestCase):
    def test_uses_requested_timeout(self):
        completed = subprocess.CompletedProcess(["command"], 0, "ok\n", "")
        with patch.object(subprocess, "run", return_value=completed) as run:
            result = hotspot_manager.run_args(["command"], timeout=75)

        self.assertEqual(result, (True, "ok", ""))
        self.assertEqual(run.call_args.kwargs["timeout"], 75)


class DockerServiceTests(unittest.TestCase):
    def test_check_docker_container_running(self):
        with patch.object(hotspot_manager, "run_args", return_value=(True, "true", "")):
            self.assertTrue(hotspot_manager.check_docker_container("adguardhome"))

    def test_check_docker_container_stopped(self):
        with patch.object(
            hotspot_manager, "run_args", return_value=(True, "false", "")
        ):
            self.assertFalse(hotspot_manager.check_docker_container("adguardhome"))

    def test_check_docker_container_missing(self):
        with patch.object(
            hotspot_manager, "run_args", return_value=(False, "", "no such object")
        ):
            self.assertIsNone(hotspot_manager.check_docker_container("nonexistent"))


class StatusChecksTests(unittest.TestCase):
    def test_check_dns_custom_domain_and_fallback(self):
        with (
            patch.dict(
                hotspot_manager.CONFIG,
                {"dns_test_domain": "custom-domain.local", "hotspot_ip": "10.50.0.1"},
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                side_effect=[(False, "", "error"), (True, "Address: 1.1.1.1", "")],
            ) as mock_run,
        ):
            self.assertTrue(hotspot_manager.check_dns())
            calls = [c[0][0] for c in mock_run.call_args_list]
            self.assertEqual(calls[0], ["nslookup", "custom-domain.local", "10.50.0.1"])
            self.assertEqual(calls[1], ["nslookup", "cloudflare.com", "10.50.0.1"])

    def test_check_dns_router_mode(self):
        with (
            patch.dict(
                hotspot_manager.CONFIG,
                {"ap_mode": "router", "router_ap_ip": "10.43.0.1"},
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(True, "Address: 1.1.1.1", ""),
            ) as mock_run,
        ):
            self.assertTrue(hotspot_manager.check_dns())
            calls = [c[0][0] for c in mock_run.call_args_list]
            self.assertEqual(calls[0], ["nslookup", "google.com", "10.43.0.1"])

    def test_check_clients_interface_fallback(self):
        with (
            patch.dict(hotspot_manager.CONFIG, {"interface_wlan": "wlan0"}),
            patch.object(
                hotspot_manager,
                "run_args",
                side_effect=[
                    (False, "", "No such device"),
                    (False, "", "No such device"),
                    (False, "", "No such device"),
                    (True, "Station aa:bb:cc:dd:ee:ff (on wlan1)\n", ""),
                ],
            ) as mock_run,
        ):
            count = hotspot_manager.check_clients()
            self.assertEqual(count, 1)
            calls = [c[0][0] for c in mock_run.call_args_list]
            dump_w0 = ["sudo", "iw", "dev", "wlan0", "station", "dump"]
            dump_w1 = ["sudo", "iw", "dev", "wlan1", "station", "dump"]
            self.assertEqual(calls[0], dump_w0)
            self.assertEqual(calls[3], dump_w1)

    def test_check_hotspot_router_ap_mode(self):
        with (
            patch.dict(
                hotspot_manager.CONFIG,
                {"ap_mode": "router", "router_ap_if": "eth1"},
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(True, "eth1: <BROADCAST,MULTICAST,UP> state UP", ""),
            ),
        ):
            self.assertTrue(hotspot_manager.check_hotspot())

    def test_check_clients_router_ap_fallback(self):
        with (
            patch.dict(
                hotspot_manager.CONFIG,
                {"ap_mode": "router", "interface_wlan": "wlan0"},
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(False, "", "No device"),
            ),
            patch.object(
                hotspot_manager,
                "get_connected_clients_detailed",
                return_value=[{"ip": "10.43.0.47"}, {"ip": "10.43.0.48"}],
            ),
        ):
            self.assertEqual(hotspot_manager.check_clients(), 2)

    def test_formatter_router_ap_mode(self):
        status = {
            "services": {"hostapd": False, "dnsmasq": True},
            "vpn": {
                "connected": True,
                "backend": "sing-box",
                "interface": "sing0",
                "ip": "10.99.0.1",
                "external_ip": "1.2.3.4",
            },
            "hotspot": {
                "broadcasting": True,
                "clients": 5,
                "ap_mode": "router",
                "router_ip": "10.43.0.2",
                "router_alias_ip": "192.168.100.2",
            },
            "wan": {"interface": "eth0", "type": "Fiber"},
            "dns_working": True,
            "internet": True,
            "ipv6_protection": "drop",
        }
        term_out = hotspot_manager.print_status(status)
        self.assertIn("Standby (Router AP)", term_out)
        self.assertIn("Mode: Router AP (TP-Link via eth1)", term_out)
        self.assertIn("Dashboard: http://10.43.0.2", term_out)
        self.assertIn("Via Router 1: http://192.168.100.2", term_out)
        self.assertIn("Clients: 5", term_out)

        tg_out = hotspot_manager.print_status(status, telegram_format=True)
        self.assertIn("Standby (Router AP)", tg_out)
        self.assertIn("Router AP", tg_out)
        self.assertIn("http://10.43.0.2", tg_out)
        self.assertIn("http://192.168.100.2", tg_out)
        self.assertIn("Clients: <code>5</code>", tg_out)


if __name__ == "__main__":
    unittest.main()
