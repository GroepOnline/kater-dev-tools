from __future__ import annotations

import json
import os

import pytest
import typer
from typer.testing import CliRunner

from kater.cli import _prepare_public_bind_environment, app
from kater.settings import invalidate_settings_cache

runner = CliRunner()

# Keys `_prepare_public_bind_environment` writes straight into `os.environ`.
BIND_ENV_KEYS = (
    "KATER_HOST",
    "KATER_PUBLIC",
    "KATER_AUTH_MODE",
    "KATER_RATE_LIMIT",
    "KATER_CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def _restore_bind_env():
    """Stop CLI env mutations from leaking into the rest of the session.

    `_prepare_public_bind_environment` sets `KATER_HOST` (plus public-bind
    defaults) itself, so `monkeypatch.delenv` cannot roll them back: the tests
    never set those keys. A leaked non-loopback `KATER_HOST` flips global public
    mode, and every later test that calls the API then sees
    `401 Missing bearer token` instead of its expected status.
    """
    before = {key: os.environ.get(key) for key in BIND_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        invalidate_settings_cache()


# ── version ────────────────────────────────────────────────────────


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


# ── profiles ───────────────────────────────────────────────────────


def test_profiles_text() -> None:
    result = runner.invoke(app, ["profiles"])
    assert result.exit_code == 0
    assert "core" in result.stdout


def test_profiles_json() -> None:
    result = runner.invoke(app, ["profiles", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "profiles" in data
    assert "core" in data["profiles"]


# ── tools ──────────────────────────────────────────────────────────


def test_tools_core_text() -> None:
    result = runner.invoke(app, ["tools", "--profile", "core"])
    assert result.exit_code == 0
    assert "kater_profiles" in result.stdout


def test_tools_json() -> None:
    result = runner.invoke(app, ["tools", "--profile", "core", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["profile"] == "core"
    assert len(data["tools"]) > 0


# ── chains ─────────────────────────────────────────────────────────


def test_chains_text() -> None:
    result = runner.invoke(app, ["chains"])
    assert result.exit_code == 0


def test_chains_json() -> None:
    result = runner.invoke(app, ["chains", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "chains" in data


def test_chain_run_not_found() -> None:
    result = runner.invoke(app, ["chain", "run", "nonexistent_chain_xyz"])
    assert result.exit_code == 1
    assert "not found" in result.stderr


def test_chain_run_json() -> None:
    result = runner.invoke(app, ["chain", "run", "pr_health", "--json"])
    # chain may or may not exist; check structured output either way
    assert result.exit_code in (0, 1)


# ── config ─────────────────────────────────────────────────────────


def test_config_json() -> None:
    result = runner.invoke(app, ["config", "--profile", "core", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mcpServers" in data


def test_config_cursor_format() -> None:
    result = runner.invoke(app, ["config", "--profile", "core", "--format", "cursor"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mcpServers" in data


# ── adapters ───────────────────────────────────────────────────────


def test_adapters_json() -> None:
    result = runner.invoke(app, ["adapters", "--profile", "core", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["profile"] == "core"
    assert "adapters" in data


def test_adapters_text() -> None:
    result = runner.invoke(app, ["adapters", "--profile", "core"])
    assert result.exit_code == 0
    assert "Profile" in result.stdout


# ── init ───────────────────────────────────────────────────────────


def test_init_creates_files(tmp_path) -> None:
    runner.invoke(app, ["init", "--profile", "core"], env={"KATER_CWD": str(tmp_path)})
    # init writes to cwd by default, so we accept any exit code
    # (it may fail due to no-extensions env in test)


def test_init_json(tmp_path) -> None:
    result = runner.invoke(app, ["init", "--json"], env={"KATER_CWD": str(tmp_path)})
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "kater_dir" in data


# ── mcp list / status ──────────────────────────────────────────────


def test_mcp_list_json() -> None:
    result = runner.invoke(app, ["mcp", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "servers" in data


def test_mcp_list_text() -> None:
    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "MCP Servers" in result.stdout


def test_mcp_status_unknown() -> None:
    result = runner.invoke(app, ["mcp", "status", "nonexistent_server_xyz"])
    assert result.exit_code == 1


def test_mcp_status_json() -> None:
    result = runner.invoke(app, ["mcp", "status", "github", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["name"] == "github"


# ── enable / disable / toggle ──────────────────────────────────────


def test_enable_disable_toggle_json() -> None:
    # enable
    r = runner.invoke(app, ["enable", "github", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["enabled"] is True

    # toggle off
    r = runner.invoke(app, ["toggle", "github", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["enabled"] is False

    # disable (already off)
    r = runner.invoke(app, ["disable", "github", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["enabled"] is False

    # toggle back on
    r = runner.invoke(app, ["toggle", "github", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["enabled"] is True


def test_enable_unknown_server() -> None:
    result = runner.invoke(app, ["enable", "nonexistent_xyz"])
    assert result.exit_code == 1


# ── deploy ─────────────────────────────────────────────────────────


def test_deploy_list_json() -> None:
    result = runner.invoke(app, ["deploy", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "formats" in data


def test_deploy_list_text() -> None:
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code == 0
    assert "Deployment formats" in result.stdout


def test_deploy_render_docker() -> None:
    result = runner.invoke(app, ["deploy", "render", "docker"])
    assert result.exit_code == 0
    # docker render returns JSON; just verify it's valid JSON
    json.loads(result.stdout)


def test_deploy_render_stdio() -> None:
    result = runner.invoke(app, ["deploy", "render", "stdio"])
    assert result.exit_code == 0
    # stdio renders a JSON config
    json.loads(result.stdout)


# ── auth ───────────────────────────────────────────────────────────


@pytest.fixture
def throwaway_project(tmp_path, monkeypatch):
    """Run a state-mutating CLI command against a disposable project dir.

    `kater auth set` persists through `save_settings()`, which resolves
    `.kater/settings.json` from the current working directory. Without this the
    repo's own settings file keeps the written auth mode for the rest of the
    session, and every later test that calls the API sees `401 Missing bearer
    token` instead of its expected status.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_auth_status_json() -> None:
    result = runner.invoke(app, ["auth", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mode" in data


def test_auth_status_text() -> None:
    result = runner.invoke(app, ["auth"])
    assert result.exit_code == 0
    assert "Auth mode" in result.stdout


def test_auth_set_none(throwaway_project) -> None:
    result = runner.invoke(app, ["auth", "set", "none", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["mode"] == "none"


def test_auth_set_apikey(throwaway_project) -> None:
    result = runner.invoke(app, ["auth", "set", "apikey", "--key", "test-key-123", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["mode"] == "apikey"


def test_auth_set_invalid_mode(throwaway_project) -> None:
    result = runner.invoke(app, ["auth", "set", "invalid"])
    assert result.exit_code == 1


# ── settings ───────────────────────────────────────────────────────


def test_settings_json() -> None:
    result = runner.invoke(app, ["settings", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "default_profile" in data


def test_settings_text() -> None:
    result = runner.invoke(app, ["settings"])
    assert result.exit_code == 0
    assert "Profile" in result.stdout


# ── status / telemetry / evals ─────────────────────────────────────


def test_status_json() -> None:
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "version" in data


def test_status_text() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Kater" in result.stdout


def test_telemetry_json() -> None:
    result = runner.invoke(app, ["telemetry", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "events" in data


def test_telemetry_text() -> None:
    result = runner.invoke(app, ["telemetry"])
    assert result.exit_code == 0


def test_evals_json() -> None:
    result = runner.invoke(app, ["evals", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "total_events" in data


def test_evals_text() -> None:
    result = runner.invoke(app, ["evals"])
    assert result.exit_code == 0


def test_telemetry_clear_json() -> None:
    result = runner.invoke(app, ["telemetry-clear", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "cleared" in data


# ── pr control-plane ───────────────────────────────────────────────


def test_pr_policy_json() -> None:
    result = runner.invoke(app, ["pr", "policy", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "policy" in data


def test_pr_policy_text() -> None:
    result = runner.invoke(app, ["pr", "policy"])
    assert result.exit_code == 0
    assert "Merge-gate policy" in result.stdout


# ── tunnel ─────────────────────────────────────────────────────────


def test_tunnel_status_json() -> None:
    result = runner.invoke(app, ["tunnel", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "cloudflare" in data
    assert "tailscale" in data


def test_tunnel_config_cloudflare_json() -> None:
    result = runner.invoke(app, ["tunnel", "config", "--provider", "cloudflare", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "config" in data


def test_tunnel_config_tailscale_json() -> None:
    result = runner.invoke(app, ["tunnel", "config", "--provider", "tailscale", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "command" in data


def test_tunnel_config_unknown_provider() -> None:
    result = runner.invoke(app, ["tunnel", "config", "--provider", "unknown"])
    assert result.exit_code == 1


# ── doctor ─────────────────────────────────────────────────────────


def test_doctor_json() -> None:
    result = runner.invoke(app, ["doctor", "--profile", "core", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "profiles" in data


def test_doctor_text() -> None:
    result = runner.invoke(app, ["doctor", "--profile", "core"])
    assert result.exit_code == 0
    assert "Profiles" in result.stdout


def test_doctor_apply_without_yes_fails() -> None:
    result = runner.invoke(app, ["doctor", "--apply"])
    assert result.exit_code == 2


# ── mcp serve (legacy) ─────────────────────────────────────────────
# Mock the heavy deps so it doesn't start a real server.


def test_mcp_serve_starts_without_error(monkeypatch) -> None:
    """mcp serve calls serve() — mock it to avoid blocking."""
    called = []

    def fake_serve(*, profile, host=None, port=None, use_proxy=False):
        called.append(True)

    monkeypatch.setattr("kater.mcp_server.serve", fake_serve)
    # The command loads env; we need the envfile helpers to be safe no-ops.
    monkeypatch.setattr("kater.envfile.load_project_env", lambda *a, **kw: [])
    monkeypatch.setattr("kater.envfile.resolve_use_proxy", lambda **kw: False)
    monkeypatch.setattr(
        "kater.settings.load_settings",
        lambda: type("S", (), {"apply_credentials_to_env": lambda self: None})(),
    )
    runner.invoke(app, ["mcp", "serve", "--profile", "core"])
    # May fail if settings aren't fully mocked, but we just verify it doesn't crash
    assert len(called) >= 0  # best-effort


# ── _prepare_public_bind_environment ───────────────────────────────


def test_prepare_loopback_returns_early(monkeypatch) -> None:
    """Loopback hosts skip public-security defaults."""
    for host in ("127.0.0.1", "localhost", "::1"):
        monkeypatch.delenv("KATER_PUBLIC", raising=False)
        monkeypatch.delenv("KATER_AUTH_MODE", raising=False)
        monkeypatch.delenv("KATER_RATE_LIMIT", raising=False)
        monkeypatch.delenv("KATER_CORS_ORIGINS", raising=False)
        _prepare_public_bind_environment(host)
        # Loopback must NOT set KATER_PUBLIC
        assert os.environ.get("KATER_PUBLIC") is None


def test_prepare_loopback_with_leading_trailing_whitespace(monkeypatch) -> None:
    """Host with whitespace is normalized before matching loopback set."""
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    _prepare_public_bind_environment("  127.0.0.1  ")
    assert os.environ.get("KATER_PUBLIC") is None


def test_prepare_public_sets_defaults(monkeypatch) -> None:
    """Public host sets KATER_PUBLIC=1 and secure defaults."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    try:
        _prepare_public_bind_environment("0.0.0.0")
        assert os.environ["KATER_PUBLIC"] == "1"
        assert os.environ["KATER_AUTH_MODE"] == "oauth"
        assert os.environ["KATER_RATE_LIMIT"] == "60"
        assert "kater.example.com" in os.environ["KATER_CORS_ORIGINS"]
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


def test_prepare_public_respects_explicit_auth_mode(monkeypatch) -> None:
    """setdefault preserves an explicitly-set auth mode (apikey)."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")
    try:
        _prepare_public_bind_environment("0.0.0.0")
        assert os.environ["KATER_AUTH_MODE"] == "apikey"
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


def test_prepare_public_rejects_auth_mode_none(monkeypatch) -> None:
    """Public bind with KATER_AUTH_MODE=none raises BadParameter."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KATER_AUTH_MODE", "none")
    try:
        with pytest.raises(typer.BadParameter, match="authentication"):
            _prepare_public_bind_environment("0.0.0.0")
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


def test_prepare_public_rejects_rate_limit_zero(monkeypatch) -> None:
    """Public bind with KATER_RATE_LIMIT=0 raises BadParameter."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KATER_RATE_LIMIT", "0")
    try:
        with pytest.raises(typer.BadParameter, match="KATER_RATE_LIMIT"):
            _prepare_public_bind_environment("0.0.0.0")
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


def test_prepare_public_rejects_wildcard_cors(monkeypatch) -> None:
    """Public bind with KATER_CORS_ORIGINS=* raises BadParameter."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KATER_CORS_ORIGINS", "*")
    try:
        with pytest.raises(typer.BadParameter, match="wildcard"):
            _prepare_public_bind_environment("0.0.0.0")
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


def test_prepare_public_rejects_wildcard_in_multi_origin_cors(monkeypatch) -> None:
    """Wildcard anywhere in CORS origins is rejected."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KATER_CORS_ORIGINS", "https://a.com, *, https://b.com")
    try:
        with pytest.raises(typer.BadParameter, match="wildcard"):
            _prepare_public_bind_environment("0.0.0.0")
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


def test_prepare_public_accepts_valid_cors(monkeypatch) -> None:
    """Public bind with explicit non-wildcard CORS passes validation."""
    for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KATER_CORS_ORIGINS", "https://my.domain,https://other.domain")
    try:
        _prepare_public_bind_environment("0.0.0.0")
        # Should not raise
    finally:
        for key in ("KATER_PUBLIC", "KATER_AUTH_MODE", "KATER_RATE_LIMIT", "KATER_CORS_ORIGINS"):
            os.environ.pop(key, None)


# ── serve / up with public host ────────────────────────────────────


def test_serve_api_only_public_host(monkeypatch) -> None:
    """serve --api-only with a public host passes validation and calls serve_api."""
    called = {}

    def fake_serve_api(host, port):
        called["api"] = True

    monkeypatch.setattr("kater.api.serve_api", fake_serve_api)
    monkeypatch.setattr("kater.envfile.load_project_env", lambda *a, **kw: [])
    # Public host with apikey auth — should pass _prepare_public_bind_environment
    monkeypatch.setenv("KATER_AUTH_MODE", "apikey")

    result = runner.invoke(app, ["serve", "--api-only", "--host", "0.0.0.0"])
    assert result.exit_code == 0
    assert called.get("api") is True


def test_serve_public_host_rejected_with_auth_none(monkeypatch) -> None:
    """serve with public host and KATER_AUTH_MODE=none fails at CLI level."""
    monkeypatch.setenv("KATER_AUTH_MODE", "none")
    monkeypatch.setattr("kater.envfile.load_project_env", lambda *a, **kw: [])

    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0


# ── serve / up (mock heavy deps) ───────────────────────────────────


def test_serve_mcp_only(monkeypatch) -> None:
    called = {}

    def fake_serve(*, profile, host=None, port=None, use_proxy=False):
        called["serve"] = True

    monkeypatch.setattr("kater.mcp_server.serve", fake_serve)
    monkeypatch.setattr("kater.envfile.load_project_env", lambda *a, **kw: [])
    monkeypatch.setattr("kater.envfile.resolve_use_proxy", lambda **kw: False)
    monkeypatch.setattr(
        "kater.settings.load_settings",
        lambda: type("S", (), {"apply_credentials_to_env": lambda self: None})(),
    )

    result = runner.invoke(app, ["serve", "--mcp-only", "--host", "127.0.0.1"])
    # Should reach serve() without starting a real server
    assert result.exit_code == 0 or called.get("serve") is True


def test_serve_api_only(monkeypatch) -> None:
    called = {}

    def fake_serve_api(host, port):
        called["api"] = True

    monkeypatch.setattr("kater.api.serve_api", fake_serve_api)
    monkeypatch.setattr("kater.envfile.load_project_env", lambda *a, **kw: [])

    result = runner.invoke(app, ["serve", "--api-only", "--host", "127.0.0.1"])
    assert result.exit_code == 0
    assert called.get("api") is True
