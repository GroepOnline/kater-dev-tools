from __future__ import annotations

from kater.adapters.external import render_profile_config, scan_adapters
from kater.profiles import TOOL_SOURCES
from kater.proxy.manager import ProxyManager
from kater.proxy.sse_backend import SSEBackend


def test_sentry_catalog_uses_sse_and_bearer_header() -> None:
    sentry = next(source for source in TOOL_SOURCES if source.name == "sentry")

    assert sentry.mcp is not None
    assert sentry.mcp.url == "https://mcp.sentry.dev/sse"
    assert sentry.mcp.headers_template == {
        "Authorization": "Bearer ${SENTRY_AUTH_TOKEN}",
    }
    assert sentry.mcp.env_template == {}


def test_render_profile_config_sentry_includes_bearer_header(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sntry_test")

    config = render_profile_config("ops")
    sentry = config["mcpServers"]["sentry"]

    assert sentry["type"] == "sse"
    assert sentry["url"] == "https://mcp.sentry.dev/sse"
    assert sentry["headers"]["Authorization"] == "Bearer sntry_test"
    assert "env" not in sentry


def test_render_profile_config_sentry_redacts_token_when_secrets_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "supersecret-sentry-token")

    safe = render_profile_config("ops", include_secrets=False)
    sentry = safe["mcpServers"]["sentry"]

    assert sentry["headers"]["Authorization"] == "Bearer ${SENTRY_AUTH_TOKEN}"
    assert "supersecret-sentry-token" not in str(sentry)


def test_scan_adapters_sentry_configured_with_auth_token(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sntry_test")

    inventory = scan_adapters({"ops"})
    sentry = next(a for a in inventory.sources if a.source.name == "sentry")

    assert sentry.configured is True
    assert sentry.launch_hint is not None
    assert sentry.launch_hint["headers"]["Authorization"] == "Bearer sntry_test"
    assert "env" not in sentry.launch_hint


def test_proxy_manager_creates_sse_backend_for_sentry(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sntry_test")

    manager = ProxyManager()
    source = next(item for item in TOOL_SOURCES if item.name == "sentry")
    backend = manager._create_backend(source)

    assert isinstance(backend, SSEBackend)
    assert backend._url == "https://mcp.sentry.dev/sse"
    assert backend._headers["Authorization"] == "Bearer sntry_test"
