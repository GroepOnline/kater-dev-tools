from __future__ import annotations

import base64
import hashlib
import json
import shutil
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from kater.api import create_api_server
from kater.oauth import (
    cleanup_expired,
    create_auth_code,
    create_token,
    discovery_metadata,
    exchange_code,
    get_client,
    register_client,
    render_consent_page,
    reset_state,
    resource_metadata,
    revoke_token,
    validate_token,
)

KATER_DIR = Path.cwd() / ".kater"


@pytest.fixture(autouse=True)
def clean_oauth():
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


def test_register_client():
    client = register_client("test-app", ["https://app.example.com/callback"])
    assert client.client_id.startswith("client_")
    assert client.client_secret is not None
    assert "test-app" == client.client_name
    assert "https://app.example.com/callback" in client.redirect_uris


def test_get_client():
    client = register_client("myapp", ["http://localhost:3000/cb"])
    loaded = get_client(client.client_id)
    assert loaded is not None
    assert loaded.client_name == "myapp"


def test_get_client_not_found():
    assert get_client("nonexistent") is None


def test_full_auth_code_flow():
    client = register_client("chatgpt", ["https://chat.openai.com/cb"])

    verifier = "test-verifier-1234567890"
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")

    code = create_auth_code(
        client_id=client.client_id,
        redirect_uri="https://chat.openai.com/cb",
        code_challenge=challenge,
        code_challenge_method="S256",
        scope="tools",
        state="abc123",
        profile="ops",
    )
    assert code.startswith("code_")

    token = exchange_code(code, client.client_id, verifier)
    assert token is not None
    assert token["access_token"].startswith("tok_")
    assert token["token_type"] == "Bearer"
    assert token["expires_in"] > 0


def test_exchange_code_used():
    client = register_client("app", ["http://localhost/cb"])
    code = create_auth_code(
        client_id=client.client_id,
        redirect_uri="http://localhost/cb",
        code_challenge="verifier",
        code_challenge_method="plain",
    )
    token1 = exchange_code(code, client.client_id, "verifier")
    assert token1 is not None
    token2 = exchange_code(code, client.client_id, "verifier")
    assert token2 is None


def test_exchange_code_wrong_verifier():
    client = register_client("app", ["http://localhost/cb"])
    code = create_auth_code(
        client_id=client.client_id,
        redirect_uri="http://localhost/cb",
        code_challenge="correct",
        code_challenge_method="plain",
    )
    result = exchange_code(code, client.client_id, "wrong")
    assert result is None


def test_validate_token():
    token = create_token("client_x", "tools", "ops")
    at = validate_token(token["access_token"])
    assert at is not None
    assert at.client_id == "client_x"
    assert at.profile == "ops"


def test_validate_invalid_token():
    assert validate_token("tok_nonexistent") is None


def test_revoke_token():
    token = create_token("client_x", "tools")
    assert revoke_token(token["access_token"]) is True
    assert validate_token(token["access_token"]) is None
    assert revoke_token("nonexistent") is False


def test_discovery_metadata():
    meta = discovery_metadata("https://kater.example.com")
    assert meta["issuer"] == "https://kater.example.com"
    assert "/authorize" in meta["authorization_endpoint"]
    assert "/token" in meta["token_endpoint"]
    assert "/register" in meta["registration_endpoint"]
    assert "authorization_code" in meta["grant_types_supported"]
    assert "S256" in meta["code_challenge_methods_supported"]


def test_resource_metadata():
    meta = resource_metadata("https://kater.example.com")
    assert meta["resource"] == "https://kater.example.com"
    assert "tools" in meta["scopes_supported"]


def test_render_consent_page():
    html = render_consent_page(
        client_name="ChatGPT",
        redirect_uri="https://chat.openai.com/cb",
        state="xyz",
        authorize_url="https://kater.example.com/authorize?...",
        profile="ops",
    )
    assert "<!DOCTYPE html>" in html
    assert "ChatGPT" in html
    assert "Allow" in html
    assert "Deny" in html
    assert "ops" in html


def test_cleanup_expired():
    token = create_token("c", "tools", expires_in=0)
    time.sleep(0.1)
    count = cleanup_expired()
    assert count >= 1
    assert validate_token(token["access_token"]) is None


# ── API Integration ────────────────────────────────────────────────


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", 9920)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.2)


def _post_raw(
    port: int, path: str, body: str,
    content_type: str = "application/x-www-form-urlencoded",
) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body.encode(),
        headers={"Content-Type": content_type},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def test_api_discovery(api_server):
    resp = urllib.request.urlopen(
        "http://127.0.0.1:9920/.well-known/oauth-authorization-server"
    )
    data = json.loads(resp.read())
    assert "authorization_endpoint" in data
    assert "token_endpoint" in data


def test_api_resource_metadata(api_server):
    resp = urllib.request.urlopen(
        "http://127.0.0.1:9920/.well-known/oauth-protected-resource"
    )
    data = json.loads(resp.read())
    assert "resource" in data


def test_api_register_client(api_server):
    data = _post_raw(
        9920,
        "/register",
        json.dumps({"client_name": "ChatGPT", "redirect_uris": ["https://chat.openai.com/cb"]}),
        "application/json",
    )
    assert data["client_id"].startswith("client_")
    assert data["client_secret"]


def test_api_full_oauth_flow(api_server):
    reg = _post_raw(
        9920,
        "/register",
        json.dumps({"client_name": "ChatGPT", "redirect_uris": ["http://localhost/cb"]}),
        "application/json",
    )

    import base64 as b64
    import hashlib as hl

    verifier = "verifier12345678901234567890"
    challenge = b64.urlsafe_b64encode(
        hl.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")

    code = create_auth_code(
        client_id=reg["client_id"],
        redirect_uri="http://localhost/cb",
        code_challenge=challenge,
        code_challenge_method="S256",
        profile="ops",
    )

    token = _post_raw(
        9920,
        "/token",
        f"grant_type=authorization_code&code={code}"
        f"&client_id={reg['client_id']}&code_verifier={verifier}",
    )
    assert token["access_token"].startswith("tok_")
    assert token["token_type"] == "Bearer"
