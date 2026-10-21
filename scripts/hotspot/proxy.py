#!/usr/bin/env python3
"""Lightweight HTTP reverse proxy for TP-Link Router AP web management."""

import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from .constants import CONFIG
from .context import Context


class RouterProxyHandler(BaseHTTPRequestHandler):
    target_host: str = "10.43.0.2"
    alias_ip: str = "192.168.100.2"

    def log_message(self, format: str, *args: object) -> None:
        pass  # Quiet logging

    def do_HEAD(self) -> None:
        self._proxy("HEAD")

    def do_GET(self) -> None:
        self._proxy("GET")

    def do_POST(self) -> None:
        self._proxy("POST")

    def _proxy(self, method: str) -> None:
        url = f"http://{self.target_host}{self.path}"
        length = self.headers.get("Content-Length")
        body = self.rfile.read(int(length)) if length and length.isdigit() else None
        req = urllib.request.Request(url, data=body, method=method)

        for k, v in self.headers.items():
            if k.lower() in ["host", "referer"]:
                continue
            req.add_header(k, v)

        req.add_header("Host", self.target_host)
        referer = self.headers.get("Referer")
        if referer:
            for alias in [self.alias_ip, "192.168.100.69:8092", "192.168.100.69"]:
                referer = referer.replace(alias, self.target_host)
            req.add_header("Referer", referer)
        else:
            req.add_header("Referer", f"http://{self.target_host}/userRpm/Index.htm")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for hk, hv in resp.headers.items():
                    hkl = hk.lower()
                    if hkl in ["transfer-encoding", "content-length"]:
                        continue
                    if hkl == "location":
                        hv = hv.replace(self.target_host, self.alias_ip)
                    self.send_header(hk, hv)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for hk, hv in e.headers.items():
                if hk.lower() not in ["transfer-encoding", "content-length"]:
                    self.send_header(hk, hv)
            err = e.read()
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
        except Exception as e:
            self.send_error(502, f"Router Proxy Error: {e}")


def run_proxy(port: int = 8092, host: str = "127.0.0.1") -> None:
    ctx = Context.get()
    cfg = getattr(ctx, "CONFIG", CONFIG)
    RouterProxyHandler.target_host = cfg.get("router_ap_router_ip", "10.43.0.2")
    RouterProxyHandler.alias_ip = cfg.get("router_ap_alias_ip", "192.168.100.2")
    server = HTTPServer((host, port), RouterProxyHandler)
    server.serve_forever()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8092
    run_proxy(p)
