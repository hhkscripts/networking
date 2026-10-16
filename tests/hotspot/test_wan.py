"""Tests for WAN health checking, failover, and default route switching."""

import unittest
from unittest.mock import patch

from tests.hotspot import hotspot_manager


class WanResilienceTests(unittest.TestCase):
    def test_check_wan_reachability_success(self):
        with patch.object(
            hotspot_manager,
            "run_args",
            side_effect=[
                (True, "state UP", ""),
                (True, "inet 192.168.100.69/24", ""),
                (True, "0% packet loss", ""),
            ],
        ):
            self.assertTrue(hotspot_manager.check_wan_reachability("eth0"))

    def test_check_wan_reachability_down_interface(self):
        with patch.object(
            hotspot_manager,
            "run_args",
            return_value=(False, "", ""),
        ):
            self.assertFalse(hotspot_manager.check_wan_reachability("eth0"))

        route_out = (
            "default via 192.168.100.1 dev eth0 proto dhcp "
            "src 192.168.100.69 metric 100\n"
        )
        with patch.object(
            hotspot_manager,
            "run_args",
            return_value=(True, route_out, ""),
        ):
            self.assertEqual(hotspot_manager.get_current_default_wan(), "eth0")

    def test_switch_wan_uplink_usb0(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="eth0",
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(True, "", ""),
            ) as mock_run,
            patch.object(hotspot_manager, "apply_vpn_policy") as mock_pol,
            patch.object(hotspot_manager, "restart_vpn") as mock_restart,
            patch("builtins.open", unittest.mock.mock_open()),
        ):
            self.assertTrue(hotspot_manager.switch_wan_uplink("usb0"))
            mock_run.assert_any_call(
                [
                    "sudo",
                    "ip",
                    "route",
                    "replace",
                    "default",
                    "dev",
                    "usb0",
                    "metric",
                    "50",
                ]
            )
            mock_pol.assert_called()
            mock_restart.assert_called()

    def test_ensure_wan_resilience_fiber_healthy(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="eth0",
            ),
            patch.object(
                hotspot_manager,
                "check_wan_reachability",
                side_effect=lambda iface: iface == "eth0",
            ),
        ):
            ok, state = hotspot_manager.ensure_wan_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "wan_fiber_healthy")

    def test_ensure_wan_resilience_failover_to_usb(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="eth0",
            ),
            patch.object(
                hotspot_manager,
                "check_wan_reachability",
                side_effect=lambda iface: iface == "usb0",
            ),
            patch.object(
                hotspot_manager,
                "switch_wan_uplink",
                return_value=True,
            ) as mock_switch,
        ):
            ok, state = hotspot_manager.ensure_wan_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "wan_failed_over_to_usb")
            mock_switch.assert_called_with("usb0")

    def test_ensure_wan_resilience_failback_to_fiber(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="usb0",
            ),
            patch.object(
                hotspot_manager,
                "check_wan_reachability",
                side_effect=lambda iface: iface == "eth0",
            ),
            patch.object(
                hotspot_manager,
                "switch_wan_uplink",
                return_value=True,
            ) as mock_switch,
        ):
            ok, state = hotspot_manager.ensure_wan_resilience()
            self.assertTrue(ok)
            self.assertEqual(state, "wan_failed_back_to_fiber")
            mock_switch.assert_called_with("eth0")

    def test_ensure_wan_resilience_all_offline(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="eth0",
            ),
            patch.object(
                hotspot_manager,
                "check_wan_reachability",
                return_value=False,
            ),
        ):
            ok, state = hotspot_manager.ensure_wan_resilience()
            self.assertFalse(ok)
            self.assertEqual(state, "wan_all_offline")

    def test_wan_in_get_status(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="eth0",
            ),
            patch.object(hotspot_manager, "check_clients", return_value=3),
            patch.object(hotspot_manager, "check_vpn", return_value=True),
            patch.object(
                hotspot_manager,
                "get_active_vpn_interface",
                return_value=("sing0", "sing-box"),
            ),
            patch.object(
                hotspot_manager,
                "check_vpn_ip",
                return_value=(True, "10.99.0.1"),
            ),
            patch.object(
                hotspot_manager,
                "check_vpn_external_ip",
                return_value=(True, "1.2.3.4"),
            ),
            patch.object(hotspot_manager, "check_internet", return_value=True),
            patch.object(hotspot_manager, "check_dns", return_value=True),
            patch.object(hotspot_manager, "check_hotspot", return_value=True),
            patch.object(
                hotspot_manager,
                "check_ping",
                return_value={
                    "ok": True,
                    "target": "8.8.8.8",
                    "summary": "ok",
                    "avg_ms": "10",
                    "loss": "0",
                    "rtt": "",
                },
            ),
            patch.object(hotspot_manager, "check_service", return_value=True),
            patch.object(hotspot_manager, "check_docker_container", return_value=True),
        ):
            status = hotspot_manager.get_status()
            self.assertIn("wan", status)
            self.assertEqual(status["wan"]["interface"], "eth0")
            self.assertEqual(status["wan"]["type"], "Fiber")

    def test_wan_in_formatter(self):
        status = {
            "services": {"hostapd": True, "dnsmasq": True},
            "vpn": {
                "connected": True,
                "interface": "sing0",
                "backend": "sing-box",
                "ip": "10.99.0.1",
                "external_ip": "1.2.3.4",
                "external_ok": True,
            },
            "hotspot": {"broadcasting": True, "clients": 2},
            "wan": {"interface": "eth0", "type": "Fiber", "metric": 100},
            "dns_working": True,
            "internet": True,
            "ping": {
                "ok": True,
                "target": "8.8.8.8",
                "summary": "3 packets",
                "avg_ms": "10",
                "loss": "0",
            },
            "ipv6_protection": "reject",
        }
        terminal_out = hotspot_manager.print_status(status, telegram_format=False)
        self.assertIn("🌐 Uplink: Fiber (eth0)", terminal_out)

        html_out = hotspot_manager.print_status(status, telegram_format=True)
        self.assertIn("🌐 Uplink: <code>Fiber (eth0)</code>", html_out)

        # Test mobile USB
        status["wan"] = {"interface": "usb0", "type": "Mobile USB", "metric": 50}
        html_out_usb = hotspot_manager.print_status(status, telegram_format=True)
        self.assertIn("📱 Uplink: <code>Mobile USB (usb0)</code>", html_out_usb)

    def test_switch_wan_uplink_sends_notification(self):
        with (
            patch.object(
                hotspot_manager,
                "get_current_default_wan",
                return_value="eth0",
            ),
            patch.object(hotspot_manager, "run_args", return_value=(True, "", "")),
            patch.object(hotspot_manager, "apply_vpn_policy"),
            patch.object(hotspot_manager, "restart_vpn"),
            patch.object(hotspot_manager, "send_telegram_notification") as mock_notify,
            patch("builtins.open", unittest.mock.mock_open()),
        ):
            hotspot_manager.switch_wan_uplink("usb0")
            mock_notify.assert_called()
            call_msg = mock_notify.call_args[0][0]
            self.assertIn("Mobile USB (usb0)", call_msg)


if __name__ == "__main__":
    unittest.main()
