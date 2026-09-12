from __future__ import annotations

import json
import logging
import secrets
import shutil
import ssl
import subprocess
import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from kater.api import Request, create_api_server
from kater.api.server import handle
from kater.resource_auth import (
    AuthUnavailable,
    InsufficientScope,
    IntrospectionClient,
    InvalidToken,
    ResourceAuthConfig,
    ResourceAuthConfigurationError,
    ResourceAuthDisabled,
    parse_introspection,
)
from kater.runtime import KaterRuntime
from kater.settings import KaterSettings, ListenConfig, load_settings, save_settings, settings_path

ISSUER = "https://auth.example.test"
RESOURCE = "https://tools.example.test/mcp"
READ = frozenset({"tool:read"})
NOW = 1_800_000_000


@pytest.fixture
def config():
    return ResourceAuthConfig(
        enabled=True,
        issuer=ISSUER,
        resource=RESOURCE,
        allowed_scopes=("tool:read", "tool:write"),
    )


@pytest.fixture
def claims():
    # Exact response shape from Auth src/server/app.ts /v1/introspect.
    return {
        "active": True,
        "sub": "account-123",
        "plane": "internal",
        "scope": "tool:read tool:write",
        "aud": RESOURCE,
        "exp": NOW + 300,
    }


@pytest.fixture
def transport(monkeypatch, claims):
    connection = MagicMock()
    response = connection.getresponse.return_value
    response.status = 200
    response.getheader.return_value = "application/json; charset=utf-8"
    response.read.return_value = json.dumps(claims).encode()
    factory = MagicMock(return_value=connection)
    monkeypatch.setattr("kater.resource_auth.HTTPSConnection", factory)
    monkeypatch.setattr("kater.resource_auth.time.time", lambda: NOW)
    service_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("KATER_RESOURCE_AUTH_SERVICE_KEY", service_key)
    return factory, connection, response, service_key


def test_config_is_disabled_and_existing_auth_is_unchanged():
    settings = KaterSettings()
    assert settings.resource_auth == ResourceAuthConfig()
    assert settings.resource_auth.enabled is False
    assert settings.auth.mode == "none"


def test_settings_roundtrip_stores_only_service_key_env_name(tmp_path, config, transport):
    service_key = transport[3]
    settings = KaterSettings(resource_auth=config)
    save_settings(settings, tmp_path)
    assert load_settings(tmp_path).resource_auth == config
    for data in (settings.to_dict(), settings.to_safe_dict()):
        encoded = json.dumps(data)
        assert service_key not in encoded
        assert "KATER_RESOURCE_AUTH_SERVICE_KEY" in encoded


def test_invalid_persisted_contract_does_not_fall_back_to_disabled(tmp_path):
    path = settings_path(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({"resource_auth": {"enabled": True}}))
    with pytest.raises(ResourceAuthConfigurationError):
        load_settings(tmp_path)


def test_other_invalid_settings_cannot_disable_an_enabled_contract(tmp_path, config):
    path = settings_path(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({"resource_auth": config.model_dump(), "api_port": "invalid"}))
    with pytest.raises(ResourceAuthConfigurationError):
        load_settings(tmp_path)


def _persist_malformed_resource_auth(tmp_path, *, secret: str) -> None:
    path = settings_path(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({"resource_auth": {"enabled": True, "issuer": secret}}))


def test_gateway_configuration_errors_are_redacted_at_auth_and_body_size_boundaries(
    tmp_path, monkeypatch
):
    """Malformed resource auth state must not crash or reveal the persisted contract."""
    secret = "persisted-resource-auth-secret"
    monkeypatch.chdir(tmp_path)
    _persist_malformed_resource_auth(tmp_path, secret=secret)

    # Skip the separate rate-limit settings read to reach the authentication boundary.
    monkeypatch.setattr(
        "kater.api.server._get_rate_limiter", lambda: MagicMock(check=lambda _: True)
    )
    auth_response = handle(
        Request(
            method="GET",
            path="/api/profiles",
            query={},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://127.0.0.1",
        )
    )
    assert auth_response.status == 503
    assert auth_response.payload == {"error": "resource_auth_configuration_error"}
    assert secret not in auth_response.encoded().decode()

    server = create_api_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request(
            "POST",
            "/api/settings",
            body=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "1048577"},
        )
        response = connection.getresponse()
        body = response.read().decode()
        assert response.status == 503
        assert json.loads(body) == {"error": "resource_auth_configuration_error"}
        assert secret not in body
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_runtime_refuses_malformed_resource_auth_without_leaking_configuration(
    tmp_path, monkeypatch, caplog
):
    secret = "persisted-resource-auth-secret"
    monkeypatch.chdir(tmp_path)
    _persist_malformed_resource_auth(tmp_path, secret=secret)
    runtime = KaterRuntime(
        profile="core",
        listen=ListenConfig(host="127.0.0.1", api_port=0, mcp_port=0, ws_port=0),
    )

    with caplog.at_level(logging.ERROR, logger="kater.runtime"):
        with pytest.raises(ResourceAuthConfigurationError) as error:
            runtime.start()

    assert error.value.code == "resource_auth_configuration_error"
    assert "resource_auth_configuration_error" in caplog.text
    assert secret not in caplog.text
    assert runtime._started is False
    assert runtime._api_server is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "http://auth.example.test"),
        ("issuer", ISSUER + "/"),
        ("issuer", ISSUER + "/elsewhere"),
        ("issuer", "https://user:password@auth.example.test"),
        ("issuer", "https://AUTH.example.test"),
        ("issuer", " https://auth.example.test"),
        ("resource", "http://tools.example.test/mcp"),
        ("resource", RESOURCE + "?"),
        ("resource", RESOURCE + "#"),
        ("resource", RESOURCE + "?query=1"),
        ("resource", RESOURCE + "#fragment"),
        ("resource", "https://tools.example.test\\evil/mcp"),
        ("resource", "https://tools.example.test:bad/mcp"),
        ("resource", "https://tools.example.test/mcp\n"),
        ("resource", "https://tools.example.test/../mcp"),
        ("allowed_scopes", ()),
        ("allowed_scopes", ("tool:read", "tool:read")),
        ("allowed_scopes", ("tool:read tool:write",)),
        ("allowed_scopes", ("tool:read\t",)),
        ("service_key_env", "not-an-env-name"),
        ("timeout_seconds", 0),
        ("timeout_seconds", float("inf")),
        ("enabled", "true"),
    ],
)
def test_invalid_configuration_is_rejected(config, field, value):
    with pytest.raises(ValidationError):
        ResourceAuthConfig.model_validate({**config.model_dump(), field: value})


def test_enabling_requires_an_explicit_resource_contract():
    with pytest.raises(ValidationError):
        ResourceAuthConfig(enabled=True)


def test_disabled_client_does_not_contact_auth(transport):
    with pytest.raises(ResourceAuthDisabled) as error:
        IntrospectionClient(ResourceAuthConfig()).authenticate("opaque-token", required_scopes=READ)
    assert error.value.status_code == 503
    transport[0].assert_not_called()


def test_parse_exact_auth_contract(config, claims):
    principal = parse_introspection(claims, config=config, required_scopes=READ, now=NOW)
    assert principal.subject == "account-123"
    assert principal.issuer == ISSUER
    assert principal.audience == RESOURCE
    assert principal.plane == "internal"
    assert principal.scopes == frozenset({"tool:read", "tool:write"})
    assert principal.expires_at == NOW + 300
    with pytest.raises(AttributeError):
        principal.subject = "changed"


@pytest.mark.parametrize("field", ["active", "sub", "plane", "scope", "aud", "exp"])
def test_missing_claim_is_denied(config, claims, field):
    claims.pop(field)
    with pytest.raises(InvalidToken):
        parse_introspection(claims, config=config, required_scopes=READ, now=NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("active", False),
        ("active", 1),
        ("active", "true"),
        ("sub", ""),
        ("sub", 123),
        ("sub", "account\n123"),
        ("plane", "public"),
        ("plane", ["internal"]),
        ("aud", RESOURCE + "/"),
        ("aud", "https://other.example.test/mcp"),
        ("aud", [RESOURCE]),
        ("aud", RESOURCE.replace("https:", "http:")),
        ("scope", ["tool:read"]),
        ("scope", "tool:read\ttool:write"),
        ("scope", "tool:read  tool:write"),
        ("scope", "tool:read tool:read"),
        ("scope", "tool:read admin:all"),
        ("scope", 'tool:read "bad"'),
        ("exp", NOW),
        ("exp", NOW - 1),
        ("exp", str(NOW + 300)),
        ("exp", float(NOW + 300)),
        ("exp", True),
        ("exp", None),
        ("iss", "https://wrong.example.test"),
        ("iss", ISSUER + "/"),
    ],
)
def test_invalid_claim_is_denied(config, claims, field, value):
    claims[field] = value
    with pytest.raises(InvalidToken) as error:
        parse_introspection(claims, config=config, required_scopes=READ, now=NOW)
    assert error.value.status_code == 401
    assert error.value.code == "invalid_token"


@pytest.mark.parametrize("payload", [None, [], "active", {"active": False}])
def test_invalid_payload_is_denied(config, payload):
    with pytest.raises(InvalidToken):
        parse_introspection(payload, config=config, required_scopes=READ, now=NOW)


@pytest.mark.parametrize("scope", ["", "tool:write"])
def test_missing_required_scope_is_forbidden(config, claims, scope):
    claims["scope"] = scope
    with pytest.raises(InsufficientScope) as error:
        parse_introspection(claims, config=config, required_scopes=READ, now=NOW)
    assert error.value.status_code == 403


@pytest.mark.parametrize("required", [frozenset(), frozenset({"admin:all"})])
def test_invalid_required_scope_is_config_error_before_io(config, transport, required):
    with pytest.raises(ResourceAuthConfigurationError):
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=required)
    transport[0].assert_not_called()


def test_request_uses_resource_service_key_and_verified_tls(config, transport):
    factory, connection, _, service_key = transport
    principal = IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)
    assert principal.subject == "account-123"
    assert factory.call_args.args == ("auth.example.test",)
    assert factory.call_args.kwargs["timeout"] == config.timeout_seconds
    context = factory.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    args, kwargs = connection.request.call_args
    assert args == ("POST", "/v1/introspect")
    assert json.loads(kwargs["body"]) == {"token": "opaque-token", "resource": RESOURCE}
    assert kwargs["headers"]["Authorization"] == f"Bearer {service_key}"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    connection.close.assert_called_once()


def test_revocation_is_observed_on_next_call_without_positive_cache(config, transport):
    factory, _, response, _ = transport
    client = IntrospectionClient(config)
    client.authenticate("opaque-token", required_scopes=READ)
    response.read.return_value = b'{"active":false}'
    with pytest.raises(InvalidToken):
        client.authenticate("opaque-token", required_scopes=READ)
    assert factory.call_count == 2


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 429, 500, 503])
def test_upstream_error_never_redirects_retries_or_falls_back(config, transport, status):
    factory, connection, response, _ = transport
    response.status = status
    with pytest.raises(AuthUnavailable) as error:
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)
    assert error.value.status_code == 503
    assert factory.call_count == 1
    response.read.assert_not_called()
    connection.close.assert_called_once()


@pytest.mark.parametrize("failure", [TimeoutError, ConnectionError, ssl.SSLError])
def test_transport_failure_is_unavailable_and_redacted(config, transport, failure):
    factory, connection, _, service_key = transport
    connection.request.side_effect = failure(f"opaque-token {service_key}")
    with pytest.raises(AuthUnavailable) as error:
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)
    assert "opaque-token" not in str(error.value)
    assert service_key not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert factory.call_count == 1
    connection.close.assert_called_once()


def test_tls_setup_failure_is_unavailable(config, transport, monkeypatch):
    def unavailable():
        raise OSError("trust store unavailable")

    monkeypatch.setattr("kater.resource_auth.ssl.create_default_context", unavailable)
    with pytest.raises(AuthUnavailable):
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)
    transport[0].assert_not_called()


@pytest.mark.parametrize(
    "body",
    [b"not json", b"\xff", b"{}" * 16384, b'{"active":true,"active":false}', b'{"exp":NaN}'],
)
def test_unusable_upstream_body_is_unavailable(config, transport, body):
    transport[2].read.return_value = body
    with pytest.raises(AuthUnavailable):
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)


def test_non_json_content_type_is_unavailable(config, transport):
    transport[2].getheader.return_value = "text/html"
    with pytest.raises(AuthUnavailable):
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)


@pytest.mark.parametrize("key", [None, "short", "x" * 32 + "\n", "x" * 32 + "é"])
def test_missing_or_invalid_service_key_fails_before_io(config, transport, monkeypatch, key):
    monkeypatch.delenv(config.service_key_env, raising=False)
    if key is not None:
        monkeypatch.setenv(config.service_key_env, key)
    with pytest.raises(ResourceAuthConfigurationError):
        IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)
    transport[0].assert_not_called()


@pytest.mark.parametrize("token", ["", "x" * 8193, "Bearer token", "token\n", "é"])
def test_invalid_input_token_is_denied_before_io(config, transport, token):
    with pytest.raises(InvalidToken):
        IntrospectionClient(config).authenticate(token, required_scopes=READ)
    transport[0].assert_not_called()


def test_real_https_validation_revocation_and_untrusted_certificate(tmp_path, monkeypatch, claims):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is required to generate an ephemeral TLS test certificate")
    certificate = tmp_path / "certificate.pem"
    private_key = tmp_path / "private-key.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    service_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("KATER_RESOURCE_AUTH_SERVICE_KEY", service_key)
    monkeypatch.setattr("kater.resource_auth.time.time", lambda: NOW)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers["Authorization"], body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(claims).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(certificate, private_key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = ResourceAuthConfig(
        enabled=True,
        issuer=f"https://localhost:{server.server_port}",
        resource=RESOURCE,
        allowed_scopes=("tool:read", "tool:write"),
    )
    try:
        # The default trust store rejects this certificate before sending credentials.
        with pytest.raises(AuthUnavailable):
            IntrospectionClient(config).authenticate("opaque-token", required_scopes=READ)
        assert requests == []
        monkeypatch.setenv("SSL_CERT_FILE", str(certificate))
        client = IntrospectionClient(config)
        assert client.authenticate("opaque-token", required_scopes=READ).subject == "account-123"
        claims.clear()
        claims["active"] = False
        with pytest.raises(InvalidToken):
            client.authenticate("opaque-token", required_scopes=READ)
        assert (
            requests
            == [
                (
                    "/v1/introspect",
                    f"Bearer {service_key}",
                    {"token": "opaque-token", "resource": RESOURCE},
                )
            ]
            * 2
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"active": False}, True),
        ({"active": True}, False),
        ({"active": 0}, False),
        ({"error": "unavailable"}, False),
        ([], False),
    ],
)
def test_readiness_requires_explicit_inactive_response(config, transport, payload, expected):
    transport[2].read.return_value = json.dumps(payload).encode()
    assert IntrospectionClient(config).check_readiness() is expected
    sent = json.loads(transport[1].request.call_args.kwargs["body"])
    assert sent == {"token": "kater-readiness-deliberately-invalid", "resource": RESOURCE}
