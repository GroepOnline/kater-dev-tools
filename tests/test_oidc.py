"""Product Authentik OIDC RP — config, claims, authorize→callback."""

from __future__ import annotations

import base64
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from kater.api import create_api_server
from kater.browser_auth import (
    LOGIN_COOKIE,
    SESSION_COOKIE,
    authenticate_session,
    create_session,
    reset_sessions,
    revoke_session,
    safe_return_to,
)
from kater.oauth import create_auth_code, exchange_code, register_client, reset_state
from kater.oidc import (
    HttpResponse,
    OidcConfig,
    OidcError,
    begin_authorize_login,
    begin_login,
    build_authorize_url,
    complete_callback,
    decode_jwt_payload,
    discover,
    discovery_url,
    load_oidc_config,
    oidc_enabled,
    oidc_partial,
    oidc_public_status,
    reset_oidc_state,
    resolve_callback_uri,
    set_transport,
    validate_id_token_claims,
    verify_id_token,
)
from tests.portutil import free_port


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _fake_jwt(claims: dict) -> str:
    header = _b64url(b'{"alg":"none","typ":"JWT"}')
    payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    return f"{header}.{payload}.sig"


class FakeIdP:
    def __init__(self, issuer: str, client_id: str) -> None:
        self.issuer = issuer.rstrip("/") + "/"
        self.client_id = client_id
        self.authorization_endpoint = "http://127.0.0.1/idp/authorize"
        self.token_endpoint = "http://127.0.0.1/idp/token"
        self.userinfo_endpoint = "http://127.0.0.1/idp/userinfo"
        self.jwks_uri = "http://127.0.0.1/idp/jwks"
        self.last_token_fields: dict[str, str] = {}
        self.userinfo_groups: list[str] = ["owner"]
        self.revoked_access: set[str] = set()
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._kid = "fake-idp-rs256"
        jwk = json.loads(RSAAlgorithm.to_jwk(self._private_key.public_key()))
        jwk.update({"kid": self._kid, "use": "sig", "alg": "RS256"})
        self._jwks = {"keys": [jwk]}

    def sign_id_token(
        self,
        *,
        nonce: str,
        iss: str | None = None,
        aud: str | list[str] | None = None,
        exp: int | None = None,
        sub: str = "user-1",
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": iss or self.issuer,
            "aud": aud if aud is not None else self.client_id,
            "exp": exp if exp is not None else now + 120,
            "iat": now,
            "nonce": nonce,
            "sub": sub,
        }
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._kid},
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> HttpResponse:
        if url.endswith("/.well-known/openid-configuration"):
            payload = {
                "issuer": self.issuer,
                "authorization_endpoint": self.authorization_endpoint,
                "token_endpoint": self.token_endpoint,
                "jwks_uri": self.jwks_uri,
                "userinfo_endpoint": self.userinfo_endpoint,
                "code_challenge_methods_supported": ["S256"],
                "scopes_supported": ["openid"],
            }
            body = json.dumps(payload).encode()
            return HttpResponse(200, {"content-type": "application/json"}, body)
        if url == self.jwks_uri:
            body = json.dumps(self._jwks).encode()
            return HttpResponse(200, {"content-type": "application/json"}, body)
        if method == "GET" and url == self.userinfo_endpoint:
            hdrs = headers or {}
            auth = hdrs.get("Authorization") or hdrs.get("authorization") or ""
            token = auth.removeprefix("Bearer ").strip()
            if token in self.revoked_access:
                return HttpResponse(401, {}, b"{}")
            body_out = json.dumps({"sub": "user-1", "groups": self.userinfo_groups}).encode()
            return HttpResponse(200, {"content-type": "application/json"}, body_out)
        if method == "POST" and url == self.token_endpoint:
            from kater import oidc as oidc_mod

            raw = (body or b"").decode("ascii").split("&")
            fields = dict(pair.split("=", 1) for pair in raw if "=" in pair)
            self.last_token_fields = fields
            sessions = list(oidc_mod._pending.values())
            nonce = sessions[0].nonce if sessions else "missing"
            access_token = f"idp_at_{secrets.token_hex(8)}"
            token_body = {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "id_token": self.sign_id_token(nonce=nonce),
            }
            return HttpResponse(200, {}, json.dumps(token_body).encode())
        return HttpResponse(404, {}, b"{}")


@pytest.fixture
def oidc_env(monkeypatch: pytest.MonkeyPatch) -> OidcConfig:
    reset_oidc_state()
    reset_state()
    reset_sessions()
    issuer = "http://127.0.0.1/application/o/kater/"
    monkeypatch.setenv("AUTH_OIDC_ISSUER", issuer)
    monkeypatch.setenv("AUTH_OIDC_CLIENT_ID", "chefgroep-kater-oidc")
    monkeypatch.setenv("AUTH_OIDC_REDIRECT_URI", "http://127.0.0.1:9091/oidc/callback")
    monkeypatch.setenv("AUTH_OIDC_SCOPES", "openid")
    monkeypatch.delenv("AUTH_OIDC_CLIENT_SECRET", raising=False)
    fake = FakeIdP(issuer, "chefgroep-kater-oidc")
    set_transport(fake)
    yield load_oidc_config()
    set_transport(None)
    reset_oidc_state()
    reset_state()
    reset_sessions()


def test_load_config_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "AUTH_OIDC_ISSUER",
        "AUTH_OIDC_CLIENT_ID",
        "AUTH_OIDC_CLIENT_SECRET",
        "AUTH_OIDC_REDIRECT_URI",
        "AUTH_OIDC_SCOPES",
        "AUTH_OIDC_AUDIENCE",
    ):
        monkeypatch.delenv(key, raising=False)
    config = load_oidc_config()
    assert config.enabled is False
    assert oidc_enabled(config) is False
    assert oidc_partial(config) is False
    status = oidc_public_status(config)
    assert status["enabled"] is False
    assert status["gate"] == "local_or_access"
    assert "secret" not in json.dumps(status).lower()


def test_partial_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_OIDC_ISSUER", "https://auth.example.com/application/o/kater/")
    monkeypatch.delenv("AUTH_OIDC_CLIENT_ID", raising=False)
    assert oidc_partial() is True
    assert oidc_enabled() is False


def test_discovery_url() -> None:
    assert (
        discovery_url("https://auth.example.com/application/o/kater/")
        == "https://auth.example.com/application/o/kater/.well-known/openid-configuration"
    )
    already = "https://auth.example.com/application/o/kater/.well-known/openid-configuration"
    assert discovery_url(already) == already


def test_public_status_omits_secret(oidc_env: OidcConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_OIDC_CLIENT_SECRET", "super-secret-value")
    status = oidc_public_status()
    dumped = json.dumps(status)
    assert "super-secret-value" not in dumped
    assert status["enabled"] is True
    assert status["gate"] == "authentik"
    assert status["client_id"] == "chefgroep-kater-oidc"


def test_resolve_callback_loopback_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_OIDC_REDIRECT_URI", raising=False)
    monkeypatch.setenv("AUTH_OIDC_ISSUER", "https://auth.example.com/application/o/kater/")
    monkeypatch.setenv("AUTH_OIDC_CLIENT_ID", "demo")
    assert (
        resolve_callback_uri("http://127.0.0.1:9091", public=False)
        == "http://127.0.0.1:9091/oidc/callback"
    )
    with pytest.raises(OidcError) as exc:
        resolve_callback_uri("http://127.0.0.1:9091", public=True)
    assert exc.value.code == "oidc_redirect_unconfigured"


def test_id_token_claims(oidc_env: OidcConfig) -> None:
    discovery = discover(oidc_env.issuer)
    claims = {
        "iss": oidc_env.issuer,
        "aud": oidc_env.client_id,
        "exp": int(time.time()) + 60,
        "nonce": "n1",
        "sub": "user-1",
    }
    validate_id_token_claims(claims, config=oidc_env, discovery=discovery, nonce="n1")
    with pytest.raises(OidcError) as exc:
        validate_id_token_claims(claims, config=oidc_env, discovery=discovery, nonce="other")
    assert exc.value.code == "oidc_id_token_nonce"
    payload = decode_jwt_payload(_fake_jwt(claims))
    assert payload["sub"] == "user-1"


def test_build_authorize_url_has_pkce(oidc_env: OidcConfig) -> None:
    discovery = discover(oidc_env.issuer)
    url = build_authorize_url(
        discovery=discovery,
        config=oidc_env,
        redirect_uri="http://127.0.0.1:9091/oidc/callback",
        state="st",
        nonce="nn",
        code_challenge="cc",
    )
    assert url.startswith(discovery.authorization_endpoint)
    assert "client_id=chefgroep-kater-oidc" in url
    assert "code_challenge=cc" in url
    assert "code_challenge_method=S256" in url
    assert "client_secret" not in url


def test_begin_login_and_callback_roundtrip(oidc_env: OidcConfig) -> None:
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        browser_binding=binding,
    )
    assert "state=" in location
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state, browser_binding=binding)
    assert result.subject == "user-1"
    assert result.pending is None
    assert result.access_token.startswith("idp_at_")


def test_authorize_login_mints_local_code(oidc_env: OidcConfig) -> None:
    client = register_client("ChatGPT", ["http://127.0.0.1/cb"])
    binding = secrets.token_urlsafe(16)
    location = begin_authorize_login(
        client_id=client.client_id,
        redirect_uri="http://127.0.0.1/cb",
        code_challenge="abc",
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        state="client-state",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state, browser_binding=binding)
    assert result.pending is not None
    assert result.pending.client_id == client.client_id
    code = create_auth_code(
        client_id=result.pending.client_id,
        redirect_uri=result.pending.redirect_uri,
        code_challenge="abc",
        state=result.pending.state,
    )
    assert code.startswith("code_")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect())


def _assert_loopback_test_url(url: str) -> None:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    assert parts.scheme in {"http", "https"}
    assert parts.hostname in {"127.0.0.1", "localhost"}


def _test_http_open(
    target: str | urllib.request.Request,
    *,
    follow_redirects: bool = True,
) -> Any:
    """HTTP client for the in-process test API server (loopback URLs only)."""
    raw = target if isinstance(target, str) else target.full_url
    _assert_loopback_test_url(raw)
    opener = (
        urllib.request.build_opener()
        if follow_redirects
        else _opener()
    )
    return opener.open(target)  # nosec B310 — URL scheme/host validated above


def _cookie_value(set_cookie: str | None, name: str) -> str:
    if not set_cookie:
        return ""
    first = set_cookie.split(",", 1)[0]
    key, _, value = first.partition("=")
    return value if key.strip() == name else ""


@pytest.fixture
def mock_idp(oidc_env: OidcConfig) -> FakeIdP:
    from kater import oidc as oidc_mod

    assert isinstance(oidc_mod._transport, FakeIdP)
    return oidc_mod._transport


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", free_port())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.1)


def _port(server) -> int:
    return int(server.server_address[1])


def test_oidc_status_and_login_unset(api_server) -> None:
    port = _port(api_server)
    status = json.loads(_test_http_open(f"http://127.0.0.1:{port}/oidc/status").read())
    assert status["enabled"] is False
    with pytest.raises(urllib.error.HTTPError) as exc:
        _test_http_open(f"http://127.0.0.1:{port}/oidc/login")
    assert exc.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as exc:
        _test_http_open(f"http://127.0.0.1:{port}/oidc/callback")
    assert exc.value.code == 400


def test_authorize_stays_local_consent_when_oidc_unset(api_server) -> None:
    port = _port(api_server)
    client = register_client("App", [f"http://127.0.0.1:{port}/cb"])
    resp = _test_http_open(
        f"http://127.0.0.1:{port}/authorize?client_id={client.client_id}"
        f"&redirect_uri=http://127.0.0.1:{port}/cb"
        "&code_challenge=test&code_challenge_method=S256"
    )
    assert resp.status == 200
    assert b"Allow" in resp.read()


def test_authorize_to_callback_with_mock_idp(oidc_env: OidcConfig, api_server) -> None:
    import hashlib

    port = _port(api_server)
    verifier = "verifier12345678901234567890"
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    client = register_client("App", [f"http://127.0.0.1:{port}/cb"])
    try:
        _test_http_open(
            f"http://127.0.0.1:{port}/authorize?client_id={client.client_id}"
            f"&redirect_uri=http://127.0.0.1:{port}/cb"
            f"&code_challenge={challenge}&code_challenge_method=S256&state=cli",
            follow_redirects=False,
        )
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        location = exc.headers["Location"]
        login_cookie = _cookie_value(exc.headers.get("Set-Cookie"), LOGIN_COOKIE)
    assert location.startswith("http://127.0.0.1/idp/authorize")
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    try:
        _test_http_open(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/oidc/callback?code=from-idp&state={state}",
                headers={"Cookie": f"{LOGIN_COOKIE}={login_cookie}"},
            ),
            follow_redirects=False,
        )
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        back = exc.headers["Location"]
    assert back.startswith(f"http://127.0.0.1:{port}/cb?code=")
    assert "state=cli" in back
    code = parse_qs(urlparse(back).query)["code"][0]
    token = exchange_code(code, client.client_id, verifier)
    assert token is not None
    assert token["access_token"].startswith("tok_")


def test_health_includes_oidc(api_server) -> None:
    port = _port(api_server)
    data = json.loads(_test_http_open(f"http://127.0.0.1:{port}/health").read())
    assert "oidc" in data
    assert data["oidc"]["enabled"] is False


def test_safe_return_to_rejects_open_redirects() -> None:
    assert safe_return_to("/dashboard?x=1") == "/dashboard?x=1"
    assert safe_return_to("//evil.example/phish") == "/dashboard"
    assert safe_return_to("https://evil.example/x") == "/dashboard"
    assert safe_return_to("/%2f%2fevil.example") == "/dashboard"


def test_verify_id_token_wrong_issuer(oidc_env: OidcConfig, mock_idp: FakeIdP) -> None:
    discovery = discover(oidc_env.issuer)
    token = mock_idp.sign_id_token(nonce="n1", iss="https://wrong.example/o/kater/")
    with pytest.raises(OidcError) as exc:
        verify_id_token(token, discovery, oidc_env)
    assert exc.value.code == "oidc_id_token_invalid"


def test_verify_id_token_wrong_audience(oidc_env: OidcConfig, mock_idp: FakeIdP) -> None:
    discovery = discover(oidc_env.issuer)
    token = mock_idp.sign_id_token(nonce="n1", aud="other-client")
    with pytest.raises(OidcError) as exc:
        verify_id_token(token, discovery, oidc_env)
    assert exc.value.code == "oidc_id_token_invalid"


def test_verify_id_token_expired(oidc_env: OidcConfig, mock_idp: FakeIdP) -> None:
    discovery = discover(oidc_env.issuer)
    token = mock_idp.sign_id_token(nonce="n1", exp=int(time.time()) - 30)
    with pytest.raises(OidcError) as exc:
        verify_id_token(token, discovery, oidc_env)
    assert exc.value.code == "oidc_id_token_invalid"


def test_complete_callback_nonce_mismatch(oidc_env: OidcConfig) -> None:
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    with pytest.raises(OidcError) as exc:
        complete_callback(code="authz-code", state=state + "x", browser_binding=binding)
    assert exc.value.code == "oidc_state_invalid"


def test_complete_callback_binding_mismatch(oidc_env: OidcConfig) -> None:
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    with pytest.raises(OidcError) as exc:
        complete_callback(code="authz-code", state=state, browser_binding="wrong-binding")
    assert exc.value.code == "oidc_state_invalid"


def test_browser_session_logout_and_expiry(oidc_env: OidcConfig) -> None:
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state, browser_binding=binding)
    session_value = create_session(result)
    authenticate_session(session_value)
    revoke_session(session_value)
    with pytest.raises(OidcError) as exc:
        authenticate_session(session_value)
    assert exc.value.code == "oidc_session_invalid"

    result.expires_at = time.time() - 1
    with pytest.raises(OidcError) as exc2:
        create_session(result)
    assert exc2.value.code == "oidc_session_invalid"


def test_entitlement_required(
    oidc_env: OidcConfig, mock_idp: FakeIdP, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_OIDC_REQUIRED_GROUPS", "owner")
    mock_idp.userinfo_groups = []
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state, browser_binding=binding)
    with pytest.raises(OidcError) as exc:
        create_session(result)
    assert exc.value.code == "oidc_entitlement_required"


def test_oidc_login_callback_dashboard_flow(oidc_env: OidcConfig, api_server) -> None:
    port = _port(api_server)
    try:
        _test_http_open(
            f"http://127.0.0.1:{port}/oidc/login?next=/dashboard",
            follow_redirects=False,
        )
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        idp_location = exc.headers["Location"]
        login_cookie = _cookie_value(exc.headers.get("Set-Cookie"), LOGIN_COOKIE)
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(idp_location).query)["state"][0]
    try:
        _test_http_open(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/oidc/callback?code=from-idp&state={state}",
                headers={"Cookie": f"{LOGIN_COOKIE}={login_cookie}"},
            ),
            follow_redirects=False,
        )
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as cb_exc:
        assert cb_exc.code == 302
        assert cb_exc.headers["Location"].endswith("/dashboard")
        assert "api_key=" not in cb_exc.headers["Location"]
        session_cookie = _cookie_value(cb_exc.headers.get("Set-Cookie"), SESSION_COOKIE)
    assert session_cookie
    resp = _test_http_open(
        urllib.request.Request(
            f"http://127.0.0.1:{port}/dashboard",
            headers={"Cookie": f"{SESSION_COOKIE}={session_cookie}"},
        )
    )
    assert resp.status == 200


def test_dashboard_unauthorized_without_session(oidc_env: OidcConfig, api_server) -> None:
    port = _port(api_server)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _test_http_open(f"http://127.0.0.1:{port}/dashboard", follow_redirects=False)
    assert exc.value.code == 302
    assert "/oidc/login" in exc.value.headers["Location"]


def test_dashboard_forbidden_without_entitlement(
    oidc_env: OidcConfig, mock_idp: FakeIdP, api_server, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_OIDC_REQUIRED_GROUPS", "owner")
    port = _port(api_server)
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri=f"http://127.0.0.1:{port}/oidc/callback",
        browser_binding=binding,
        next_path="/dashboard",
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state, browser_binding=binding)
    session_value = create_session(result)
    mock_idp.userinfo_groups = []
    with pytest.raises(urllib.error.HTTPError) as exc:
        _test_http_open(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/dashboard",
                headers={"Cookie": f"{SESSION_COOKIE}={session_value}"},
            )
        )
    assert exc.value.code == 403


def test_oidc_logout_clears_session(oidc_env: OidcConfig, api_server) -> None:
    port = _port(api_server)
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri=f"http://127.0.0.1:{port}/oidc/callback",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    try:
        _test_http_open(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/oidc/callback?code=from-idp&state={state}",
                headers={"Cookie": f"{LOGIN_COOKIE}={binding}"},
            ),
            follow_redirects=False,
        )
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as exc:
        session_cookie = _cookie_value(exc.headers.get("Set-Cookie"), SESSION_COOKIE)
    resp = _test_http_open(
        urllib.request.Request(
            f"http://127.0.0.1:{port}/oidc/logout",
            data=b"",
            method="POST",
            headers={
                "Cookie": f"{SESSION_COOKIE}={session_cookie}",
                "Origin": "http://127.0.0.1:9091",
            },
        ),
        follow_redirects=False,
    )
    assert resp.status == 200
    with pytest.raises(urllib.error.HTTPError) as exc:
        _test_http_open(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/dashboard",
                headers={"Cookie": f"{SESSION_COOKIE}={session_cookie}"},
            )
        )
    assert exc.value.code in {302, 401}


def test_api_still_requires_bearer_without_browser_session(
    oidc_env: OidcConfig, api_server, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")
    port = _port(api_server)
    binding = secrets.token_urlsafe(16)
    location = begin_login(
        callback_uri=f"http://127.0.0.1:{port}/oidc/callback",
        browser_binding=binding,
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state, browser_binding=binding)
    session_value = create_session(result)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _test_http_open(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/api/mcp/servers",
                headers={"Cookie": f"{SESSION_COOKIE}={session_value}"},
            )
        )
    assert exc.value.code == 401
