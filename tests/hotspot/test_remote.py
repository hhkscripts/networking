"""Tests for dynamic remote VPS exit switcher without hardcoded credentials."""

import json
import tempfile
import unittest
from unittest.mock import patch

from tests.hotspot import hotspot_manager


class RemoteVpsExitTests(unittest.TestCase):
    def test_get_remote_vps_target_from_config(self):
        with patch.dict(
            hotspot_manager.CONFIG,
            {
                "vps_ssh_host": "vpn.example.com",
                "vps_ssh_port": 2200,
                "vps_ssh_user": "admin",
            },
            clear=False,
        ):
            host, port, user = hotspot_manager.get_remote_vps_target()
            self.assertEqual(host, "vpn.example.com")
            self.assertEqual(port, 2200)
            self.assertEqual(user, "admin")

    def test_get_remote_vps_target_autodetect_from_xray(self):
        xray_content = {
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [{"address": "xray.example.org", "port": 8443}]
                    },
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump(xray_content, tf)
            tf_path = tf.name

        try:
            with (
                patch.dict(
                    hotspot_manager.CONFIG,
                    {
                        "vps_ssh_host": None,
                        "vps_ssh_port": 2222,
                        "vps_ssh_user": "root",
                    },
                    clear=False,
                ),
                patch.object(hotspot_manager, "get_host_path", return_value=tf_path),
            ):
                host, port, user = hotspot_manager.get_remote_vps_target()
                self.assertEqual(host, "xray.example.org")
                self.assertEqual(port, 2222)
                self.assertEqual(user, "root")
                self.assertTrue(hotspot_manager.is_remote_vps_configured())
        finally:
            import os

            if os.path.exists(tf_path):
                os.unlink(tf_path)

    def test_switch_remote_vps_exit_success(self):
        with (
            patch.dict(
                hotspot_manager.CONFIG,
                {
                    "vps_ssh_host": "connect.example.com",
                    "vps_ssh_port": 2222,
                    "vps_ssh_user": "root",
                },
                clear=False,
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(
                    True,
                    "Successfully connected to sg (Exit IP: 1.1.1.1)",
                    "",
                ),
            ) as mock_run,
        ):
            ok, out = hotspot_manager.switch_remote_vps_exit("sg")
            self.assertTrue(ok)
            self.assertIn("Successfully connected", out)
            called_cmd = mock_run.call_args[0][0]
            self.assertIn("root@connect.example.com", called_cmd)
            self.assertIn("/usr/local/bin/switch-exit sg", called_cmd)

    def test_switch_remote_vps_exit_failure(self):
        with (
            patch.dict(
                hotspot_manager.CONFIG,
                {
                    "vps_ssh_host": "connect.example.com",
                    "vps_ssh_port": 2222,
                    "vps_ssh_user": "root",
                },
                clear=False,
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(False, "", "Connection timed out"),
            ),
        ):
            ok, out = hotspot_manager.switch_remote_vps_exit("sg")
            self.assertFalse(ok)
            self.assertIn("Connection timed out", out)

    def test_switch_unlimited_country_delegates_to_remote(self):
        with (
            patch.object(
                hotspot_manager, "is_remote_vps_configured", return_value=True
            ),
            patch.object(
                hotspot_manager,
                "switch_remote_vps_exit",
                return_value=(True, "Successfully connected to jp"),
            ) as mock_remote,
            patch.object(
                hotspot_manager, "update_goodwifi_conf", return_value=True
            ) as mock_upd,
            patch.object(
                hotspot_manager, "get_configured_backend", return_value="sing0"
            ),
            patch.object(
                hotspot_manager, "get_host_path", return_value="/tmp/test_sing.json"
            ),
        ):
            res = hotspot_manager.switch_unlimited_country("jp")
            self.assertTrue(res)
            mock_remote.assert_called_once_with("jp")
            mock_upd.assert_called_once_with("UNLIMITED_COUNTRY", "jp")


if __name__ == "__main__":
    unittest.main()
