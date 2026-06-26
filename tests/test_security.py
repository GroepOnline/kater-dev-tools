from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from kater.api import create_api_server

KATER_DIR = Path.cwd() / ".kater"


@pytest.fixture(autouse=True)
def clean_state():
    from kater.oauth import reset_state
    from kater.storage import reset_db_cache

    reset_db_cache()
    reset_state()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)
    yield
    reset_db_cache()
    reset_state()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)


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
