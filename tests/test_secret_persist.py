"""Deny-default persist policy for manual catalog credentials.

No live provider calls. Placeholder values only; never assert raw secrets
beyond the fixture names used as input.
"""

from __future__ import annotations

import json
from pathlib import Path

from kater.settings import KaterSettings, invalidate_settings_cache, settings_path
from tests._rest import call

PLACEHOLDER = "kater-test-manual-token"


def test_secret_sink_local_requires_explicit_opt_in(monkeypatch) -> None:
    from kater.secret_persist import connect_secret_decision

    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", raising=False)
    monkeypatch.delenv("KATER_CONNECT_SECRET_SINK", raising=False)
    invalidate_settings_cache()
    denied = connect_secret_decision(KaterSettings())
    assert denied.allowed is False
    assert denied.reason == "local_settings_opt_in_required"
    assert denied.persist_local_settings is False

    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    allowed = connect_secret_decision(KaterSettings())
    assert allowed.allowed is True
    assert allowed.sink == "local-settings"
    assert allowed.persist_local_settings is True


def test_secret_sink_public_deny_default_ignores_local_opt_in(monkeypatch) -> None:
    from kater.secret_persist import connect_secret_decision

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    monkeypatch.delenv("KATER_CONNECT_SECRET_SINK", raising=False)
    invalidate_settings_cache()
    denied = connect_secret_decision(KaterSettings())
    assert denied.allowed is False
    assert denied.reason == "secret_sink_required"
    assert denied.persist_local_settings is False


def test_secret_sink_chefvault_is_reference_only(monkeypatch) -> None:
    from kater.secret_persist import connect_secret_decision

    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_CONNECT_SECRET_SINK", "chefvault")
    invalidate_settings_cache()
    denied = connect_secret_decision(KaterSettings())
    assert denied.allowed is False
    assert denied.reason == "chefvault_persist_unavailable"
    assert "access_token" not in denied.as_error()["message"]


def test_public_non_admin_cannot_post_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    invalidate_settings_cache()

    creds = call(
        "POST",
        "/api/mcp/servers/github/credentials",
        body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": PLACEHOLDER}},
        headers={"authorization": "Bearer tool-secret"},
    )
    assert creds.status == 403
    assert creds.payload is not None
    assert creds.payload["error"] == "admin credential required for catalog mutations"
    assert PLACEHOLDER not in json.dumps(creds.payload)
    assert not settings_path().exists()


def test_public_admin_cannot_persist_raw_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    monkeypatch.delenv("KATER_CONNECT_SECRET_SINK", raising=False)
    invalidate_settings_cache()

    creds = call(
        "POST",
        "/api/mcp/servers/github/credentials",
        body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": PLACEHOLDER}},
        headers={"authorization": "Bearer admin-secret"},
    )
    assert creds.status == 403
    assert creds.payload is not None
    assert creds.payload["error"] == "secret_sink_required"
    assert PLACEHOLDER not in json.dumps(creds.payload)
    path = settings_path()
    if path.exists():
        assert PLACEHOLDER not in path.read_text(encoding="utf-8")


def test_local_opt_in_persists_only_after_sink_allows(monkeypatch, tmp_path) -> None:
    import os

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    monkeypatch.delenv("KATER_CONNECT_SECRET_SINK", raising=False)
    monkeypatch.delenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", raising=False)
    invalidate_settings_cache()

    denied = call(
        "POST",
        "/api/mcp/servers/github/credentials",
        body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": PLACEHOLDER}},
    )
    assert denied.status == 403
    assert denied.payload is not None
    assert denied.payload["error"] == "local_settings_opt_in_required"
    assert not settings_path().exists()

    monkeypatch.setenv("KATER_CONNECT_ALLOW_LOCAL_SETTINGS", "1")
    invalidate_settings_cache()
    try:
        ok = call(
            "POST",
            "/api/mcp/servers/github/credentials",
            body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": PLACEHOLDER}},
        )
        assert ok.status == 200
        assert ok.payload is not None
        assert ok.payload["applied"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]
        assert PLACEHOLDER not in json.dumps(ok.payload)
        stored = json.loads(Path(settings_path()).read_text(encoding="utf-8"))
        github_env = stored["server_overrides"]["github"]["env"]
        assert github_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == PLACEHOLDER
    finally:
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)
