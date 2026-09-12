from __future__ import annotations

import json
import socket
import time
from contextlib import ExitStack
from http.client import HTTPConnection

import pytest

from kater.resource_auth import (
    AuthUnavailable,
    InvalidToken,
    ResourceAuthConfig,
    ResourceAuthConfigurationError,
    ResourcePrincipal,
)
from kater.runtime import KaterRuntime
from kater.settings import KaterSettings, load_settings, resolve_listen_config, save_settings

ISSUER = "https://auth.example.test"
RESOURCE = "https://tools.example.test/mcp"
SCOPES = ("kater:read", "brain:read", "chefshare:read")


def _contract() -> ResourceAuthConfig:
    return ResourceAuthConfig(enabled=True, issuer=ISSUER, resource=RESOURCE, allowed_scopes=SCOPES)


@pytest.fixture
def product_settings(monkeypatch):
    monkeypatch.setenv("KATER_RESOURCE_AUTH_SERVICE_KEY", "test-service-key-" + "x" * 32)
    with ExitStack() as stack:
        sockets = [stack.enter_context(socket.create_server(("127.0.0.1", 0))) for _ in range(4)]
        ports = [sock.getsockname()[1] for sock in sockets]
    settings = KaterSettings(
        resource_auth=_contract(),
        api_port=ports[0],
        mcp_port=ports[1],
        ws_port=ports[2],
        product_mcp_port=ports[3],
    )
    save_settings(settings)
    return settings


def _request(port, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_product_runtime_real_socket_health_revocation_and_shutdown(product_settings, monkeypatch):
    revoked = False
    unavailable = False
    calls = []

    def introspect(_self, token):
        calls.append(token)
        if unavailable:
            raise AuthUnavailable()
        if token == "kater-readiness-deliberately-invalid" or revoked:
            raise InvalidToken()
        return ResourcePrincipal(
            issuer=ISSUER,
            subject="account-1",
            audience=RESOURCE,
            plane="internal",
            scopes=frozenset(SCOPES),
            expires_at=int(time.time()) + 120,
        )

    def check_readiness(_self):
        if unavailable:
            raise AuthUnavailable()
        return True

    monkeypatch.setattr("kater.mcp.product_server.IntrospectionClient.introspect", introspect)
    monkeypatch.setattr(
        "kater.mcp.product_server.IntrospectionClient.check_readiness", check_readiness
    )
    runtime = KaterRuntime()
    settings = product_settings
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    headers = {
        "Authorization": "Bearer same-token",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    try:
        runtime.start()
        runtime.start()  # Idempotent; no duplicate listeners.
        code, metadata = _request(
            settings.product_mcp_port, "GET", "/.well-known/oauth-protected-resource/mcp"
        )
        assert code == 200 and metadata["resource"] == RESOURCE
        code, listing = _request(settings.product_mcp_port, "POST", "/mcp", body, headers)
        assert code == 200 and len(listing["result"]["tools"]) == 6
        code, health = _request(settings.api_port, "GET", "/health/ready")
        assert code == 200 and health["components"]["product_mcp"]["status"] == "ok"
        with socket.create_connection(("127.0.0.1", settings.mcp_port), timeout=1):
            pass  # Private MCP listener remains independently available.
        revoked = True
        code, denied = _request(settings.product_mcp_port, "POST", "/mcp", body, headers)
        assert code == 401 and denied == {"error": "invalid_token"}
        assert calls.count("same-token") == 2
        unavailable = True
        code, health = _request(settings.api_port, "GET", "/health/ready")
        assert code == 503 and health["components"]["product_mcp"]["status"] == "unavailable"
        runtime._product_uvicorn.should_exit = True
        runtime._product_thread.join(timeout=3)
        code, health = _request(settings.api_port, "GET", "/health/ready")
        assert code == 503 and health["components"]["product_mcp"]["status"] == "unavailable"
    finally:
        runtime.stop()
    for port in (settings.api_port, settings.mcp_port, settings.ws_port, settings.product_mcp_port):
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.2)


def test_product_missing_key_fails_before_listener_start(product_settings, monkeypatch):
    monkeypatch.delenv("KATER_RESOURCE_AUTH_SERVICE_KEY")
    runtime = KaterRuntime()
    with pytest.raises(ResourceAuthConfigurationError):
        runtime.start()
    assert runtime._api_server is None
    assert runtime._product_thread is None


def test_product_port_collision_stops_other_listeners(product_settings):
    with socket.create_server(("127.0.0.1", product_settings.product_mcp_port)):
        runtime = KaterRuntime()
        with pytest.raises(OSError):
            runtime.start()
        assert runtime._started is False
        for port in (
            product_settings.api_port,
            product_settings.mcp_port,
            product_settings.ws_port,
        ):
            with pytest.raises(OSError):
                socket.create_connection(("127.0.0.1", port), timeout=0.2)


def test_product_cannot_reuse_private_port(product_settings):
    settings = product_settings.model_copy(update={"product_mcp_port": product_settings.mcp_port})
    save_settings(settings)
    with pytest.raises(ValueError, match="dedicated listener"):
        KaterRuntime().start()


def test_product_env_overrides_persisted_contract(tmp_path, monkeypatch):
    save_settings(KaterSettings(), tmp_path)
    monkeypatch.setenv("KATER_RESOURCE_AUTH_ENABLED", "1")
    monkeypatch.setenv("KATER_RESOURCE_AUTH_ISSUER", ISSUER)
    monkeypatch.setenv("KATER_RESOURCE_AUTH_RESOURCE", RESOURCE)
    monkeypatch.setenv("KATER_RESOURCE_AUTH_SCOPES", " ".join(SCOPES))
    monkeypatch.setenv("KATER_RESOURCE_AUTH_SERVICE_KEY_ENV", "SERVICE_AUTH_KEY")
    monkeypatch.setenv("KATER_PRODUCT_MCP_PORT", "19093")
    settings = load_settings(tmp_path)
    assert settings.resource_auth.enabled
    assert settings.resource_auth.issuer == ISSUER
    assert settings.resource_auth.resource == RESOURCE
    assert settings.resource_auth.allowed_scopes == SCOPES
    assert settings.resource_auth.service_key_env == "SERVICE_AUTH_KEY"
    assert resolve_listen_config(settings=settings).product_mcp_port == 19093
    assert settings.mcp_port == 9090


@pytest.mark.parametrize(
    "key,value",
    [
        ("KATER_RESOURCE_AUTH_ENABLED", "enabled"),
        ("KATER_RESOURCE_AUTH_ENABLED", "1"),
        ("KATER_RESOURCE_AUTH_ISSUER", "http://insecure.example"),
        ("KATER_RESOURCE_AUTH_SERVICE_KEY_ENV", "bad key"),
        ("KATER_PRODUCT_MCP_PORT", "0"),
        ("KATER_PRODUCT_MCP_PORT", "65536"),
        ("KATER_PRODUCT_MCP_PORT", "invalid"),
    ],
)
def test_invalid_product_env_is_never_silently_disabled(tmp_path, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ResourceAuthConfigurationError):
        load_settings(tmp_path)


def test_disabled_product_does_not_start_listener(product_settings):
    product_settings.resource_auth = ResourceAuthConfig()
    save_settings(product_settings)
    with KaterRuntime() as runtime:
        assert runtime._product_thread is None
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", product_settings.product_mcp_port), timeout=0.2)
