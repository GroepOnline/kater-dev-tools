from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest

from kater import mcp_server
from kater.settings import AuthConfig, KaterSettings, save_settings


def test_mcp_missing_package_message() -> None:
    with (
        patch("kater.mcp_server.import_module", side_effect=ModuleNotFoundError("mcp")),
        pytest.raises(mcp_server.McpUnavailableError) as exc_info,
    ):
        mcp_server.create_server()

    assert "uv sync" in str(exc_info.value)


def test_mcp_registers_core_tools() -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
        TransportSecuritySettings=Mock(side_effect=lambda **kw: kw),
    )

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        server = mcp_server.create_server(profile="core")

    assert server is fake_server
    registered = [call.kwargs["name"] for call in fake_server.tool.call_args_list]
    assert "kater_profiles" in registered
    assert "kater_doctor" in registered


def test_create_server_allowlists_tunnel_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    security_ctor = Mock(side_effect=lambda **kw: ("security", kw))
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
        TransportSecuritySettings=security_ctor,
    )
    monkeypatch.setenv("KATER_DOMAIN", "kater.example.com")
    monkeypatch.setenv("KATER_HTTPS_HOSTS", "kater.example.com,alt.example.com")

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        mcp_server.create_server(profile="core")

    assert fake_module.FastMCP.call_args.kwargs["transport_security"][0] == "security"
    settings = fake_module.FastMCP.call_args.kwargs["transport_security"][1]
    assert settings["enable_dns_rebinding_protection"] is True
    assert "127.0.0.1:*" in settings["allowed_hosts"]
    assert "kater.example.com" in settings["allowed_hosts"]
    assert "kater.example.com:*" in settings["allowed_hosts"]
    assert "alt.example.com" in settings["allowed_hosts"]
    assert "https://kater.example.com" in settings["allowed_origins"]


def test_create_server_does_not_start_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(
        FastMCP=Mock(return_value=fake_server),
        TransportSecuritySettings=Mock(side_effect=lambda **kw: kw),
    )
    proxy_start = Mock()
    monkeypatch.setattr(
        "kater.proxy.get_proxy",
        lambda: Mock(start=proxy_start, list_tools=Mock(return_value=[])),
    )

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        mcp_server.create_server(profile="core")

    proxy_start.assert_not_called()


def test_mcp_rate_limit_ignores_spoofed_xff_from_public_peer(monkeypatch, tmp_path) -> None:
    seen_clients: list[str] = []

    class FakeLimiter:
        def check(self, client_ip: str) -> bool:
            seen_clients.append(client_ip)
            return False

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_TRUST_PROXY", raising=False)
    monkeypatch.setattr("kater.api.server._rate_limiter", FakeLimiter())
    monkeypatch.chdir(tmp_path)
    save_settings(KaterSettings(auth=AuthConfig(mode="none")))

    async def app(scope, receive, send):
        raise AssertionError("rate limit should stop request")

    mw = mcp_server.AuthASGIMiddleware(app)
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    asyncio.run(
        mw(
            {
                "type": "http",
                "path": "/sse",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"198.51.100.1")],
                "client": ("8.8.8.8", 12345),
            },
            receive,
            send,
        )
    )

    assert seen_clients == ["8.8.8.8"]
    assert sent[0]["status"] == 429
