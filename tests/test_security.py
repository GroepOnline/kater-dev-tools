from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from kater.api import create_api_server


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", 9930)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.2)


def _get(port: int, path: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers=headers or {},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def _get_err(port: int, path: str, headers: dict | None = None) -> urllib.error.HTTPError:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers=headers or {},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        return e
    pytest.fail("Expected HTTPError")


def _post(port: int, path: str, body, headers: dict | None = None) -> dict:
    if isinstance(body, dict):
        body = json.dumps(body)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body.encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


# ── Settings redaction ────────────────────────────────────────────


def test_settings_does_not_leak_api_keys(api_server):
    _post(9930, "/api/settings", {
        "auth": {"mode": "apikey", "api_keys": ["secret-key-123"]}
    })
    data = _get(9930, "/api/settings", headers={
        "Authorization": "Bearer secret-key-123"
    })
    auth = data["auth"]
    assert auth["mode"] == "apikey"
    if isinstance(auth.get("api_keys"), int):
        assert auth["api_keys"] == 1
    else:
        assert "secret-key-123" not in json.dumps(auth)


def test_export_does_not_leak_api_keys(api_server):
    _post(9930, "/api/settings", {
        "auth": {"mode": "apikey", "api_keys": ["secret-key-456"]}
    })
    data = _get(9930, "/api/export", headers={
        "Authorization": "Bearer secret-key-456"
    })
    auth = data["auth"]
    assert "secret-key-456" not in json.dumps(auth)


def test_export_does_not_leak_server_credentials(api_server):
    import os

    try:
        _post(
            9930,
            "/api/mcp/servers/github/credentials",
            {"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "export-secret-789"}},
        )
        data = _get(9930, "/api/export")
        assert "export-secret-789" not in json.dumps(data)
        env = data["server_overrides"]["github"]["env"]
        assert env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "***"
    finally:
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)


# ── Auth enforcement ──────────────────────────────────────────────


def test_apikey_blocks_without_key(api_server):
    _post(9930, "/api/settings", {
        "auth": {"mode": "apikey", "api_keys": ["test-secret"]}
    })
    err = _get_err(9930, "/api/profiles")
    assert err.code == 401


def test_apikey_allows_with_valid_key(api_server):
    _post(9930, "/api/settings", {
        "auth": {"mode": "apikey", "api_keys": ["test-secret"]}
    })
    data = _get(9930, "/api/profiles", headers={
        "Authorization": "Bearer test-secret"
    })
    assert "core" in data["profiles"]


def test_oauth_blocks_invalid_token(api_server):
    _post(9930, "/api/settings", {"auth": {"mode": "oauth"}})
    err = _get_err(9930, "/api/profiles", headers={
        "Authorization": "Bearer tok_nonexistent"
    })
    assert err.code == 401


def test_oauth_allows_valid_token(api_server):
    from kater.oauth import create_token

    token = create_token("test_client", "tools", "core")
    _post(9930, "/api/settings", {"auth": {"mode": "oauth"}})
    data = _get(9930, "/api/profiles", headers={
        "Authorization": f"Bearer {token['access_token']}"
    })
    assert "core" in data["profiles"]


def test_health_always_open(api_server):
    _post(9930, "/api/settings", {
        "auth": {"mode": "apikey", "api_keys": ["test-secret"]}
    })
    data = _get(9930, "/health")
    assert data["status"] == "ok"


# ── OAuth redirect_uri validation ─────────────────────────────────


def test_oauth_redirect_uri_validated(api_server):
    reg = _post(9930, "/register",
        json.dumps({
            "client_name": "TestApp",
            "redirect_uris": ["https://app.example.com/callback"]
        }),
    )
    err = _get_err(9930,
        f"/authorize?client_id={reg['client_id']}"
        f"&redirect_uri=https://evil.com/callback"
        f"&code_challenge=test&code_challenge_method=S256"
    )
    assert err.code in (400, 403, 401)


def test_oauth_redirect_uri_allowed(api_server):
    reg = _post(9930, "/register",
        json.dumps({
            "client_name": "TestApp",
            "redirect_uris": ["https://app.example.com/callback"]
        }),
    )
    resp = urllib.request.urlopen(
        f"http://127.0.0.1:9930/authorize?client_id={reg['client_id']}"
        f"&redirect_uri=https://app.example.com/callback"
        f"&code_challenge=test&code_challenge_method=S256"
    )
    body = resp.read().decode()
    assert "Allow" in body


# ── API error codes ───────────────────────────────────────────────


def test_unknown_chain_returns_400(api_server):
    req = urllib.request.Request(
        "http://127.0.0.1:9930/api/chains/run",
        data=json.dumps({"name": "nonexistent"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        assert e.code in (400, 404)
        return
    pytest.fail("Expected error")


def test_invalid_json_returns_400(api_server):
    req = urllib.request.Request(
        "http://127.0.0.1:9930/api/settings",
        data=b"not valid json{{{",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        assert e.code == 400
        return
    pytest.fail("Expected 400")


def test_body_size_limit(api_server):
    big_body = "x" * (2 * 1024 * 1024)
    req = urllib.request.Request(
        "http://127.0.0.1:9930/api/settings",
        data=json.dumps({"cors_origins": [big_body]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        assert e.code in (400, 413)
        return
    except urllib.error.URLError as e:
        if "Broken pipe" in str(e.reason):
            return
        pytest.fail(f"Unexpected URLError: {e}")
    pytest.fail("Expected body size error")


# ── CORS ──────────────────────────────────────────────────────────


def test_cors_reflects_allowed_origin(api_server):
    _post(9930, "/api/settings", {
        "cors_origins": ["https://allowed.example.com"]
    })
    req = urllib.request.Request(
        "http://127.0.0.1:9930/api/profiles",
        headers={"Origin": "https://allowed.example.com"},
    )
    resp = urllib.request.urlopen(req)
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://allowed.example.com"


def test_cors_rejects_unallowed_origin(api_server):
    _post(9930, "/api/settings", {
        "cors_origins": ["https://allowed.example.com"]
    })
    req = urllib.request.Request(
        "http://127.0.0.1:9930/api/profiles",
        headers={"Origin": "https://evil.example.com"},
    )
    resp = urllib.request.urlopen(req)
    allow = resp.headers.get("Access-Control-Allow-Origin")
    assert allow != "https://evil.example.com"


# ── OAuth registration requires redirect_uris ─────────────────────


def test_validate_redirect_uri_rejects_empty():
    from kater.oauth import ClientRegistration, validate_redirect_uri

    client = ClientRegistration(client_id="c1", redirect_uris=[])
    assert validate_redirect_uri(client, "https://anything.example.com/cb") is False


def test_register_requires_redirect_uris():
    from kater.oauth import register_client

    with pytest.raises(ValueError):
        register_client("no-uris", [])


def test_api_register_without_uris_returns_400(api_server):
    req = urllib.request.Request(
        "http://127.0.0.1:9930/register",
        data=json.dumps({"client_name": "evil"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        assert e.code == 400
        return
    pytest.fail("Expected 400 for registration without redirect_uris")


# ── MCP transport (/sse) auth gate ────────────────────────────────


def _run_middleware(scope: dict, *, valid_key: str | None = None) -> tuple[bool, list]:
    from kater.mcp_server import AuthASGIMiddleware

    called = {"v": False}

    async def downstream(scope, receive, send):
        called["v"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    sent: list = []

    async def send(msg):
        sent.append(msg)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    mw = AuthASGIMiddleware(downstream)
    asyncio.run(mw(scope, receive, send))
    return called["v"], sent


def test_mcp_sse_blocks_without_auth():
    from kater.settings import AuthConfig, KaterSettings, save_settings

    save_settings(KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["k-secret"])))
    scope = {"type": "http", "headers": [], "query_string": b""}
    called, sent = _run_middleware(scope)
    assert called is False
    assert sent and sent[0]["status"] == 401


def test_mcp_sse_allows_with_valid_key():
    from kater.settings import AuthConfig, KaterSettings, save_settings

    save_settings(KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["k-secret"])))
    scope = {
        "type": "http",
        "headers": [(b"authorization", b"Bearer k-secret")],
        "query_string": b"",
    }
    called, sent = _run_middleware(scope)
    assert called is True


def test_mcp_sse_passthrough_when_auth_none():
    from kater.settings import AuthConfig, KaterSettings, save_settings

    save_settings(KaterSettings(auth=AuthConfig(mode="none")))
    scope = {"type": "http", "headers": [], "query_string": b""}
    called, _ = _run_middleware(scope)
    assert called is True


# ── Unified auth gate (one rule, three callers) ───────────────────


def test_authgate_allows_public_api_path():
    from kater.authgate import AuthContext, authenticate
    from kater.settings import AuthConfig, KaterSettings

    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["k"]))
    for path in ("/health", "/authorize", "/.well-known/oauth-authorization-server"):
        decision = authenticate(AuthContext(settings=settings, path=path))
        assert decision.allowed is True


def test_authgate_blocks_protected_path_without_key():
    from kater.authgate import AuthContext, authenticate
    from kater.settings import AuthConfig, KaterSettings

    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["k"]))
    decision = authenticate(AuthContext(settings=settings, path="/api/profiles"))
    assert decision.allowed is False


def test_authgate_unknown_mode_fails_closed():
    from kater.authgate import AuthContext, authenticate
    from kater.settings import AuthConfig, KaterSettings

    settings = KaterSettings(auth=AuthConfig(mode="weird"))
    decision = authenticate(
        AuthContext(settings=settings, authorization_header="Bearer x")
    )
    assert decision.allowed is False


def test_authgate_no_public_paths_for_mcp_transport():
    # MCP/WebSocket leave path=None, so the API allowlist must not apply.
    from kater.authgate import AuthContext, authenticate
    from kater.settings import AuthConfig, KaterSettings

    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=["k"]))
    decision = authenticate(AuthContext(settings=settings, path=None))
    assert decision.allowed is False


# ── ListenConfig SSOT ─────────────────────────────────────────────


def test_resolve_listen_config_precedence():
    from kater.settings import KaterSettings, resolve_listen_config

    settings = KaterSettings(host="0.0.0.0", api_port=1, mcp_port=2, ws_port=3)
    cfg = resolve_listen_config(host="127.0.0.1", settings=settings)
    assert cfg.host == "127.0.0.1"  # explicit override wins
    assert (cfg.api_port, cfg.mcp_port, cfg.ws_port) == (1, 2, 3)  # from settings


def test_listen_config_defaults_to_loopback():
    from kater.settings import ListenConfig

    assert ListenConfig().host == "127.0.0.1"


# ── Rate-limiter picks up settings changes ────────────────────────


def test_rate_limiter_reset_applies_new_limit():
    from kater import api
    from kater.settings import KaterSettings, save_settings

    try:
        save_settings(KaterSettings(rate_limit_per_min=5))
        api._reset_rate_limiter()
        assert api._get_rate_limiter().max_per_min == 5

        save_settings(KaterSettings(rate_limit_per_min=10))
        api._reset_rate_limiter()
        assert api._get_rate_limiter().max_per_min == 10
    finally:
        api._reset_rate_limiter()
