"""Outbound catalog OAuth client — mocked HTTP only, no live login or token mint."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from kater.connect_policy import ConnectOriginError
from kater.mcp_oauth import (
    abandon_pending,
    callback_html,
    consume_callback,
    peek_pending,
    redirect_uri,
    slack_app_manifest,
    start_authorize,
)
from kater.profiles import OAuthConnectConfig, RiskLevel, ToolSource, Transport


def _source(**overrides: object) -> ToolSource:
    oauth = OAuthConnectConfig(
        provider="slack",
        authorize_url="https://example.test/oauth/authorize",
        token_url="https://example.test/oauth/token",
        client_id_env="DEMO_CLIENT_ID",
        client_secret_env="DEMO_CLIENT_SECRET",
        token_env="DEMO_ACCESS_TOKEN",
        scopes=["users:read"],
        pkce=True,
        resource="https://example.test/mcp",
    )
    return ToolSource(
        name="demo-oauth",
        description="test",
        transport=Transport.HTTP,
        risk=RiskLevel.HIGH,
        profiles={"ops"},
        env=["DEMO_ACCESS_TOKEN"],
        oauth=oauth,
        **overrides,
    )


def test_redirect_uri_and_manifest_are_placeholders() -> None:
    callback = redirect_uri("http://127.0.0.1:9091")
    assert callback == "http://127.0.0.1:9091/api/mcp/oauth/callback"
    manifest = slack_app_manifest(callback)
    assert manifest["oauth_config"]["redirect_urls"] == [callback]


def test_start_authorize_deny_default_without_client_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="client id"):
        start_authorize(_source(), client_id="", base_url="http://127.0.0.1:9091")


def test_start_authorize_builds_url_without_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def _fail_open(*_args, **_kwargs):
        raise AssertionError("catalog Connect tests must not open the network")

    monkeypatch.setattr("kater.mcp_oauth.urllib.request.urlopen", _fail_open)
    started = start_authorize(
        _source(),
        client_id="kater-test-client-id",
        base_url="http://127.0.0.1:9091",
        label="workspace-a",
    )
    parsed = urlparse(started["authorize_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "example.test"
    assert query["client_id"] == ["kater-test-client-id"]
    assert query["response_type"] == ["code"]
    assert query["state"] == [started["state"]]
    assert "code_challenge" in query
    preview = peek_pending(started["state"])
    assert preview["server"] == "demo-oauth"
    assert "verifier" in preview
    pending = json.loads((tmp_path / ".kater" / "mcp-oauth-pending.json").read_text())
    assert started["state"] in pending


def test_consume_callback_unknown_state_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="unknown or expired"):
        consume_callback(
            state="missing-state",
            code="kater-test-code",
            client_id="kater-test-client-id",
            client_secret="",
            token_url="https://example.test/oauth/token",
            pkce=True,
        )


def test_consume_callback_exchanges_with_mocked_http(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    started = start_authorize(
        _source(),
        client_id="kater-test-client-id",
        base_url="http://127.0.0.1:9091",
    )

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "access_token": "kater-test-access-token",
                    "refresh_token": "kater-test-refresh-token",
                    "team": {"id": "T-TEST", "name": "Example"},
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def _fake_open(req, timeout=20):
        assert req.full_url == "https://example.test/oauth/token"
        return _Resp()

    monkeypatch.setattr("kater.mcp_oauth.urllib.request.urlopen", _fake_open)
    result = consume_callback(
        state=started["state"],
        code="kater-test-code",
        client_id="kater-test-client-id",
        client_secret="",
        token_url="https://example.test/oauth/token",
        pkce=True,
    )
    assert result["access_token"] == "kater-test-access-token"
    assert result["extra"]["team_id"] == "T-TEST"
    assert peek_pending(started["state"]) == {}


def test_start_authorize_rejects_hostile_non_loopback_http(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConnectOriginError, match="invalid_connect_base_url"):
        start_authorize(
            _source(),
            client_id="kater-test-client-id",
            base_url="http://evil.example",
        )
    assert not (tmp_path / ".kater" / "mcp-oauth-pending.json").exists()


def test_abandon_pending_drops_state_without_exchange(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    started = start_authorize(
        _source(),
        client_id="kater-test-client-id",
        base_url="http://127.0.0.1:9091",
    )
    dropped = abandon_pending(started["state"])
    assert dropped["server"] == "demo-oauth"
    assert peek_pending(started["state"]) == {}


def test_callback_html_escapes_error() -> None:
    page = callback_html(
        server="slack",
        label="",
        catalog_url="http://127.0.0.1:9091/?view=catalog",
        error="<script>alert(1)</script>",
    )
    assert "<script>alert(1)</script>" not in page
    assert "Connect failed" in page
