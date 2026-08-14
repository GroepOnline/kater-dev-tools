"""Catalog Connect API: admin gate, secret sink, and origin hardening.

In-process ROUTER only. No live provider calls, no token values in assertions
beyond placeholder names.
"""

from __future__ import annotations

import json

from tests._rest import call


def _fail_network(*_args, **_kwargs):
    raise AssertionError("catalog Connect tests must not open the network")


def test_public_non_admin_cannot_mutate_or_start_or_delete(monkeypatch) -> None:
    from kater.settings import KaterSettings, ServerConnection, ServerOverride, save_settings

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("KATER_CONNECT_PUBLIC_BASE_URL", "https://kater.example.test")
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    headers = {"authorization": "Bearer tool-secret"}

    creds = call(
        "POST",
        "/api/mcp/servers/github/credentials",
        body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "kater-test-token"}},
        headers=headers,
    )
    assert creds.status == 403
    assert creds.payload is not None
    assert creds.payload["error"] == "admin credential required for catalog mutations"

    start = call(
        "POST",
        "/api/mcp/servers/slack/oauth/start",
        body={},
        headers=headers,
    )
    assert start.status == 403
    assert start.payload is not None
    assert start.payload["error"] == "admin credential required for catalog mutations"
    dumped = json.dumps(start.payload)
    assert "evil" not in dumped
    assert "kater-test-token" not in dumped

    save_settings(
        KaterSettings(
            server_overrides={
                "slack": ServerOverride(
                    connections=[
                        ServerConnection(
                            id="acct1",
                            label="workspace-a",
                            env={"SLACK_ACCESS_TOKEN": "kater-test-access-token"},
                        )
                    ]
                )
            }
        )
    )
    listed = call("GET", "/api/mcp/servers/slack/connections", headers=headers)
    assert listed.status == 200
    assert listed.payload is not None
    assert listed.payload["connections"] == [
        {"id": "acct1", "label": "workspace-a", "created_at": 0.0}
    ]
    assert "kater-test-access-token" not in json.dumps(listed.payload)

    deleted = call(
        "DELETE",
        "/api/mcp/servers/slack/connections/acct1",
        headers=headers,
    )
    assert deleted.status == 403


def test_public_admin_cannot_persist_credentials_or_start_oauth(monkeypatch, tmp_path) -> None:
    from kater.settings import invalidate_settings_cache, settings_path

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("KATER_CONNECT_PUBLIC_BASE_URL", "https://kater.example.test")
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    invalidate_settings_cache()
    headers = {"authorization": "Bearer admin-secret"}

    creds = call(
        "POST",
        "/api/mcp/servers/github/credentials",
        body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "kater-test-token"}},
        headers=headers,
    )
    assert creds.status == 403
    assert creds.payload is not None
    assert creds.payload["error"] == "secret_sink_required"
    assert "kater-test-token" not in json.dumps(creds.payload)
    path = settings_path()
    if path.exists():
        assert "kater-test-token" not in path.read_text(encoding="utf-8")

    start = call(
        "POST",
        "/api/mcp/servers/slack/oauth/start",
        body={},
        headers=headers,
    )
    assert start.status == 403
    assert start.payload is not None
    assert start.payload["error"] == "secret_sink_required"
    assert "evil" not in json.dumps(start.payload)


def test_local_oauth_start_with_opt_in_preserves_pkce(monkeypatch) -> None:
    from urllib.parse import parse_qs, urlparse

    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    monkeypatch.setenv("SLACK_MCP_CLIENT_ID", "kater-test-client-id")
    monkeypatch.setattr("kater.mcp_oauth.discover_scopes", lambda _source: "users:read")
    resp = call("POST", "/api/mcp/servers/slack/oauth/start", body={"label": "workspace-a"})
    assert resp.status == 200
    assert resp.payload is not None
    parsed = urlparse(resp.payload["authorize_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "slack.com"
    assert query["state"] == [resp.payload["state"]]
    assert "code_challenge" in query
    assert resp.payload["redirect_uri"].startswith("http://127.0.0.1")
    dumped = json.dumps(resp.payload)
    assert "kater-test-access" not in dumped
    assert "verifier" not in dumped


def test_local_oauth_start_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    monkeypatch.delenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", raising=False)
    resp = call("POST", "/api/mcp/servers/slack/oauth/start", body={})
    assert resp.status == 403
    assert resp.payload is not None
    assert resp.payload["error"] == "local_settings_opt_in_required"


def test_local_oauth_start_rejects_hostile_request_base(monkeypatch) -> None:
    from kater.api import ROUTER, Request

    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    matched = ROUTER.match("POST", "/api/mcp/servers/slack/oauth/start")
    assert matched is not None
    route, params = matched
    req = Request(
        method="POST",
        path="/api/mcp/servers/slack/oauth/start",
        query={},
        headers={},
        raw_body=b"{}",
        client_ip="127.0.0.1",
        base_url="http://evil.example",
        params=params,
    )
    resp = route.handler(req)
    assert resp.status == 400
    assert resp.payload is not None
    assert resp.payload["error"] == "dev_base_url_must_be_loopback"
    assert "evil" not in json.dumps(resp.payload)


def test_public_oauth_start_ignores_hostile_host_and_requires_https_base(monkeypatch) -> None:
    from kater.api import ROUTER, Request

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    monkeypatch.delenv("KATER_CONNECT_PUBLIC_BASE_URL", raising=False)
    matched = ROUTER.match("POST", "/api/mcp/servers/slack/oauth/start")
    assert matched is not None
    route, params = matched
    req = Request(
        method="POST",
        path="/api/mcp/servers/slack/oauth/start",
        query={},
        headers={"authorization": "Bearer admin-secret"},
        raw_body=b"{}",
        client_ip="127.0.0.1",
        base_url="http://evil.example",
        params=params,
    )
    resp = route.handler(req)
    assert resp.status == 400
    assert resp.payload is not None
    assert resp.payload["error"] == "public_base_url_required"
    assert "evil" not in json.dumps(resp.payload)

    monkeypatch.setenv("KATER_CONNECT_PUBLIC_BASE_URL", "http://kater.example.test")
    resp = route.handler(req)
    assert resp.status == 400
    assert resp.payload is not None
    assert resp.payload["error"] == "public_base_url_must_be_https"


def test_callback_does_not_exchange_when_sink_gate_fails(tmp_path, monkeypatch) -> None:
    from kater.mcp_oauth import peek_pending, start_authorize
    from kater.profiles import get_source
    from kater.settings import invalidate_settings_cache

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    monkeypatch.setattr("kater.mcp_oauth.discover_scopes", lambda _source: "users:read")
    source = get_source("slack")
    assert source is not None and source.oauth is not None
    started = start_authorize(
        source,
        client_id="kater-test-client-id",
        base_url="http://127.0.0.1:9091",
    )
    monkeypatch.delenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS")
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_CONNECT_PUBLIC_BASE_URL", "https://kater.example.test")
    invalidate_settings_cache()
    monkeypatch.setattr("kater.mcp_oauth.urllib.request.urlopen", _fail_network)

    resp = call(
        "GET",
        "/api/mcp/oauth/callback",
        query={"state": [started["state"]], "code": ["kater-test-code"]},
    )
    assert resp.status == 403
    body = (resp.body or b"").decode()
    assert "secret storage is not enabled" in body
    assert "kater-test-code" not in body
    assert "kater-test-access" not in body
    assert peek_pending(started["state"]) == {}
