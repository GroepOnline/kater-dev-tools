from __future__ import annotations

from kater.authgate import should_proxy_to_api


def test_should_proxy_dashboard_paths() -> None:
    assert should_proxy_to_api("/")
    assert should_proxy_to_api("/dashboard")
    assert should_proxy_to_api("/api/status")


def test_should_not_proxy_mcp_paths() -> None:
    assert not should_proxy_to_api("/sse")
    assert not should_proxy_to_api("/messages")
