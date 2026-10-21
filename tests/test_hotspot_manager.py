"""Backward-compatible test runner for modular hotspot manager tests."""

# flake8: noqa: F401

import unittest

from tests.hotspot.test_adguard import AdGuardStateTests
from tests.hotspot.test_clients import ConnectedClientsDetailedTests
from tests.hotspot.test_detection import VpnConnectionDetectionTests
from tests.hotspot.test_ipv6 import Ipv6ModeTests
from tests.hotspot.test_proxy import RouterProxyHandlerTests
from tests.hotspot.test_remote import RemoteVpsExitTests
from tests.hotspot.test_runner import (
    DockerServiceTests,
    RunArgsTests,
    StatusChecksTests,
)
from tests.hotspot.test_singbox import CountryProfileTests
from tests.hotspot.test_vpn import (
    ApplyVpnPolicyTests,
    RestartVpnTests,
    SingboxBackendTests,
    VpnResilienceWatchdogTests,
)
from tests.hotspot.test_wan import WanResilienceTests

if __name__ == "__main__":
    unittest.main()
