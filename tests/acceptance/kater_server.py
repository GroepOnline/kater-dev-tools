"""Minimal acceptance-only HTTP facade over Kater's production Computer path."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kater.capabilities.computer import (
    ComputerConnector,
    load_computer_manifests_from_udo,
    revoke_computer_capability,
)
from kater.capabilities.registry import CapabilityRegistry
from kater.capabilities.store import get_capability, upsert_capability
from kater.proxy.manager import ProxyManager


def build() -> tuple[CapabilityRegistry, ProxyManager]:
    checkout = Path(os.environ["KATER_UDO_CHECKOUT"])
    digest = os.environ["GENERATED_CONTRACT_DIGEST"]
    manifests = load_computer_manifests_from_udo(checkout, expected_digest=digest)
    registry = CapabilityRegistry()
    for manifest in manifests:
        upsert_capability(manifest)
        registry.register(get_capability(manifest.capability_id, manifest.version) or manifest)
    connector = ComputerConnector(
        manifests,
        registry,
        base_url=os.environ["GUEST_ORIGIN"],
        auth_token=os.environ["GUEST_AGENT_TOKEN"],
    )
    proxy = ProxyManager()
    proxy.register_computer_connector(connector)
    return registry, proxy


class Handler(BaseHTTPRequestHandler):
    registry: CapabilityRegistry
    proxy: ProxyManager

    def _json(self, status: int, value: object) -> None:
        raw = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("body must be an object")
        return value

    def do_GET(self) -> None:
        if self.path == "/tools/list":
            self._json(200, {"tools": self.proxy.list_tools()})
            return
        if self.path.startswith("/capabilities/status?"):
            from urllib.parse import parse_qs, urlsplit

            query = parse_qs(urlsplit(self.path).query)
            capability_id = query.get("capability_id", [""])[0]
            version = query.get("version", ["1.0.0"])[0]
            manifest = get_capability(capability_id, version)
            self._json(
                200,
                {
                    "capability_id": capability_id,
                    "version": version,
                    "lifecycle_state": (
                        manifest.lifecycle_state.value if manifest is not None else None
                    ),
                },
            )
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        try:
            body = self._body()
            if self.path == "/tools/call":
                name = body.get("name")
                arguments = body.get("arguments")
                if not isinstance(name, str) or not isinstance(arguments, dict):
                    raise ValueError("name and arguments are required")
                self._json(200, self.proxy.call_tool(name, arguments))
                return
            if self.path == "/capabilities/revoke":
                capability_id = body.get("capability_id")
                version = body.get("version", "1.0.0")
                if not isinstance(capability_id, str) or not isinstance(version, str):
                    raise ValueError("capability_id and version are required")
                revoke_computer_capability(self.registry, capability_id, version)
                self._json(200, {"revoked": capability_id})
                return
            self._json(404, {"error": "not_found"})
        except Exception as error:
            self._json(400, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    registry, proxy = build()
    Handler.registry, Handler.proxy = registry, proxy
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ["KATER_PORT"])), Handler)
    try:
        server.serve_forever()
    finally:
        proxy.stop()
        server.server_close()


if __name__ == "__main__":
    main()
