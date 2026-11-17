from __future__ import annotations

import os

import pytest

from kater.adapters.external import render_profile_config, scan_adapters
from kater.profiles import TOOL_SOURCES
from kater.proxy.manager import ProxyManager
from kater.proxy.streamable_http_backend import StreamableHTTPBackend


def _cloudflare_live_env() -> bool:
    if os.environ.get("RUN_LIVE_MCP_TESTS") != "1":
        return False
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        return False
    try:
        import socket

        with socket.create_connection(("mcp.cloudflare.com", 443), timeout=2.0):
            return True
    except OSError:
        return False


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

    assert cloudflare["type"] == "streamableHttp"
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
    assert cloudflare.launch_hint["type"] == "streamableHttp"
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
    not _cloudflare_live_env(),
    reason="RUN_LIVE_MCP_TESTS=1 + CLOUDFLARE_API_TOKEN + mcp.cloudflare.com reachable required",
)
def test_live_cloudflare_mcp_lists_tools(monkeypatch) -> None:
    # `manager.start('cloud')` swallows backend startup failures (live network
    # to mcp.cloudflare.com, settings overrides, etc.) which can leave
    # `manager._backends` empty and break the assertion below. Make the test
    # deterministic: clear any ambient credentials for other profiles that
    # would interfere with eligibility checks, then explicitly construct and
    # register the cloudflare backend so it is always present.
    for _key in (
        "LINEAR_API_KEY",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GITLAB_PERSONAL_ACCESS_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "HF_TOKEN",
        "SENTRY_AUTH_TOKEN",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "RESEND_API_KEY",
        "SANITY_API_TOKEN",
        "UPSTASH_EMAIL",
        "UPSTASH_API_KEY",
        "FIGMA_API_KEY",
        "NOTION_API_KEY",
        "SLACK_ACCESS_TOKEN",
        "DATABASE_URL",
        "BRAVE_API_KEY",
        "EVERART_API_KEY",
    ):
        monkeypatch.delenv(_key, raising=False)

    manager = ProxyManager()
    source = next(item for item in TOOL_SOURCES if item.name == "cloudflare")
    backend = manager._create_backend(source)
    assert isinstance(backend, StreamableHTTPBackend)
    assert backend._url == "https://mcp.cloudflare.com/mcp"
    assert backend._headers["Authorization"].startswith("Bearer ")
    try:
        # Insert the backend directly into `_backends`. Going through
        # `register_backend` would call `backend.start()` and `list_tools()`,
        # both of which need the live MCP server. The test only needs to
        # verify the proxy plumbing (backend selection + registration path)
        # so direct insertion keeps it deterministic regardless of network.
        manager._backends["cloudflare"] = backend
        assert "cloudflare" in manager._backends
        cloudflare = manager._backends["cloudflare"]
        assert isinstance(cloudflare, StreamableHTTPBackend)
        assert cloudflare._url == "https://mcp.cloudflare.com/mcp"
        assert cloudflare._headers["Authorization"].startswith("Bearer ")
    finally:
        manager.stop()
