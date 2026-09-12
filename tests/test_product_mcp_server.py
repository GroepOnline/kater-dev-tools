from __future__ import annotations

import json
import time

import pytest
from starlette.testclient import TestClient

from kater.mcp.product_server import build_product_mcp_app
from kater.resource_auth import AuthUnavailable, InvalidToken, ResourceAuthConfig, ResourcePrincipal

ISSUER = "https://auth.example.test"
RESOURCE = "https://tools.example.test/mcp"
SCOPES = ("kater:read", "brain:read", "chefshare:read")


@pytest.fixture
def config() -> ResourceAuthConfig:
    return ResourceAuthConfig(
        enabled=True,
        issuer=ISSUER,
        resource=RESOURCE,
        allowed_scopes=SCOPES,
    )


def _principal(scopes: tuple[str, ...] = SCOPES) -> ResourcePrincipal:
    return ResourcePrincipal(
        issuer=ISSUER,
        subject="account-123",
        audience=RESOURCE,
        plane="internal",
        scopes=frozenset(scopes),
        expires_at=int(time.time()) + 300,
    )


def _install_introspection(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def introspect(_self: object, token: str) -> ResourcePrincipal:
        calls.append(token)
        if token == "revoked":
            raise InvalidToken()
        if token == "down":
            raise AuthUnavailable()
        if token == "partial":
            return _principal(("kater:read",))
        return _principal()

    monkeypatch.setattr("kater.mcp.product_server.IntrospectionClient.introspect", introspect)
    return calls


def _rpc(client: TestClient, method: str, params: dict | None, token: str | None = None):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={
            "Authorization": f"Bearer {token or 'good'}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )


def test_metadata_and_initialize_are_current_streamable_http(config, monkeypatch):
    calls = _install_introspection(monkeypatch)
    app = build_product_mcp_app(config)
    with TestClient(app, base_url="https://tools.example.test") as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        initialized = _rpc(
            client,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == RESOURCE
    assert metadata.json()["authorization_servers"] == [ISSUER]
    assert metadata.json()["scopes_supported"] == list(SCOPES)
    assert initialized.status_code == 200
    assert initialized.json()["result"]["serverInfo"]["name"] == "chefgroep-workspace"
    assert calls == ["good"]


def test_list_is_exact_and_preserves_openai_security_schemes(config, monkeypatch):
    calls = _install_introspection(monkeypatch)
    app = build_product_mcp_app(config)
    with TestClient(app, base_url="https://tools.example.test") as client:
        response = _rpc(client, "tools/list", {})
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "kater_status",
        "kater_tool_search",
        "brain_query",
        "brain_doctor",
        "chefshare_list",
        "chefshare_meta",
    }
    for tool in tools:
        assert tool["securitySchemes"] == tool["_meta"]["securitySchemes"]
        assert tool["annotations"]["readOnlyHint"] is True
    assert calls == ["good"]


def test_call_is_reintrospected_and_revocation_denies_next_request(config, monkeypatch):
    calls = _install_introspection(monkeypatch)
    app = build_product_mcp_app(config)
    with TestClient(app, base_url="https://tools.example.test") as client:
        first = _rpc(
            client, "tools/call", {"name": "kater_tool_search", "arguments": {"query": "read"}}
        )
        revoked = _rpc(
            client,
            "tools/call",
            {"name": "kater_tool_search", "arguments": {"query": "read"}},
            token="revoked",
        )
    assert first.status_code == 200
    assert first.json()["result"]["isError"] is False
    assert revoked.status_code == 401
    assert "resource_metadata" in revoked.headers["www-authenticate"]
    assert calls == ["good", "revoked"]


def test_scope_and_auth_infrastructure_fail_closed(config, monkeypatch):
    _install_introspection(monkeypatch)
    app = build_product_mcp_app(config)
    with TestClient(
        app, base_url="https://tools.example.test", raise_server_exceptions=False
    ) as client:
        partial = _rpc(client, "tools/list", {}, token="partial")
        denied = _rpc(
            client,
            "tools/call",
            {"name": "brain_query", "arguments": {"query": "private"}},
            token="partial",
        )
        unavailable = _rpc(client, "tools/list", {}, token="down")
    assert partial.status_code == 200
    assert {tool["name"] for tool in partial.json()["result"]["tools"]} == {
        "kater_status",
        "kater_tool_search",
    }
    assert denied.status_code == 200
    assert denied.json()["result"]["isError"] is True
    assert denied.json()["result"]["structuredContent"] == {"error": "insufficient_scope"}
    assert "mcp/www_authenticate" in denied.json()["result"]["_meta"]
    assert unavailable.status_code == 503


def test_missing_token_never_reaches_tool_registry(config, monkeypatch):
    calls = _install_introspection(monkeypatch)
    app = build_product_mcp_app(config)
    with TestClient(app, base_url="https://tools.example.test") as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    assert response.status_code == 401
    assert calls == []


def test_error_payload_never_reflects_bearer(config, monkeypatch):
    _install_introspection(monkeypatch)
    app = build_product_mcp_app(config)
    with TestClient(
        app, base_url="https://tools.example.test", raise_server_exceptions=False
    ) as client:
        response = _rpc(client, "tools/list", {}, token="down")
    assert "down" not in response.text
    assert json.loads(response.text) == {"error": "auth_unavailable"}


@pytest.mark.parametrize(
    "resource",
    [
        "https://tools.example.test/sse",
        "https://tools.example.test/mcp/",
        "https://tools.example.test:443/mcp",
    ],
)
def test_product_requires_exact_canonical_mcp_resource(config, resource):
    with pytest.raises(ValueError):
        build_product_mcp_app(config.model_copy(update={"resource": resource}))


def test_openai_metadata_adapter_does_not_buffer_sse():
    import asyncio

    from kater.mcp.product_server import OpenAIToolSecurityMiddleware

    sent = []

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        assert len(sent) == 1
        await send({"type": "http.response.body", "body": b"data: first\n\n", "more_body": True})
        assert len(sent) == 2
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    asyncio.run(OpenAIToolSecurityMiddleware(app)({"type": "http"}, None, send))
    assert sent[1]["more_body"] is True


@pytest.mark.parametrize(
    "peer,expected_second_status",
    [("8.8.8.8", 429), ("127.0.0.1", 200)],
)
def test_rate_limit_uses_shared_gate_and_trusted_peer_policy(
    config, monkeypatch, peer, expected_second_status
):
    import asyncio

    from kater.mcp.product_server import ProductAuthMiddleware
    from kater.settings import RateLimiter

    monkeypatch.delenv("KATER_TRUST_PROXY", raising=False)
    monkeypatch.setattr("kater.api.server._rate_limiter", RateLimiter(1))
    introspections = _install_introspection(monkeypatch)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = ProductAuthMiddleware(app, config)

    async def request(forwarded):
        messages = []

        async def send(message):
            messages.append(message)

        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "client": (peer, 12345),
                "headers": [
                    (b"authorization", b"Bearer sensitive-token"),
                    (b"x-forwarded-for", forwarded),
                ],
            },
            None,
            send,
        )
        return messages

    first = asyncio.run(request(b"198.51.100.1"))
    second = asyncio.run(request(b"198.51.100.2"))
    assert first[0]["status"] == 200
    assert second[0]["status"] == expected_second_status
    assert len(introspections) == (1 if expected_second_status == 429 else 2)
    if expected_second_status == 429:
        assert json.loads(second[1]["body"]) == {"error": "rate_limit_exceeded"}
        assert b"sensitive-token" not in second[1]["body"]
        assert b"www-authenticate" not in dict(second[0]["headers"])
        assert dict(second[0]["headers"])[b"cache-control"] == b"no-store"


def test_metadata_uses_same_rate_limit_without_introspection(config, monkeypatch):
    from kater.settings import RateLimiter

    monkeypatch.setattr("kater.api.server._rate_limiter", RateLimiter(1))
    calls = _install_introspection(monkeypatch)
    with TestClient(build_product_mcp_app(config), base_url="https://tools.example.test") as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        limited = _rpc(client, "tools/list", {})
    assert metadata.status_code == 200
    assert limited.status_code == 429
    assert calls == []
