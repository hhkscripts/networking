"""Tests for AdGuard Home state inspection and fallback DNS switching."""

import unittest
from unittest.mock import patch

from tests.hotspot import hotspot_manager


class AdGuardStateTests(unittest.TestCase):
    def test_get_adguard_enabled_defaults_to_true(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch.object(
                hotspot_manager, "check_docker_container", return_value=True
            ):
                self.assertTrue(hotspot_manager.get_adguard_enabled())

    def test_set_adguard_state_disable(self):
        with (
            patch.object(
                hotspot_manager, "update_goodwifi_conf", return_value=True
            ) as upd,
            patch.object(
                hotspot_manager, "configure_dnsmasq_fallback", return_value=True
            ) as dnsm,
            patch.object(
                hotspot_manager, "run_args", return_value=(True, "", "")
            ) as run,
            patch.object(hotspot_manager, "check_dns", return_value=True),
            patch.object(hotspot_manager, "log"),
        ):
            self.assertTrue(hotspot_manager.set_adguard_state(False))
            upd.assert_called_once_with("ADGUARD_ENABLED", "false")
            dnsm.assert_called_once_with(enable_fallback=True)
            stop_call = any(
                call.args[0][:2] == ["docker", "stop"] for call in run.call_args_list
            )
            self.assertTrue(stop_call)

    def test_set_adguard_state_enable(self):
        with (
            patch.object(
                hotspot_manager, "update_goodwifi_conf", return_value=True
            ) as upd,
            patch.object(
                hotspot_manager, "configure_dnsmasq_fallback", return_value=True
            ) as dnsm,
            patch.object(hotspot_manager, "run_args", return_value=(True, "", "")),
            patch.object(hotspot_manager, "check_docker_container", return_value=True),
            patch.object(hotspot_manager, "log"),
        ):
            self.assertTrue(hotspot_manager.set_adguard_state(True))
            upd.assert_called_once_with("ADGUARD_ENABLED", "true")
            dnsm.assert_called_once_with(enable_fallback=False)

    def test_ensure_adguard_resilience_disabled(self):
        with (
            patch.object(hotspot_manager, "get_adguard_enabled", return_value=False),
            patch.object(
                hotspot_manager, "configure_dnsmasq_fallback", return_value=True
            ) as dnsm,
        ):
            ok, state = hotspot_manager.ensure_adguard_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "fallback_active")
            dnsm.assert_called_once_with(enable_fallback=True)

    def test_ensure_adguard_resilience_healthy(self):
        with (
            patch.object(hotspot_manager, "get_adguard_enabled", return_value=True),
            patch.object(hotspot_manager, "check_docker_container", return_value=True),
            patch.object(
                hotspot_manager, "configure_dnsmasq_fallback", return_value=True
            ) as dnsm,
        ):
            ok, state = hotspot_manager.ensure_adguard_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "adguard_healthy")
            dnsm.assert_called_once_with(enable_fallback=False)

    def test_ensure_adguard_resilience_recovered(self):
        with (
            patch.object(hotspot_manager, "get_adguard_enabled", return_value=True),
            patch.object(
                hotspot_manager, "check_docker_container", side_effect=[False, True]
            ),
            patch.object(
                hotspot_manager, "configure_dnsmasq_fallback", return_value=True
            ) as dnsm,
            patch.object(
                hotspot_manager, "run_args", return_value=(True, "", "")
            ) as run,
            patch("time.sleep"),
            patch.object(hotspot_manager, "log"),
        ):
            ok, state = hotspot_manager.ensure_adguard_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "adguard_recovered")
            dnsm.assert_called_once_with(enable_fallback=False)
            start_call = any(
                call.args[0][:2] == ["docker", "start"] for call in run.call_args_list
            )
            self.assertTrue(start_call)

    def test_ensure_adguard_resilience_crashed_failover(self):
        with (
            patch.object(hotspot_manager, "get_adguard_enabled", return_value=True),
            patch.object(hotspot_manager, "check_docker_container", return_value=False),
            patch.object(
                hotspot_manager, "configure_dnsmasq_fallback", return_value=True
            ) as dnsm,
            patch.object(
                hotspot_manager, "run_args", return_value=(True, "", "")
            ) as run,
            patch("time.sleep"),
            patch.object(hotspot_manager, "log"),
        ):
            ok, state = hotspot_manager.ensure_adguard_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "fallback_activated")
            dnsm.assert_has_calls(
                [
                    unittest.mock.call(enable_fallback=False),
                    unittest.mock.call(enable_fallback=True),
                ]
            )
            restart_call = any(
                call.args[0] == ["sudo", "systemctl", "restart", "dnsmasq"]
                for call in run.call_args_list
            )
            self.assertTrue(restart_call)

    def test_doh_blocklist_rules_exist(self):
        from pathlib import Path

        blocklist_path = (
            Path(__file__).parents[2] / "configs" / "routes" / "dns-doh-blocklist.txt"
        )
        if not blocklist_path.exists():
            blocklist_path = (
                Path(__file__).parents[2] / "configs" / "routes" / "doh-blocklist.txt"
            )
        self.assertTrue(blocklist_path.exists())
        content = blocklist_path.read_text(encoding="utf-8")
        self.assertIn("mask.icloud.com", content)
        self.assertIn("cloudflare-dns.com", content)
        self.assertIn("dns.google", content)
        self.assertIn("dns.quad9.net", content)


if __name__ == "__main__":
    unittest.main()
