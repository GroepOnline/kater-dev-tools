"""Product Authentik OIDC RP — config, claims, authorize→callback."""

from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from kater.api import create_api_server
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
        self.last_token_fields: dict[str, str] = {}

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
                "jwks_uri": "http://127.0.0.1/idp/jwks",
                "code_challenge_methods_supported": ["S256"],
                "scopes_supported": ["openid"],
            }
            payload_bytes = json.dumps(payload).encode()
            return HttpResponse(200, {"content-type": "application/json"}, payload_bytes)
        if method == "POST" and url == self.token_endpoint:
            from kater import oidc as oidc_mod

            raw = (body or b"").decode("ascii").split("&")
            fields = dict(pair.split("=", 1) for pair in raw if "=" in pair)
            self.last_token_fields = fields
            sessions = list(oidc_mod._pending.values())
            nonce = sessions[0].nonce if sessions else "missing"
            claims = {
                "iss": self.issuer,
                "aud": self.client_id,
                "exp": int(time.time()) + 120,
                "nonce": nonce,
                "sub": "user-1",
            }
            token_body = {
                "access_token": "idp_at",
                "token_type": "Bearer",
                "id_token": _fake_jwt(claims),
            }
            return HttpResponse(200, {}, json.dumps(token_body).encode())
        return HttpResponse(404, {}, b"{}")


@pytest.fixture
def oidc_env(monkeypatch: pytest.MonkeyPatch) -> OidcConfig:
    reset_oidc_state()
    reset_state()
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
    location = begin_login(callback_uri="http://127.0.0.1:9091/oidc/callback")
    assert "state=" in location
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state)
    assert result.subject == "user-1"
    assert result.pending is None


def test_authorize_login_mints_local_code(oidc_env: OidcConfig) -> None:
    client = register_client("ChatGPT", ["http://127.0.0.1/cb"])
    location = begin_authorize_login(
        client_id=client.client_id,
        redirect_uri="http://127.0.0.1/cb",
        code_challenge="abc",
        callback_uri="http://127.0.0.1:9091/oidc/callback",
        state="client-state",
    )
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    result = complete_callback(code="authz-code", state=state)
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
    status = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/oidc/status").read())
    assert status["enabled"] is False
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/oidc/login")
    assert exc.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/oidc/callback")
    assert exc.value.code == 400


def test_authorize_stays_local_consent_when_oidc_unset(api_server) -> None:
    port = _port(api_server)
    client = register_client("App", [f"http://127.0.0.1:{port}/cb"])
    resp = urllib.request.urlopen(
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
        _opener().open(
            f"http://127.0.0.1:{port}/authorize?client_id={client.client_id}"
            f"&redirect_uri=http://127.0.0.1:{port}/cb"
            f"&code_challenge={challenge}&code_challenge_method=S256&state=cli"
        )
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        location = exc.headers["Location"]
    assert location.startswith("http://127.0.0.1/idp/authorize")
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(location).query)["state"][0]
    try:
        _opener().open(f"http://127.0.0.1:{port}/oidc/callback?code=from-idp&state={state}")
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
    data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read())
    assert "oidc" in data
    assert data["oidc"]["enabled"] is False
