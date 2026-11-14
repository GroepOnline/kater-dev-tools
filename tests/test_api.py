from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from kater.api import create_api_server
from tests.portutil import free_port


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", free_port())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.2)


def _api_port(server) -> int:
    return int(server.server_address[1])


def _get(port: int, path: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers=headers or {},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def _delete(port: int, path: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method="DELETE",
        headers=headers or {},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def _post(port: int, path: str, body: dict, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def _post_err(
    port: int, path: str, body: dict, headers: dict | None = None
) -> urllib.error.HTTPError:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        return e
    pytest.fail("Expected HTTPError")


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


def test_public_path_fails_closed_on_an_invalid_context_token(api_server) -> None:
    """A public route ignores absent credentials, but not an invalid one.

    ``/health`` skips the credential check, so an explicit but unverifiable
    ``X-Kater-Context`` must be rejected rather than silently downgraded to
    anonymous access.
    """
    assert _get(_api_port(api_server), "/health")["status"] == "ok"

    err = _get_err(_api_port(api_server), "/health", headers={"X-Kater-Context": "garbage"})
    assert err.code == 401
    assert json.loads(err.read().decode())["error"] == "Invalid context token."


def test_cors_advertises_the_context_header_and_mutating_methods(api_server) -> None:
    """Preflight must allow X-Kater-Context and the PATCH/DELETE routes."""
    req = urllib.request.Request(
        f"http://127.0.0.1:{_api_port(api_server)}/api/profiles",
        method="OPTIONS",
        headers={"Origin": "http://127.0.0.1"},
    )
    resp = urllib.request.urlopen(req)
    allowed_headers = resp.headers.get("Access-Control-Allow-Headers", "")
    allowed_methods = resp.headers.get("Access-Control-Allow-Methods", "")
    assert "X-Kater-Context" in allowed_headers
    assert "Authorization" in allowed_headers
    for method in ("GET", "POST", "PATCH", "DELETE", "OPTIONS"):
        assert method in allowed_methods


# ── Basic endpoints ────────────────────────────────────────────────


def test_health(api_server) -> None:
    data = _get(_api_port(api_server), "/health")
    assert data["status"] == "ok"
    assert "version" in data
    assert data["auth_mode"] == "none"


def test_health_live(api_server) -> None:
    data = _get(_api_port(api_server), "/health/live")
    assert data["status"] == "ok"
    assert "version" in data
    assert data["auth_mode"] == "none"


def test_health_ready(api_server) -> None:
    data = _get(_api_port(api_server), "/health/ready")
    assert data["status"] in {"ok", "degraded", "unhealthy"}
    assert data["service"] == "kater"
    assert "components" in data
    assert "api" in data["components"]
    assert "mcp" in data["components"]


def test_profiles(api_server) -> None:
    data = _get(_api_port(api_server), "/api/profiles")
    assert "core" in data["profiles"]
    assert "ops" in data["profiles"]


def test_mcp_servers(api_server) -> None:
    data = _get(_api_port(api_server), "/api/mcp/servers")
    assert data["total"] > 15
    names = {s["name"] for s in data["servers"]}
    assert "github" in names
    assert "cloudflare" in names
    assert "sentry" in names
    assert "context7" in names
    assert "notion" in names


def test_mcp_server_detail(api_server) -> None:
    data = _get(_api_port(api_server), "/api/mcp/servers/github")
    assert data["name"] == "github"
    assert data["transport"] == "stdio"
    assert data["mcp"]["command"] == "npx"
    assert data["enabled"] is True


def test_adapters(api_server) -> None:
    data = _get(_api_port(api_server), "/api/adapters")
    assert "adapters" in data
    assert "total" in data


def test_doctor(api_server) -> None:
    data = _get(_api_port(api_server), "/api/doctor")
    assert "findings" in data
    assert "profiles" in data


def test_doctor_honors_query_profile_with_multi_profile_runtime(api_server, monkeypatch) -> None:
    monkeypatch.setenv("KATER_PROFILE", "ops,cloud,research,code,web")

    data = _get(_api_port(api_server), "/api/doctor?profile=ops")

    assert data["profiles"] == ["ops"]
    assert len(data["sources"]) > 1


def test_chains(api_server) -> None:
    data = _get(_api_port(api_server), "/api/chains")
    assert "chains" in data


def test_chain_run(api_server) -> None:
    data = _post(
        _api_port(api_server), "/api/chains/run", {"name": "research_brief", "profile": "research"}
    )
    assert data["chain"] == "research_brief"
    assert len(data["steps"]) == 3


def test_404(api_server) -> None:
    err = _get_err(_api_port(api_server), "/api/nonexistent")
    assert err.code == 404


# ── Settings ───────────────────────────────────────────────────────


def test_get_settings(api_server) -> None:
    data = _get(_api_port(api_server), "/api/settings")
    assert data["version"] == 2
    assert data["auth"]["mode"] == "none"


def test_update_settings_auth_partial_patch(api_server) -> None:
    # First set full auth config
    _post(
        _api_port(api_server),
        "/api/settings",
        {"auth": {"mode": "apikey", "api_keys": ["secret1"], "oauth_issuer": "https://issuer.com"}},
    )

    # Then apply partial patch (e.g., just changing mode).
    # Since we set mode=apikey, we need to authenticate with the key!
    data = _post(
        _api_port(api_server),
        "/api/settings",
        {"auth": {"mode": "oauth"}},
        headers={"Authorization": "Bearer secret1"},
    )

    # Verify that unspecified fields are not wiped
    assert data["auth"]["mode"] == "oauth"

    # Because api_keys is redacted from the API response (replaced with length),
    # we load raw settings to verify it exactly
    from kater.settings import load_settings

    settings = load_settings()
    assert settings.auth.mode == "oauth"
    assert settings.auth.api_keys == ["secret1"]
    assert settings.auth.oauth_issuer == "https://issuer.com"


def test_update_settings(api_server) -> None:
    data = _post(
        _api_port(api_server),
        "/api/settings",
        {
            "cors_origins": ["https://example.com"],
            "rate_limit_per_min": 100,
        },
    )
    assert data["cors_origins"] == ["https://example.com"]
    assert data["rate_limit_per_min"] == 100


# ── Enable / disable ───────────────────────────────────────────────


def test_disable_server(api_server) -> None:
    data = _post(_api_port(api_server), "/api/mcp/servers/github/disable", {})
    assert data["name"] == "github"
    assert data["enabled"] is False

    detail = _get(_api_port(api_server), "/api/mcp/servers/github")
    assert detail["enabled"] is False


def test_enable_server(api_server) -> None:
    _post(_api_port(api_server), "/api/mcp/servers/sentry/disable", {})
    data = _post(_api_port(api_server), "/api/mcp/servers/sentry/enable", {})
    assert data["enabled"] is True


def test_toggle_server(api_server) -> None:
    data = _post(_api_port(api_server), "/api/mcp/servers/exa/toggle", {})
    assert data["enabled"] is False
    data = _post(_api_port(api_server), "/api/mcp/servers/exa/toggle", {})
    assert data["enabled"] is True


# ── Deploy ─────────────────────────────────────────────────────────


def test_deploy_formats(api_server) -> None:
    data = _get(_api_port(api_server), "/api/deploy")
    names = {f["name"] for f in data["formats"]}
    assert "docker" in names
    assert "cloudflare" in names


def test_deploy_render(api_server) -> None:
    data = _get(_api_port(api_server), "/api/deploy/docker")
    assert data["format"] == "docker-compose"


def test_deploy_render_unknown_format_404(api_server) -> None:
    err = _get_err(_api_port(api_server), "/api/deploy/nonexistent")
    assert err.code == 404
    body = err.read().decode()
    assert "Unknown format" in body
    assert "Available:" in body or "docker" in body


# ── Auth ───────────────────────────────────────────────────────────


def test_auth_blocks_without_key(api_server) -> None:
    _post(
        _api_port(api_server),
        "/api/settings",
        {"auth": {"mode": "apikey", "api_keys": ["test-secret"]}},
    )
    err = _get_err(_api_port(api_server), "/api/profiles")
    assert err.code == 401


def test_auth_allows_with_key(api_server) -> None:
    _post(
        _api_port(api_server),
        "/api/settings",
        {"auth": {"mode": "apikey", "api_keys": ["test-secret"]}},
    )
    data = _get(
        _api_port(api_server), "/api/profiles", headers={"Authorization": "Bearer test-secret"}
    )
    assert "core" in data["profiles"]


def test_auth_health_always_open(api_server) -> None:
    _post(
        _api_port(api_server),
        "/api/settings",
        {"auth": {"mode": "apikey", "api_keys": ["test-secret"]}},
    )
    for path in ("/health", "/health/live", "/health/ready"):
        data = _get(_api_port(api_server), path)
        assert data["status"] in {"ok", "degraded"}
        assert data["auth_mode"] == "apikey"


# ── Catalog ────────────────────────────────────────────────────────


def test_catalog(api_server) -> None:
    data = _get(_api_port(api_server), "/api/catalog")
    assert data["total"] > 15
    assert "by_transport" in data
    assert "by_risk" in data
    assert "by_category" in data
    assert "stdio" in data["by_transport"]
    assert "high" in data["by_risk"]
    first = data["servers"][0]
    assert "category" in first
    assert "auth_schemes" in first
    assert "toolkit_tools" in first

    search = _get(_api_port(api_server), "/api/catalog?q=brave")
    names = {s["name"] for s in search["servers"]}
    assert names == {"brave-search"}

    profile = _get(_api_port(api_server), "/api/catalog?profile=research")
    for server in profile["servers"]:
        assert "research" in server["profiles"]

    dev = _get(_api_port(api_server), "/api/catalog?category=dev")
    assert dev["total"] > 0
    for server in dev["servers"]:
        assert server["category"] == "dev"
    # Guard the model-validator auto-inference powering the catalog UX.
    by_name = {s["name"]: s for s in _get(_api_port(api_server), "/api/catalog")["servers"]}
    figma = by_name.get("figma")
    assert figma is not None, "figma missing from catalog"
    assert figma["auth_schemes"], "figma must declare at least one auth scheme"
    assert any(scheme in {"api_key", "bearer", "oauth2"} for scheme in figma["auth_schemes"]), (
        f"figma expected credentialed scheme, got {figma['auth_schemes']!r}"
    )
    assert figma["category"] == "productivity"
    assert len(figma["toolkit_tools"]) >= 1
    seq = by_name.get("sequential-thinking")
    assert seq is not None, "sequential-thinking missing from catalog"
    assert seq["auth_schemes"] == ["none"], (
        f"sequential-thinking expected exactly ['none'], got {seq['auth_schemes']!r}"
    )
    assert seq["category"] == "ai"


def test_catalog_connection_count(api_server) -> None:
    data = _get(_api_port(api_server), "/api/catalog")
    assert data["total"] > 0
    for s in data["servers"]:
        assert "connection_count" in s, f"server {s.get('name')!r} missing connection_count"
        assert isinstance(s["connection_count"], int)
        assert s["connection_count"] >= 0
    # figma has no oauth in its static config; count must be 0
    by_name = {s["name"]: s for s in data["servers"]}
    figma = by_name.get("figma")
    assert figma is not None, "figma missing from catalog"
    assert figma["connection_count"] == 0


def test_catalog_triggers_in_payload(api_server) -> None:
    data = _get(_api_port(api_server), "/api/catalog")
    for s in data["servers"]:
        assert "triggers" in s
        assert isinstance(s["triggers"], list)
        assert "connection_count" in s
        assert isinstance(s["connection_count"], int)
    github = next(s for s in data["servers"] if s["name"] == "github")
    assert len(github["triggers"]) >= 1
    assert github["triggers"][0]["cadence"] in {"realtime", "poll"}


def test_catalog_request_toolkit(api_server) -> None:
    port = _api_port(api_server)
    ok = _post(
        port,
        "/api/catalog/request",
        {"name": "figma-pro", "use_case": "design review", "contact": "team@x"},
    )
    assert ok["name"] == "figma-pro"
    assert ok["type"] == "toolkit_request"
    assert "queued_at" in ok

    err = _post_err(port, "/api/catalog/request", {})
    assert err.code == 422

    err_long = _post_err(port, "/api/catalog/request", {"name": "x" * 100})
    assert err_long.code == 422

    err_too_long_use_case = _post_err(
        port, "/api/catalog/request", {"name": "ok", "use_case": "u" * 501}
    )
    assert err_too_long_use_case.code == 422


def test_catalog_requests_list_admin_gate(api_server, monkeypatch) -> None:
    from kater.settings import invalidate_settings_cache

    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    invalidate_settings_cache()

    port = _api_port(api_server)

    # Without admin credential -> 403
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(port, "/api/catalog/requests")
    assert exc.value.code == 403

    # With admin credential -> 200 and request visible after submit
    _post(
        port,
        "/api/catalog/request",
        {"name": "admin-gated-queue", "use_case": "ops", "contact": "ops@x"},
    )
    data = _get(
        port, "/api/catalog/requests", headers={"Authorization": "Bearer admin-secret"}
    )
    assert data["total"] >= 1
    names = {row["name"] for row in data["requests"]}
    assert "admin-gated-queue" in names
    match = next(row for row in data["requests"] if row["name"] == "admin-gated-queue")
    assert match["use_case"] == "ops"
    assert match["contact"] == "ops@x"
    assert "queued_at" in match

    # Cleanup
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    invalidate_settings_cache()


def test_catalog_enable_integration_cases(api_server) -> None:
    # 404 on unknown toolkit
    err_404 = _post_err(_api_port(api_server), "/api/catalog/nonexistent_toolkit_xyz/enable", {})
    assert err_404.code == 404

    # 422 if credentials missing for server that requires env
    err_422 = _post_err(_api_port(api_server), "/api/catalog/figma/enable", {})
    assert err_422.code == 422

    # 400 if invalid env key supplied
    err_400 = _post_err(
        _api_port(api_server),
        "/api/catalog/figma/enable",
        {"auth": {"NOT_A_REAL_ENV_VAR": "secret123"}},
    )
    assert err_400.code == 400

    # Successful enable for no-auth toolkit -> 201 Created + metadata returned
    # Disable first to ensure predictable enable test
    _post(_api_port(api_server), "/api/mcp/servers/sequential-thinking/disable", {})
    res_201 = _post(
        _api_port(api_server),
        "/api/catalog/sequential-thinking/enable",
        {},
    )
    assert res_201["name"] == "sequential-thinking"
    assert res_201["enabled"] is True
    assert "category" in res_201
    assert "toolkit_tools" in res_201

    # 409 Duplicate / Already enabled
    err_409 = _post_err(
        _api_port(api_server),
        "/api/catalog/sequential-thinking/enable",
        {},
    )
    assert err_409.code == 409

    # Redaction: credentials passed to enable are not leaked in response
    _post(_api_port(api_server), "/api/mcp/servers/figma/disable", {})
    res_with_auth = _post(
        _api_port(api_server),
        "/api/catalog/figma/enable",
        {"auth": {"api_key": "figma_test_secret_value_123"}},
    )
    assert res_with_auth["name"] == "figma"
    assert res_with_auth["enabled"] is True
    assert "figma_test_secret_value_123" not in json.dumps(res_with_auth)

    # Clean up figma token
    import os
    os.environ.pop("FIGMA_API_KEY", None)


def test_catalog_triggers(api_server) -> None:
    data = _get(_api_port(api_server), "/api/catalog/github/triggers")
    assert data["name"] == "github"
    assert isinstance(data["triggers"], list)
    assert len(data["triggers"]) >= 1
    assert data["triggers"][0]["cadence"] in {"realtime", "poll"}
    assert data["triggers"][0]["name"]

    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(_api_port(api_server), "/api/catalog/nonexistent_xyz/triggers")
    assert exc.value.code == 404


def test_catalog_search_and_sort(api_server) -> None:
    ai = _get(_api_port(api_server), "/api/catalog?q=ai")
    assert ai["total"] >= 1
    assert any(
        "ai" in s["name"].lower()
        or "ai" in s["description"].lower()
        or any("ai" in t["name"].lower() for t in s.get("toolkit_tools", []) or [])
        for s in ai["servers"]
    )

    pop = _get(_api_port(api_server), "/api/catalog?sort=popularity")
    assert pop["total"] > 0
    first = pop["servers"][0]
    # First should have a trigger or be alphabetical if no triggers
    assert "trigger_count" in first or first["name"] <= pop["servers"][-1]["name"]


def test_update_storage_backend(api_server) -> None:
    updated = _post(_api_port(api_server), "/api/settings", {"storage_backend": "jsonl"})
    assert updated["storage_backend"] == "jsonl"
    assert _get(_api_port(api_server), "/api/settings")["storage_backend"] == "jsonl"

    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(_api_port(api_server), "/api/settings", {"storage_backend": "redis"})
    assert exc.value.code == 400


def test_server_credentials(api_server, monkeypatch) -> None:
    import os

    try:
        ok = _post(
            _api_port(api_server),
            "/api/mcp/servers/github/credentials",
            {"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "tok123"}},
        )
        assert ok["env_configured"] is True
        assert ok["applied"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]
        # The server reports configured now that the credential is set.
        detail = _get(_api_port(api_server), "/api/mcp/servers/github")
        assert detail["env_configured"] is True

        # Only declared credentials are accepted (no arbitrary env injection).
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(
                _api_port(api_server), "/api/mcp/servers/github/credentials", {"env": {"NOPE": "x"}}
            )
        assert exc.value.code == 400

        removed = _delete(_api_port(api_server), "/api/mcp/servers/github/connections/legacy")
        assert removed["removed"] == "legacy"
        assert removed["env_configured"] is False
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" not in os.environ
        detail = _get(_api_port(api_server), "/api/mcp/servers/github")
        assert detail["env_configured"] is False
    finally:
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)


def test_settings_redacts_server_credentials(api_server, monkeypatch) -> None:
    import os

    try:
        _post(
            _api_port(api_server),
            "/api/mcp/servers/github/credentials",
            {"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "supersecret-token"}},
        )
        raw = _get(_api_port(api_server), "/api/settings")
        assert "supersecret-token" not in json.dumps(raw)
        stored = raw["server_overrides"]["github"]["env"]
        assert stored["GITHUB_PERSONAL_ACCESS_TOKEN"] == "***"
    finally:
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)


def test_catalog_oauth_start_deny_default_without_client(api_server, monkeypatch) -> None:
    import os

    monkeypatch.setattr("kater.mcp_oauth.discover_scopes", lambda _source: "users:read")
    os.environ.pop("SLACK_MCP_CLIENT_ID", None)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(_api_port(api_server), "/api/mcp/servers/slack/oauth/start", {})
    assert exc.value.code == 409
    body = json.loads(exc.value.read().decode())
    assert body["error"] == "oauth_app_missing"
    assert body["setup"]["client_id_env"] == "SLACK_MCP_CLIENT_ID"
    assert body["setup"]["client_secret_env"] == "SLACK_MCP_CLIENT_SECRET"
    dumped = json.dumps(body)
    assert "kater-test-" not in dumped
    listed = _get(_api_port(api_server), "/api/mcp/servers/slack/connections")
    assert listed["connections"] == []
    catalog = _get(_api_port(api_server), "/api/catalog?q=slack")
    slack = next(s for s in catalog["servers"] if s["name"] == "slack")
    assert slack["oauth"]["provider"] == "slack"
    assert slack["oauth"]["client_configured"] is False
    assert "token" not in json.dumps(slack["oauth"]["connections"])


def test_private_server_hidden_in_public_mode(monkeypatch) -> None:
    # A public deployment must not acknowledge private (org-only) servers at all.
    # The detail/toggle/credentials handlers all gate through _visible_source,
    # so a None result there is what turns into a 404 for every one of them.
    from kater.api import _visible_source

    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    assert _visible_source("demo_private_server") is not None

    monkeypatch.setenv("KATER_PUBLIC", "1")
    assert _visible_source("demo_private_server") is None
    assert _visible_source("github") is not None


# ── Spec ───────────────────────────────────────────────────────────


def test_openapi_spec(api_server) -> None:
    data = _get(_api_port(api_server), "/api/spec")
    assert data["openapi"] == "3.1.0"
    assert "paths" in data
    assert "/health" in data["paths"]
    assert "/health/live" in data["paths"]
    assert "/health/ready" in data["paths"]
    assert "/api/catalog" in data["paths"]


def _normalize_path(path: str) -> str:
    import re

    return re.sub(r"\{[^}]+\}", "{}", path)


def test_openapi_spec_has_no_api_drift() -> None:
    # Single source of truth: every /api/* route must be documented and vice
    # versa (param names normalized, so /api/deploy/{fmt} == /api/deploy/{format}).
    from kater.api import ROUTER
    from kater.openapi_spec import generate_spec

    router_api = {
        _normalize_path(r.pattern) for r in ROUTER._routes if r.pattern.startswith("/api/")
    }
    spec_api = {_normalize_path(p) for p in generate_spec()["paths"] if p.startswith("/api/")}
    assert router_api == spec_api, {
        "documented_but_missing": spec_api - router_api,
        "undocumented_routes": router_api - spec_api,
    }


# ── Export ─────────────────────────────────────────────────────────


def test_export(api_server) -> None:
    data = _get(_api_port(api_server), "/api/export")
    assert "version" in data
    assert "exported_at" in data
    assert "auth" in data


# ── Status ─────────────────────────────────────────────────────────


def test_status(api_server) -> None:
    data = _get(_api_port(api_server), "/api/status")
    assert data["version"] is not None
    assert "servers" in data
    assert "telemetry" in data
    assert data["storage_backend"] in ("sqlite", "jsonl")


# ── Dashboard ──────────────────────────────────────────────────────


def test_dashboard_html(api_server) -> None:
    resp = urllib.request.urlopen(f"http://127.0.0.1:{_api_port(api_server)}/")
    body = resp.read().decode()
    assert "<!DOCTYPE html>" in body
    assert "server-map" in body
    assert "route-table" in body or "Routing table" in body
    assert "cmd-input" in body
    assert "Kater" in body
    assert resp.headers.get("Content-Type", "").startswith("text/html")
