"""Locks in the security hardening fixes from the full audit.

Covers: XSS escaping in the consent page, redirect_uri scheme validation,
client_secret verification for confidential clients, registration-token
gating, admin-key separation for settings, rate limiting on the MCP/WS
transports, telemetry pruning/cap, OpenAPI drift, and KATER_PUBLIC truthy
visibility.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from kater.api import create_api_server
from kater.oauth import (
    AuthCodeRequest,
    register_client,
    render_consent_page,
)

KATER_DIR = Path.cwd() / ".kater"


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", 9970)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.2)


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


def _get_err_post(
    port: int, path: str, body, headers: dict | None = None
) -> urllib.error.HTTPError:
    if isinstance(body, dict):
        body = json.dumps(body)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body.encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        return e
    pytest.fail("Expected HTTPError")


# ── 1. XSS escaping in consent page ────────────────────────────────


def test_consent_page_escapes_state_attribute_injection():
    """state with quote/quote chars must not break out of the href attribute."""
    html = render_consent_page(
        client_name="App",
        redirect_uri="https://app.example.com/cb",
        state='x" onfocus=alert(1) autofocus x="',
        authorize_url="https://kater.example.com/authorize?x=1",
        profile="core",
    )
    # The raw injection payload must not appear unescaped.
    assert 'onfocus=alert' not in html
    assert 'x" onfocus' not in html
    # The Allow link must still carry an escaped state parameter.
    assert "state=" in html


def test_consent_page_escapes_client_name():
    html = render_consent_page(
        client_name="<script>alert(1)</script>",
        redirect_uri="https://app.example.com/cb",
        state=None,
        authorize_url="https://kater.example.com/authorize?x=1",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ── 2. redirect_uri scheme validation ──────────────────────────────


@pytest.mark.parametrize(
    "uri,ok",
    [
        ("https://app.example.com/cb", True),
        ("http://localhost:3000/cb", True),
        ("http://127.0.0.1:8080/cb", True),
        ("javascript:alert(1)", False),
        ("data:text/html,<script>", False),
        ("file:///etc/passwd", False),
        ("http://evil.com/cb", False),
    ],
)
def test_register_rejects_unsafe_redirect_schemes(uri, ok):
    if ok:
        client = register_client("app", [uri])
        assert uri in client.redirect_uris
    else:
        with pytest.raises(ValueError):
            register_client("app", [uri])


def test_api_register_rejects_javascript_uri(api_server):
    err = _get_err_post(
        9970,
        "/register",
        json.dumps({"client_name": "x", "redirect_uris": ["javascript:alert(1)"]}),
    )
    assert err.code == 400


# ── 3. client_secret verification (confidential clients) ───────────


def test_settings_change_blocked_without_admin_key(api_server, monkeypatch):
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    # A normal tool-credential must not be able to change settings.
    err = _get_err_post(
        9970,
        "/api/settings",
        json.dumps({"cors_origins": ["https://evil.com"]}),
        headers={"Authorization": "Bearer not-admin"},
    )
    assert err.code == 403


def test_settings_change_allowed_with_admin_key(api_server, monkeypatch):
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    req = urllib.request.Request(
        "http://127.0.0.1:9970/api/settings",
        data=json.dumps({"cors_origins": ["https://ok.com"]}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer admin-secret",
        },
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert resp.status == 200
    assert "https://ok.com" in data["cors_origins"]


def test_settings_change_works_without_admin_key_set(api_server, monkeypatch):
    """No admin key configured -> every authenticated caller is admin (local default)."""
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    data = _post(9970, "/api/settings", {"cors_origins": ["https://local.com"]})
    assert "https://local.com" in data["cors_origins"]


def test_public_settings_change_requires_admin_key(monkeypatch, api_server):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")
    monkeypatch.setenv("KATER_API_KEY", "tool-secret")
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)

    err = _get_err_post(
        9970,
        "/api/settings",
        {"cors_origins": ["https://ok.example.com"]},
        headers={"Authorization": "Bearer tool-secret"},
    )
    assert err.code == 403


@pytest.mark.parametrize(
    "body,expected",
    [
        ({"auth": {"mode": "none"}}, "auth.mode=none"),
        ({"cors_origins": ["*"]}, "cors_origins"),
        ({"rate_limit_per_min": 0}, "rate_limit_per_min"),
    ],
)
def test_public_settings_reject_unsafe_downgrades(monkeypatch, api_server, body, expected):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")
    monkeypatch.setenv("KATER_API_KEYS", "admin-secret")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")

    err = _get_err_post(
        9970,
        "/api/settings",
        body,
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert err.code == 400
    assert expected in err.read().decode()


def test_public_settings_unsafe_override_allows_explicit_downgrade(monkeypatch, api_server):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")
    monkeypatch.setenv("KATER_API_KEYS", "admin-secret")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("KATER_ALLOW_UNSAFE_PUBLIC_SETTINGS", "1")

    data = _post(
        9970,
        "/api/settings",
        {"auth": {"mode": "none"}},
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert data["auth"]["mode"] == "none"


def test_confidential_client_requires_secret_for_token():
    import base64
    import hashlib

    from kater.oauth import create_auth_code, exchange_code

    client = register_client(
        "confidential-app",
        ["https://app.example.com/cb"],
        token_endpoint_auth_method="client_secret_post",
    )
    verifier = "v" * 40
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    code = create_auth_code(
        AuthCodeRequest(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
    )
    # Missing secret -> rejected.
    assert exchange_code(code, client.client_id, verifier, client_secret=None) is None

    code2 = create_auth_code(
        AuthCodeRequest(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
    )
    # Wrong secret -> rejected.
    assert exchange_code(code2, client.client_id, verifier, client_secret="wrong") is None

    code3 = create_auth_code(
        AuthCodeRequest(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
    )
    # Correct secret -> accepted.
    result = exchange_code(code3, client.client_id, verifier, client_secret=client.client_secret)
    assert result is not None
    assert result["access_token"].startswith("tok_")


def test_public_client_works_without_secret():
    """Default (none) clients must still work with PKCE only (ChatGPT flow)."""
    import base64
    import hashlib

    from kater.oauth import create_auth_code, exchange_code

    client = register_client("public-app", ["https://app.example.com/cb"])
    assert client.token_endpoint_auth_method == "none"
    verifier = "v" * 40
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    code = create_auth_code(
        AuthCodeRequest(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
    )
    result = exchange_code(code, client.client_id, verifier, client_secret=None)
    assert result is not None


# ── 4. Registration token gating ───────────────────────────────────


def test_register_requires_token_when_set(api_server, monkeypatch):
    monkeypatch.setenv("KATER_REGISTRATION_TOKEN", "secret-reg-token")
    # Without token -> 403.
    err = _get_err_post(
        9970,
        "/register",
        json.dumps({"client_name": "x", "redirect_uris": ["https://a.com/cb"]}),
    )
    assert err.code == 403
    # With token -> 201.
    data = _post(
        9970,
        "/register",
        json.dumps({"client_name": "x", "redirect_uris": ["https://a.com/cb"]}),
        headers={"X-Registration-Token": "secret-reg-token"},
    )
    assert data["client_id"].startswith("client_")


def test_public_register_disabled_by_default(api_server, monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_ALLOW_DYNAMIC_REGISTRATION", raising=False)
    monkeypatch.delenv("KATER_REGISTRATION_TOKEN", raising=False)

    err = _get_err_post(
        9970,
        "/register",
        {"client_name": "x", "redirect_uris": ["https://a.com/cb"]},
    )
    assert err.code == 403
    assert json.loads(err.read())["error"] == "registration_disabled"


def test_public_register_requires_opt_in_and_presented_token(api_server, monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ALLOW_DYNAMIC_REGISTRATION", "1")
    monkeypatch.setenv("KATER_REGISTRATION_TOKEN", "secret-reg-token")

    err = _get_err_post(
        9970,
        "/register",
        {"client_name": "x", "redirect_uris": ["https://a.com/cb"]},
    )
    assert err.code == 403
    assert json.loads(err.read())["error"] == "registration_forbidden"

    data = _post(
        9970,
        "/register",
        {"client_name": "x", "redirect_uris": ["https://a.com/cb"]},
        headers={"X-Registration-Token": "secret-reg-token"},
    )
    assert data["client_id"].startswith("client_")


def test_public_dashboard_first_party_authorize_does_not_need_registration(api_server, monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_ALLOW_DYNAMIC_REGISTRATION", raising=False)
    monkeypatch.delenv("KATER_REGISTRATION_TOKEN", raising=False)

    resp = urllib.request.urlopen(
        "http://127.0.0.1:9970/authorize?client_id=kater-dashboard"
        "&redirect_uri=http://127.0.0.1:9970/dashboard"
        "&code_challenge=test&code_challenge_method=S256"
    )

    html = resp.read().decode()
    assert resp.status == 200
    assert "kater-dashboard" in html
    assert resp.headers["Set-Cookie"].startswith("kater_oauth_consent=")


def test_authorize_approve_requires_consent_nonce(api_server):
    client = register_client("NoBypass", ["https://app.example.com/cb"])
    err = _get_err(
        9970,
        f"/authorize?client_id={client.client_id}"
        f"&redirect_uri=https://app.example.com/cb"
        f"&code_challenge=test&code_challenge_method=S256"
        f"&state=xyz123&approve=1",
    )
    assert err.code == 403
    assert json.loads(err.read())["error"] == "consent_required"


# ── 6. Rate limiting on MCP transport ──────────────────────────────


def test_mcp_middleware_applies_rate_limit(monkeypatch):
    from kater.mcp_server import AuthASGIMiddleware
    from kater.settings import KaterSettings, save_settings

    save_settings(KaterSettings(rate_limit_per_min=2))
    # Reset the module-global limiter so the new limit takes effect.
    from kater import api as api_mod

    api_mod._reset_rate_limiter()

    sent: list = []

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(msg):
        sent.append(msg)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "headers": [], "query_string": b"", "client": ("1.2.3.4", 0)}
    mw = AuthASGIMiddleware(downstream)
    # First two calls pass auth-none and rate-limit; third is throttled.
    asyncio.run(mw(scope, receive, send))
    asyncio.run(mw(scope, receive, send))
    asyncio.run(mw(scope, receive, send))
    statuses = [m.get("status") for m in sent if m.get("type") == "http.response.start"]
    assert 429 in statuses
    api_mod._reset_rate_limiter()


# ── 7. Telemetry pruning / disk cap ────────────────────────────────


def test_sqlite_prune_caps_rows(monkeypatch, tmp_path):
    from kater import storage
    from kater.settings import KaterSettings, save_settings

    monkeypatch.chdir(tmp_path)
    save_settings(KaterSettings(storage_backend="sqlite"))
    storage.reset_db_cache()
    # Lower the cap to make the test fast.
    monkeypatch.setattr(storage, "MAX_ROWS_ON_DISK", 10)
    now = time.time()
    try:
        for i in range(25):
            storage.insert_event(
                {"type": "t", "name": f"n{i}", "timestamp": now + i, "success": True}
            )
        storage.prune_all()
        assert storage.count_events() <= 10
    finally:
        storage.reset_db_cache()


# ── 8. OpenAPI drift: every route is in the spec ───────────────────


def test_openapi_spec_covers_all_routes():
    from kater.api import ROUTER
    from kater.openapi_spec import generate_spec

    spec = generate_spec()
    spec_paths = set(spec.get("paths", {}).keys())

    missing = []
    for route in ROUTER._routes:
        # Convert {param} -> keep as-is; OpenAPI uses the same braces.
        if route.pattern not in spec_paths:
            missing.append(f"{route.method} {route.pattern}")
    assert not missing, f"Routes missing from OpenAPI spec: {missing}"


# ── 9. KATER_PUBLIC truthy hides private sources ───────────────────


def test_public_mode_true_hides_private_profiles(monkeypatch):
    from kater.profiles import is_public_mode, list_profiles

    monkeypatch.setenv("KATER_PUBLIC", "true")
    assert is_public_mode() is True
    profiles = list_profiles()
    assert "demo_private" not in profiles


def test_public_mode_yes_hides_private_profiles(monkeypatch):
    from kater.profiles import is_public_mode

    monkeypatch.setenv("KATER_PUBLIC", "yes")
    assert is_public_mode() is True


def test_private_mode_shows_private_profiles(monkeypatch):
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    from kater.profiles import is_public_mode

    assert is_public_mode() is False


# ── 10. doctor treats registration as closed by default ────────────


def test_doctor_does_not_flag_closed_default_registration(monkeypatch):
    from kater.doctor import run_doctor
    from kater.settings import AuthConfig, KaterSettings, save_settings

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.delenv("KATER_ALLOW_DYNAMIC_REGISTRATION", raising=False)
    monkeypatch.delenv("KATER_REGISTRATION_TOKEN", raising=False)
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    save_settings(KaterSettings(auth=AuthConfig(mode="oauth")))
    report = run_doctor(profiles={"core"})
    codes = [f.code for f in report.findings]
    assert "public_oauth_open_registration" not in codes
    assert "public_oauth_registration_token_missing" not in codes
    assert "public_oauth_ready" in codes


# ── 11. client registration limit ──────────────────────────────────


def test_register_client_limit_enforced(monkeypatch):
    from kater import oauth

    monkeypatch.setattr(oauth, "MAX_CLIENTS", 2)
    oauth.register_client("a", ["https://a.com/cb"])
    oauth.register_client("b", ["https://b.com/cb"])
    with pytest.raises(ValueError):
        oauth.register_client("c", ["https://c.com/cb"])


# ── 12. SSEBackend discovery over a real HTTP server ───────────────


def test_sse_backend_discovers_endpoint_and_calls_tool():
    """SSEBackend was previously untested; exercise discovery + RPC end-to-end."""
    import http.server
    import json as _json

    from kater.proxy.sse_backend import SSEBackend

    calls: list[dict] = []

    class _FakeMCPServer(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            # First GET: announce the messages endpoint.
            self.wfile.write(
                b'data: {"type": "endpoint", "uri": "/messages"}\n\n'
            )

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode() if length else "{}"
            calls.append(_json.loads(body))
            method = calls[-1].get("method")
            rid = calls[-1].get("id")
            resp = {"jsonrpc": "2.0", "id": rid}
            if method == "initialize":
                resp["result"] = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "fake", "version": "1"},
                    "capabilities": {"tools": {}},
                }
            elif method == "tools/list":
                resp["result"] = {"tools": [{"name": "ping"}]}
            elif method == "tools/call":
                resp["result"] = {"content": [{"type": "text", "text": "pong"}]}
            else:
                resp["result"] = {}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write((_json.dumps(resp) + "\n").encode())

    httpd = http.server.HTTPServer(("127.0.0.1", 0), _FakeMCPServer)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        backend = SSEBackend(name="fake", url=f"http://127.0.0.1:{port}/sse")
        backend.start()
        assert backend.is_healthy(), f"not healthy: {backend.status.error}"
        assert [t.name for t in backend.list_tools()] == ["ping"]
        result = backend.call_tool("ping", {})
        assert result["content"][0]["text"] == "pong"
    finally:
        httpd.shutdown()
        httpd.server_close()


# ── 13. Full /authorize browser flow → /token end-to-end ──────────


def test_full_authorize_browser_flow(api_server):
    """Register → consent page → approve redirect → token exchange, all via HTTP."""
    import base64
    import hashlib
    from urllib.parse import parse_qs, urlparse

    # Register a client.
    reg = _post(
        9970,
        "/register",
        {"client_name": "FlowTest", "redirect_uris": ["https://app.example.com/cb"]},
    )
    client_id = reg["client_id"]

    verifier = "verifier-" + "0" * 40
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")

    # Hit /authorize without approve → consent page HTML.
    consent_resp = urllib.request.urlopen(
        f"http://127.0.0.1:9970/authorize?client_id={client_id}"
        f"&redirect_uri=https://app.example.com/cb"
        f"&code_challenge={challenge}&code_challenge_method=S256"
        f"&state=xyz123"
    )
    consent = consent_resp.read().decode()
    assert "Allow" in consent
    assert "FlowTest" in consent
    cookie = consent_resp.headers["Set-Cookie"].split(";", 1)[0]
    allow_href = re.search(r'href="([^"]+approve=1[^"]+)"', consent)
    assert allow_href is not None
    approve_url = allow_href.group(1).replace("&amp;", "&")

    # Approve → 302 redirect with code=.
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    redirect_caught: list[str] = []

    class _NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            redirect_caught.append(newurl)
            return None

    opener = urllib.request.build_opener(_NoFollow)
    req = urllib.request.Request(
        approve_url,
        headers={"Cookie": cookie},
    )
    try:
        opener.open(req)
    except urllib.error.HTTPError as exc:
        # 302 surfaces as HTTPError with the redirect body.
        loc = exc.headers.get("Location", "")
        redirect_caught.append(loc)
    assert redirect_caught, "expected a redirect"
    location = redirect_caught[0]
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    assert "code" in qs
    code = qs["code"][0]
    # state must be echoed back verbatim (URL-encoded).
    assert "xyz123" in qs.get("state", [""])[0]

    # Exchange the code for a token.
    token = _post_raw_form(
        9970,
        "/token",
        f"grant_type=authorization_code&code={code}"
        f"&client_id={client_id}&code_verifier={verifier}",
    )
    assert token["access_token"].startswith("tok_")


def _post_raw_form(port, path, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


# ── Round 4: additional security hardening ─────────────────────────


def test_settings_atomic_write():
    """save_settings uses tmp+replace — file is never partially written."""
    from kater.settings import KaterSettings, save_settings

    save_settings(KaterSettings(rate_limit_per_min=42))
    # Verify the on-disk content is valid JSON (atomic swap leaves no half-write).
    raw = (KATER_DIR / "settings.json").read_text()
    data = json.loads(raw)
    assert data["rate_limit_per_min"] == 42
    # Cleanup
    save_settings(KaterSettings())


def test_websocket_origin_validation():
    """WebSocket handshake rejects Origins not in CORS allowlist."""
    from kater.settings import KaterSettings, save_settings

    # Restrict CORS to a single origin so we can test rejection.
    save_settings(KaterSettings(cors_origins=["http://localhost:9091"]))
    try:
        from kater.websocket import WSHandler

        class FakeHandler(WSHandler):
            def __init__(self):
                self.headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
                import io
                self.wfile = io.BytesIO()

            def send_response(self, code, *a):
                self._status = code

            def end_headers(self):
                pass

            def send_header(self, k, v):
                pass

        h = FakeHandler()
        # Without Origin header → allowed (non-browser client).
        assert h._do_handshake() is True

        h2 = FakeHandler()
        h2.headers["Origin"] = "http://localhost:9091"
        assert h2._do_handshake() is True

        h3 = FakeHandler()
        h3.headers["Origin"] = "https://evil.com"
        assert h3._do_handshake() is False
    finally:
        save_settings(KaterSettings())


def test_base_url_trusts_forwarded_host_only_from_loopback():
    """_base_url only honours X-Forwarded-Host when peer is loopback."""
    from kater.api import _base_url

    class FakeHandler:
        def __init__(self, peer, xfh=None, host="example.com"):
            self.client_address = (peer,)
            self.headers = {"Host": host}
            if xfh:
                self.headers["X-Forwarded-Host"] = xfh

    # Loopback peer + XFF → trusted.
    h = _base_url(FakeHandler("127.0.0.1", xfh="safe.example.com"))
    assert h == "http://safe.example.com"

    # External peer + XFF → XFF ignored, Host used.
    h = _base_url(FakeHandler("10.0.0.1", xfh="evil.com", host="real.example.com"))
    assert h == "http://real.example.com"


def test_oauth_file_permissions():
    """oauth.json is created with owner-only permissions (0o600)."""
    import stat

    from kater.oauth import _db_path, _save

    _save()
    mode = stat.S_IMODE(_db_path().stat().st_mode)
    # Owner can read/write; group and others must have no access.
    assert mode & 0o077 == 0


def test_cors_vary_origin_header():
    """CORS responses include Vary: Origin when origin is dynamic."""
    import inspect

    from kater.api import KaterAPIHandler

    src = inspect.getsource(KaterAPIHandler._write)
    assert "Vary" in src


def test_security_headers_include_csp_referrer_and_https_hsts(api_server):
    req = urllib.request.Request(
        "http://127.0.0.1:9970/health",
        headers={"X-Forwarded-Proto": "https"},
    )
    resp = urllib.request.urlopen(req)

    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    csp = resp.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "object-src 'none'" in csp
    assert resp.headers.get("Strict-Transport-Security") == (
        "max-age=31536000; includeSubDomains"
    )
