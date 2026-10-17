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


if __name__ == "__main__":
    unittest.main()
