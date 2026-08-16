from __future__ import annotations

import os

import pytest

from kater.adapters.external import render_profile_config, scan_adapters
from kater.profiles import TOOL_SOURCES
from kater.proxy.manager import ProxyManager
from kater.proxy.streamable_http_backend import StreamableHTTPBackend


def test_cloudflare_catalog_uses_streamable_http_and_bearer_header() -> None:
    cloudflare = next(source for source in TOOL_SOURCES if source.name == "cloudflare")

    assert cloudflare.mcp is not None
    assert cloudflare.transport.value == "http"
    assert cloudflare.mcp.url == "https://mcp.cloudflare.com/mcp"
    assert cloudflare.mcp.headers_template == {
        "Authorization": "Bearer ${CLOUDFLARE_API_TOKEN}",
    }
    assert cloudflare.mcp.env_template == {}


def test_render_profile_config_cloudflare_includes_bearer_header(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf_api_test")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")

    config = render_profile_config("cloud")
    cloudflare = config["mcpServers"]["cloudflare"]

    assert cloudflare["type"] == "http"
    assert cloudflare["url"] == "https://mcp.cloudflare.com/mcp"
    assert cloudflare["headers"]["Authorization"] == "Bearer cf_api_test"
    assert "env" not in cloudflare


def test_scan_adapters_cloudflare_configured_with_api_token(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf_api_test")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")

    inventory = scan_adapters({"cloud"})
    cloudflare = next(a for a in inventory.sources if a.source.name == "cloudflare")

    assert cloudflare.configured is True
    assert cloudflare.launch_hint is not None
    assert cloudflare.launch_hint["type"] == "http"
    assert cloudflare.launch_hint["url"] == "https://mcp.cloudflare.com/mcp"
    assert cloudflare.launch_hint["headers"]["Authorization"] == "Bearer cf_api_test"


def test_scan_adapters_cloudflare_launch_hint_without_live_token() -> None:
    inventory = scan_adapters({"cloud"}, include_secrets=False)
    cloudflare = next(a for a in inventory.sources if a.source.name == "cloudflare")

    assert cloudflare.launch_hint is not None
    assert cloudflare.launch_hint["headers"]["Authorization"] == "Bearer ${CLOUDFLARE_API_TOKEN}"


def test_proxy_manager_creates_streamable_backend_for_cloudflare(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf_api_test")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")

    manager = ProxyManager()
    source = next(item for item in TOOL_SOURCES if item.name == "cloudflare")
    backend = manager._create_backend(source)

    assert isinstance(backend, StreamableHTTPBackend)
    assert backend._url == "https://mcp.cloudflare.com/mcp"
    assert backend._headers["Authorization"] == "Bearer cf_api_test"


@pytest.mark.skipif(
    not os.environ.get("CLOUDFLARE_API_TOKEN"),
    reason="Set CLOUDFLARE_API_TOKEN to exercise live Cloudflare MCP",
)
def test_live_cloudflare_mcp_lists_tools():
    manager = ProxyManager()
    manager.start("cloud")
    try:
        assert "cloudflare" in manager._backends
        cloudflare = manager._backends["cloudflare"]
        assert cloudflare.is_healthy(), cloudflare.status.error
        tools = cloudflare.list_tools()
        assert len(tools) > 0
    finally:
        manager.stop()
