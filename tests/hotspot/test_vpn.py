"""Tests for VPN restarts, routing policy apply, and backend switches."""

import unittest
from unittest.mock import patch

from tests.hotspot import hotspot_manager


class RestartVpnTests(unittest.TestCase):
    def test_retries_activation_before_applying_policy(self):
        up_attempts = 0

        def fake_run_args(cmd, timeout=30):
            nonlocal up_attempts
            if cmd[:4] == ["sudo", "nmcli", "connection", "up"]:
                up_attempts += 1
                if up_attempts == 1:
                    return False, "", "temporary timeout"
            return True, "", ""

        with (
            patch.object(
                hotspot_manager, "get_configured_backend", return_value="tun0"
            ),
            patch.object(hotspot_manager, "check_vpn", return_value=False),
            patch.object(hotspot_manager, "run_args", side_effect=fake_run_args),
            patch.object(hotspot_manager, "wait_for_interface", return_value=True),
            patch.object(
                hotspot_manager, "apply_vpn_policy", return_value=True
            ) as policy,
            patch.object(hotspot_manager, "refresh_github_routes") as refresh,
            patch.object(
                hotspot_manager, "ensure_adguard_resilience", return_value=(True, "ok")
            ) as ensure_adg,
            patch.object(hotspot_manager.time, "sleep"),
            patch.object(hotspot_manager, "log"),
        ):
            self.assertTrue(hotspot_manager.restart_vpn())

        self.assertEqual(up_attempts, 2)
        policy.assert_called_once_with("tun0")
        refresh.assert_called_once_with()
        ensure_adg.assert_called_once_with()

    def test_github_refresh_allows_sufficient_runtime(self):
        with (
            patch.object(hotspot_manager, "run_args") as run,
            patch.object(hotspot_manager, "APPLY_ROUTE_SCRIPT", "/apply-routes"),
            patch.object(hotspot_manager, "GITHUB_ROUTE_SCRIPT", "/route-refresh"),
        ):
            run.side_effect = [
                (True, "", ""),
                (True, "", ""),
                (True, "", ""),
                (True, "", ""),
            ]
            hotspot_manager.refresh_github_routes()

        self.assertEqual(run.call_args_list[1].kwargs["timeout"], 60)
        self.assertEqual(run.call_args_list[3].kwargs["timeout"], 120)

    def test_routes_refresh_runs_both_apply_and_github_scripts(self):
        with (
            patch.object(hotspot_manager, "run_args") as run,
            patch.object(hotspot_manager, "APPLY_ROUTE_SCRIPT", "/apply-routes"),
            patch.object(hotspot_manager, "GITHUB_ROUTE_SCRIPT", "/github-routes"),
        ):
            run.side_effect = [
                (True, "", ""),
                (True, "", ""),
                (True, "", ""),
                (True, "", ""),
            ]
            ok = hotspot_manager.refresh_routes()
            self.assertTrue(ok)

        self.assertEqual(run.call_args_list[0].args[0], ["test", "-x", "/apply-routes"])
        self.assertEqual(run.call_args_list[1].args[0], ["sudo", "/apply-routes"])
        self.assertEqual(
            run.call_args_list[2].args[0], ["test", "-x", "/github-routes"]
        )
        self.assertEqual(run.call_args_list[3].args[0], ["sudo", "/github-routes"])


class SingboxBackendTests(unittest.TestCase):
    def test_get_active_vpn_interface_sing0(self):
        with patch.object(
            hotspot_manager,
            "run_args",
            return_value=(True, "default dev sing0 proto static scope link\n", ""),
        ):
            iface, name = hotspot_manager.get_active_vpn_interface()
            self.assertEqual(iface, "sing0")
            self.assertEqual(name, "VLESS")

    def test_switch_vpn_sing0(self):
        with (
            patch.object(hotspot_manager, "update_goodwifi_conf", return_value=True),
            patch.object(
                hotspot_manager, "get_vpn_connection_name", return_value="goodwifi-vpn"
            ),
            patch.object(hotspot_manager, "run_args", return_value=(True, "", "")),
            patch.object(hotspot_manager, "wait_for_interface", return_value=True),
            patch.object(
                hotspot_manager, "apply_vpn_policy", return_value=True
            ) as apply_pol,
            patch.object(hotspot_manager, "refresh_github_routes"),
            patch.object(
                hotspot_manager, "ensure_adguard_resilience", return_value=(True, "ok")
            ) as ensure_adg,
            patch.object(hotspot_manager, "log"),
        ):
            self.assertTrue(hotspot_manager.switch_vpn("sing0"))
            apply_pol.assert_called_once_with("sing0")
            ensure_adg.assert_called_once_with()


class VpnResilienceWatchdogTests(unittest.TestCase):
    def test_ensure_vpn_resilience_healthy(self):
        with (
            patch.object(hotspot_manager, "check_vpn", return_value=True),
            patch.object(
                hotspot_manager, "check_vpn_external_ip", return_value=(True, "1.2.3.4")
            ),
            patch.object(
                hotspot_manager,
                "get_active_vpn_interface",
                return_value=("sing0", "VLESS"),
            ),
        ):
            ok, state = hotspot_manager.ensure_vpn_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "vpn_healthy")

    def test_ensure_vpn_resilience_rotates_candidate_ip(self):
        with (
            patch.object(hotspot_manager, "check_vpn", return_value=False),
            patch.object(
                hotspot_manager,
                "get_active_vpn_interface",
                return_value=("sing0", "VLESS"),
            ),
            patch.object(
                hotspot_manager, "get_configured_unlimited_country", return_value="jp"
            ),
            patch.object(
                hotspot_manager, "rotate_unlimited_country_ip", return_value=True
            ) as rot,
            patch.object(hotspot_manager, "log"),
        ):
            ok, state = hotspot_manager.ensure_vpn_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "vpn_rotated_ip")
            rot.assert_called_once_with("jp")

    def test_ensure_vpn_resilience_restarts_backend(self):
        with (
            patch.object(hotspot_manager, "check_vpn", return_value=False),
            patch.object(
                hotspot_manager,
                "get_active_vpn_interface",
                return_value=("awg0", "AmneziaWG"),
            ),
            patch.object(
                hotspot_manager,
                "get_configured_unlimited_country",
                return_value="direct",
            ),
            patch.object(hotspot_manager, "restart_vpn", return_value=True) as rst,
            patch.object(hotspot_manager, "log"),
        ):
            ok, state = hotspot_manager.ensure_vpn_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "vpn_recovered")
            rst.assert_called_once_with("awg0")


if __name__ == "__main__":
    unittest.main()
