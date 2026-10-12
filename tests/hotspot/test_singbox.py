"""Tests for Singbox configuration generation and country profile scanning."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.hotspot import hotspot_manager


class CountryProfileTests(unittest.TestCase):
    def test_get_country_profiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "user_sg_vpn.ovpn").touch()
            Path(tmpdir, "user_jp_vpn.ovpn").touch()
            profs = hotspot_manager.get_country_profiles(tmpdir)
            self.assertIn("sg", profs)
            self.assertIn("jp", profs)
            self.assertEqual(profs["sg"]["flag"], "🇸🇬")
            self.assertEqual(profs["sg"]["country_name"], "Singapore")
            self.assertEqual(profs["jp"]["flag"], "🇯🇵")
            self.assertEqual(profs["jp"]["country_name"], "Japan")

    def test_get_active_vpn_interface_sing0_with_country(self):
        with (
            patch.object(
                hotspot_manager,
                "get_configured_unlimited_country",
                return_value="sg",
            ),
            patch.object(
                hotspot_manager,
                "run_args",
                return_value=(True, "default dev sing0 proto static scope link\n", ""),
            ),
        ):
            iface, name = hotspot_manager.get_active_vpn_interface()
            self.assertEqual(iface, "sing0")
            self.assertEqual(name, "VLESS [🇸🇬 SG]")

    def test_generate_singbox_config_direct(self):
        cfg = hotspot_manager.generate_singbox_config(None)
        self.assertNotIn("endpoints", cfg)
        self.assertEqual(cfg["inbounds"][0]["type"], "tun")
        self.assertEqual(cfg["outbounds"][0]["type"], "socks")
        self.assertEqual(cfg["route"]["rules"][0]["action"], "sniff")
        self.assertEqual(cfg["route"]["rules"][1]["outbound"], "xray-socks")

    def test_generate_singbox_config_detour(self):
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as tf:
            tf.write(
                "[Interface]\n"
                "PrivateKey = fake_priv_key\n"
                "Address = 10.102.147.215/32\n"
                "[Peer]\n"
                "PublicKey = fake_pub_key\n"
                "Endpoint = 143.198.208.211:255\n"
                "AllowedIPs = 0.0.0.0/0\n"
            )
            tf_path = tf.name

        try:
            cfg = hotspot_manager.generate_singbox_config(tf_path)
            self.assertIn("endpoints", cfg)
            ep = cfg["endpoints"][0]
            self.assertEqual(ep["type"], "wireguard")
            self.assertEqual(ep["detour"], "xray-socks")
            self.assertEqual(ep["peers"][0]["address"], "143.198.208.211")
            self.assertEqual(ep["peers"][0]["port"], 255)
            self.assertEqual(ep["peers"][0]["persistent_keepalive_interval"], 25)
            self.assertEqual(cfg["route"]["rules"][0]["action"], "sniff")
            self.assertEqual(cfg["route"]["rules"][-1]["outbound"], "wg-out")
        finally:
            if os.path.exists(tf_path):
                os.unlink(tf_path)

    def test_generate_singbox_config_ovpn_detour(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ovpn", delete=False) as tf:
            tf.write(
                "client\n"
                "dev tun\n"
                "remote de.nordvpn.com 1195\n"
                "cipher AES-128-GCM\n"
                "auth SHA256\n"
                "<ca>\nfake_ca\n</ca>\n"
                "<cert>\nfake_cert\n</cert>\n"
                "<key>\nfake_key\n</key>\n"
            )
            tf_path = tf.name

        try:
            cfg = hotspot_manager.generate_singbox_config(tf_path)
            self.assertIn("endpoints", cfg)
            ep = cfg["endpoints"][0]
            self.assertEqual(ep["type"], "openvpn-client")
            self.assertEqual(ep["server_port"], 1195)
            self.assertEqual(ep["auth"], "SHA256")
            self.assertIn("AES-128-GCM", ep["data_ciphers"])
            self.assertEqual(ep["tls"]["server_name"], "de.nordvpn.com")
            self.assertEqual(ep["ping_interval"], "5s")
            self.assertEqual(ep["ping_restart"], "20s")
            self.assertEqual(cfg["route"]["rules"][-1]["outbound"], "ovpn-out")
        finally:
            if os.path.exists(tf_path):
                os.unlink(tf_path)

    def test_switch_unlimited_country(self):
        with (
            patch.object(
                hotspot_manager, "update_goodwifi_conf", return_value=True
            ) as upd,
            patch.object(
                hotspot_manager, "get_configured_backend", return_value="sing0"
            ),
            patch.object(hotspot_manager, "run_args", return_value=(True, "", "")),
            patch.object(hotspot_manager, "wait_for_interface", return_value=True),
            patch.object(hotspot_manager, "apply_vpn_policy", return_value=True),
            patch.object(
                hotspot_manager, "ensure_adguard_resilience", return_value=(True, "ok")
            ) as ensure_adg,
            patch.object(
                hotspot_manager, "get_host_path", return_value="/tmp/singbox_test.json"
            ),
        ):
            self.assertTrue(hotspot_manager.switch_unlimited_country("direct"))
            upd.assert_called_once_with("UNLIMITED_COUNTRY", "direct")
            ensure_adg.assert_called_once_with()

    def test_resolve_server_ips_and_next_ip(self):
        # Raw IP should return directly
        self.assertEqual(hotspot_manager.resolve_server_ips("1.2.3.4"), ["1.2.3.4"])

        # Multiple IPs resolution mock
        with patch(
            "socket.getaddrinfo",
            return_value=[
                (None, None, None, None, ("10.0.0.1", 0)),
                (None, None, None, None, ("10.0.0.2", 0)),
            ],
        ):
            ips = hotspot_manager.resolve_server_ips("vpn.example.com")
            self.assertIn("10.0.0.1", ips)
            self.assertIn("10.0.0.2", ips)

    def test_rotate_unlimited_country_ip(self):
        with (
            patch.object(
                hotspot_manager, "get_configured_unlimited_country", return_value="jp"
            ),
            patch.object(
                hotspot_manager,
                "get_country_profiles",
                return_value={"jp": {"path": "/fake/jp.ovpn"}},
            ),
            patch.object(
                hotspot_manager,
                "get_profile_candidate_ips",
                return_value=["10.0.0.1", "10.0.0.2"],
            ),
            patch.object(
                hotspot_manager,
                "get_current_singbox_endpoint_ip",
                return_value="10.0.0.1",
            ),
            patch.object(hotspot_manager, "run_args", return_value=(True, "", "")),
            patch.object(hotspot_manager, "wait_for_interface", return_value=True),
            patch.object(hotspot_manager, "apply_vpn_policy", return_value=True),
            patch.object(hotspot_manager, "refresh_routes", return_value=True),
            patch.object(
                hotspot_manager, "ensure_adguard_resilience", return_value=(True, "ok")
            ),
            patch.object(
                hotspot_manager,
                "check_vpn_external_ip",
                return_value=(True, "10.0.0.2"),
            ),
            patch.object(
                hotspot_manager, "get_host_path", return_value="/tmp/test_singbox.json"
            ),
        ):
            ok = hotspot_manager.rotate_unlimited_country_ip("jp")
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
