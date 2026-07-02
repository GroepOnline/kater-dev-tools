from __future__ import annotations

import http.server
import json
import os
import threading

import pytest

from kater.adapters.external import render_profile_config, scan_adapters
from kater.profiles import TOOL_SOURCES
from kater.proxy.base import MockBackend
from kater.proxy.manager import ProxyManager
from kater.proxy.streamable_http_backend import StreamableHTTPBackend


def test_linear_catalog_uses_streamable_http_and_bearer_header() -> None:
    linear = next(source for source in TOOL_SOURCES if source.name == "linear")

    assert linear.mcp is not None
    assert linear.mcp.url == "https://mcp.linear.app/mcp"
    assert linear.mcp.headers_template == {
        "Authorization": "Bearer ${LINEAR_API_KEY}",
    }


def test_render_profile_config_linear_includes_bearer_header(monkeypatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")

    config = render_profile_config("ops")
    linear = config["mcpServers"]["linear"]

    assert linear["type"] == "http"
    assert linear["url"] == "https://mcp.linear.app/mcp"
    assert linear["headers"]["Authorization"] == "Bearer lin_api_test"


def test_scan_adapters_linear_configured_with_api_key(monkeypatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")

    inventory = scan_adapters({"ops"})
    linear = next(a for a in inventory.sources if a.source.name == "linear")

    assert linear.configured is True
    assert linear.launch_hint is not None
    assert linear.launch_hint["headers"]["Authorization"] == "Bearer lin_api_test"


def test_streamable_http_backend_initialize_and_list_tools():
    calls: list[dict] = []

    class _FakeStreamableServer(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode() if length else "{}"
            calls.append(json.loads(body))
            method = calls[-1].get("method")
            rid = calls[-1].get("id")
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            resp = {"jsonrpc": "2.0", "id": rid}
            if method == "initialize":
                resp["result"] = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "linear", "version": "1"},
                    "capabilities": {"tools": {}},
                }
            elif method == "tools/list":
                resp["result"] = {
                    "tools": [
                        {
                            "name": "list_issues",
                            "description": "List issues",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                }
            else:
                resp["result"] = {}
            payload = f"event: message\ndata: {json.dumps(resp)}\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(payload.encode())

    httpd = http.server.HTTPServer(("127.0.0.1", 0), _FakeStreamableServer)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        backend = StreamableHTTPBackend(
            name="linear",
            url=f"http://127.0.0.1:{port}/mcp",
            headers={"Authorization": "Bearer test"},
        )
        backend.start()
        assert backend.is_healthy()
        assert [tool.name for tool in backend.list_tools()] == ["list_issues"]
        assert calls[0]["method"] == "initialize"
        assert calls[1]["method"] == "notifications/initialized"
        assert calls[2]["method"] == "tools/list"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_proxy_manager_creates_streamable_backend_for_linear(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")

    manager = ProxyManager()
    source = next(item for item in TOOL_SOURCES if item.name == "linear")
    backend = manager._create_backend(source)

    assert isinstance(backend, StreamableHTTPBackend)
    assert backend._url == "https://mcp.linear.app/mcp"
    assert backend._headers["Authorization"] == "Bearer lin_api_test"


def test_proxy_manager_starts_linear_without_default_enabled(monkeypatch):
    """Linear has default_enabled=False but must still start when env is set."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    linear = next(source for source in TOOL_SOURCES if source.name == "linear")
    assert linear.default_enabled is False

    def fake_create(self, source):
        if source.name == "linear":
            return MockBackend(tools=[{"name": "list_issues"}])
        return None

    monkeypatch.setattr(ProxyManager, "_create_backend", fake_create)
    monkeypatch.setattr(
        "kater.proxy.manager.all_tool_sources",
        lambda: (linear,),
    )

    manager = ProxyManager()
    manager.start("ops")
    try:
        assert "linear" in manager._backends
    finally:
        manager.stop()


@pytest.mark.skipif(
    not os.environ.get("LINEAR_API_KEY"),
    reason="Set LINEAR_API_KEY to exercise live Linear MCP",
)
def test_live_linear_mcp_lists_tools():
    manager = ProxyManager()
    manager.start("ops")
    try:
        assert "linear" in manager._backends
        linear = manager._backends["linear"]
        assert linear.is_healthy(), linear.status.error
        tools = linear.list_tools()
        assert len(tools) > 0
    finally:
        manager.stop()
