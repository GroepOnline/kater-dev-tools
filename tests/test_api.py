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
def clean_kater_dir():
    from kater.storage import reset_db_cache

    reset_db_cache()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)
    yield
    reset_db_cache()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", 9912)
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


def _post(port: int, path: str, body: dict, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
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


# ── Basic endpoints ────────────────────────────────────────────────


def test_health(api_server) -> None:
    data = _get(9912, "/health")
    assert data["status"] == "ok"
    assert "version" in data
    assert data["auth_mode"] == "none"


def test_profiles(api_server) -> None:
    data = _get(9912, "/api/profiles")
    assert "core" in data["profiles"]
    assert "ops" in data["profiles"]


def test_mcp_servers(api_server) -> None:
    data = _get(9912, "/api/mcp/servers")
    assert data["total"] > 15
    names = {s["name"] for s in data["servers"]}
    assert "github" in names
    assert "cloudflare" in names
    assert "sentry" in names
    assert "context7" in names
    assert "notion" in names


def test_mcp_server_detail(api_server) -> None:
    data = _get(9912, "/api/mcp/servers/github")
    assert data["name"] == "github"
    assert data["transport"] == "stdio"
    assert data["mcp"]["command"] == "npx"
    assert data["enabled"] is True


def test_adapters(api_server) -> None:
    data = _get(9912, "/api/adapters")
    assert "adapters" in data
    assert "total" in data


def test_doctor(api_server) -> None:
    data = _get(9912, "/api/doctor")
    assert "findings" in data
    assert "profiles" in data


def test_chains(api_server) -> None:
    data = _get(9912, "/api/chains")
    assert "chains" in data


def test_chain_run(api_server) -> None:
    data = _post(9912, "/api/chains/run", {"name": "research_brief", "profile": "research"})
    assert data["chain"] == "research_brief"
    assert len(data["steps"]) == 3


def test_404(api_server) -> None:
    err = _get_err(9912, "/api/nonexistent")
    assert err.code == 404


# ── Settings ───────────────────────────────────────────────────────


def test_get_settings(api_server) -> None:
    data = _get(9912, "/api/settings")
    assert data["version"] == 2
    assert data["auth"]["mode"] == "none"


def test_update_settings(api_server) -> None:
    data = _post(9912, "/api/settings", {
        "cors_origins": ["https://example.com"],
        "rate_limit_per_min": 100,
    })
    assert data["cors_origins"] == ["https://example.com"]
    assert data["rate_limit_per_min"] == 100


# ── Enable / disable ───────────────────────────────────────────────


def test_disable_server(api_server) -> None:
    data = _post(9912, "/api/mcp/servers/github/disable", {})
    assert data["name"] == "github"
    assert data["enabled"] is False

    detail = _get(9912, "/api/mcp/servers/github")
    assert detail["enabled"] is False


def test_enable_server(api_server) -> None:
    _post(9912, "/api/mcp/servers/sentry/disable", {})
    data = _post(9912, "/api/mcp/servers/sentry/enable", {})
    assert data["enabled"] is True


def test_toggle_server(api_server) -> None:
    data = _post(9912, "/api/mcp/servers/exa/toggle", {})
    assert data["enabled"] is False
    data = _post(9912, "/api/mcp/servers/exa/toggle", {})
    assert data["enabled"] is True


# ── Deploy ─────────────────────────────────────────────────────────


def test_deploy_formats(api_server) -> None:
    data = _get(9912, "/api/deploy")
    names = {f["name"] for f in data["formats"]}
    assert "docker" in names
    assert "cloudflare" in names


def test_deploy_render(api_server) -> None:
    data = _get(9912, "/api/deploy/docker")
    assert data["format"] == "docker-compose"


# ── Auth ───────────────────────────────────────────────────────────


def test_auth_blocks_without_key(api_server) -> None:
    _post(9912, "/api/settings", {"auth": {"mode": "apikey", "api_keys": ["test-secret"]}})
    err = _get_err(9912, "/api/profiles")
    assert err.code == 401


def test_auth_allows_with_key(api_server) -> None:
    _post(9912, "/api/settings", {"auth": {"mode": "apikey", "api_keys": ["test-secret"]}})
    data = _get(9912, "/api/profiles", headers={"Authorization": "Bearer test-secret"})
    assert "core" in data["profiles"]


def test_auth_health_always_open(api_server) -> None:
    _post(9912, "/api/settings", {"auth": {"mode": "apikey", "api_keys": ["test-secret"]}})
    data = _get(9912, "/health")
    assert data["status"] == "ok"
    assert data["auth_mode"] == "apikey"


# ── Catalog ────────────────────────────────────────────────────────


def test_catalog(api_server) -> None:
    data = _get(9912, "/api/catalog")
    assert data["total"] > 15
    assert "by_transport" in data
    assert "by_risk" in data
    assert "stdio" in data["by_transport"]
    assert "high" in data["by_risk"]


# ── Spec ───────────────────────────────────────────────────────────


def test_openapi_spec(api_server) -> None:
    data = _get(9912, "/api/spec")
    assert data["openapi"] == "3.1.0"
    assert "paths" in data
    assert "/health" in data["paths"]
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
        _normalize_path(r.pattern)
        for r in ROUTER._routes
        if r.pattern.startswith("/api/")
    }
    spec_api = {
        _normalize_path(p)
        for p in generate_spec()["paths"]
        if p.startswith("/api/")
    }
    assert router_api == spec_api, {
        "documented_but_missing": spec_api - router_api,
        "undocumented_routes": router_api - spec_api,
    }


# ── Export ─────────────────────────────────────────────────────────


def test_export(api_server) -> None:
    data = _get(9912, "/api/export")
    assert "version" in data
    assert "exported_at" in data
    assert "auth" in data


# ── Status ─────────────────────────────────────────────────────────


def test_status(api_server) -> None:
    data = _get(9912, "/api/status")
    assert data["version"] is not None
    assert "servers" in data
    assert "telemetry" in data
    assert data["storage_backend"] in ("sqlite", "jsonl")


# ── Dashboard ──────────────────────────────────────────────────────


def test_dashboard_html(api_server) -> None:
    resp = urllib.request.urlopen("http://127.0.0.1:9912/")
    body = resp.read().decode()
    assert "<!DOCTYPE html>" in body
    assert "constellation-canvas" in body
    assert "cmd-input" in body
    assert "KATER" in body
    assert resp.headers.get("Content-Type", "").startswith("text/html")
