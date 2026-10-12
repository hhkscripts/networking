"""Backward-compatible test runner for modular hotspot manager tests."""

import unittest

from tests.hotspot.test_adguard import AdGuardStateTests
from tests.hotspot.test_clients import ConnectedClientsDetailedTests
from tests.hotspot.test_detection import VpnConnectionDetectionTests
from tests.hotspot.test_ipv6 import Ipv6ModeTests
from tests.hotspot.test_runner import DockerServiceTests, RunArgsTests
from tests.hotspot.test_singbox import CountryProfileTests
from tests.hotspot.test_vpn import (
    RestartVpnTests,
    SingboxBackendTests,
    VpnResilienceWatchdogTests,
)

__all__ = [
    "RunArgsTests",
    "RestartVpnTests",
    "Ipv6ModeTests",
    "DockerServiceTests",
    "VpnConnectionDetectionTests",
    "ConnectedClientsDetailedTests",
    "AdGuardStateTests",
    "SingboxBackendTests",
    "CountryProfileTests",
    "VpnResilienceWatchdogTests",
]

if __name__ == "__main__":
    unittest.main()
