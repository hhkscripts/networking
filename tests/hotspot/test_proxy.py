"""Unit tests for the Router AP HTTP reverse proxy."""

import io
import unittest
from unittest.mock import MagicMock, patch

from hotspot.proxy import RouterProxyHandler


class RouterProxyHandlerTests(unittest.TestCase):
    def test_proxy_rewrites_referer_and_host(self):
        handler = RouterProxyHandler.__new__(RouterProxyHandler)
        handler.target_host = "10.43.0.2"
        handler.alias_ip = "192.168.100.2"
        handler.path = "/userRpm/StatusRpm.htm"
        handler.command = "GET"
        handler.headers = {
            "Host": "192.168.100.2",
            "Referer": "http://192.168.100.2/userRpm/Index.htm",
            "Authorization": "Basic YWRtaW46YWRtaW4=",
        }
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.read.return_value = b"<html>ok</html>"

        sent_requests = []

        def fake_urlopen(req, timeout=10):
            sent_requests.append(req)
            return mock_resp

        with (
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
            patch.object(handler, "send_response") as mock_send_resp,
            patch.object(handler, "send_header") as mock_send_hdr,
            patch.object(handler, "end_headers"),
        ):
            handler.do_GET()

        self.assertEqual(len(sent_requests), 1)
        req = sent_requests[0]
        self.assertEqual(req.get_header("Host"), "10.43.0.2")
        self.assertEqual(
            req.get_header("Referer"), "http://10.43.0.2/userRpm/Index.htm"
        )
        self.assertEqual(req.get_header("Authorization"), "Basic YWRtaW46YWRtaW4=")
        mock_send_resp.assert_called_once_with(200)
        mock_send_hdr.assert_any_call("Content-Type", "text/html")

    def test_proxy_handles_location_header_rewrite(self):
        handler = RouterProxyHandler.__new__(RouterProxyHandler)
        handler.target_host = "10.43.0.2"
        handler.alias_ip = "192.168.100.2"
        handler.path = "/"
        handler.command = "GET"
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.status = 302
        mock_resp.headers = {
            "Location": "http://10.43.0.2/userRpm/Index.htm",
            "Content-Type": "text/html",
        }
        mock_resp.read.return_value = b""

        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch.object(handler, "send_response"),
            patch.object(handler, "send_header") as mock_send_hdr,
            patch.object(handler, "end_headers"),
        ):
            handler.do_GET()

        mock_send_hdr.assert_any_call(
            "Location", "http://192.168.100.2/userRpm/Index.htm"
        )


if __name__ == "__main__":
    unittest.main()
