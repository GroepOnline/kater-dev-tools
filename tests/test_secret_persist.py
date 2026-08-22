"""Local-settings persist policy for manual catalog credentials.

No live provider calls. Placeholder values only; never assert raw secrets
beyond the fixture names used as input.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from kater.settings import invalidate_settings_cache, settings_path
from tests._rest import call

PLACEHOLDER = "kater-test-manual-token"


def test_decision_always_allows_local_settings() -> None:
    from kater.secret_persist import connect_secret_decision

    decision = connect_secret_decision()
    assert decision.allowed is True
    assert decision.sink == "local-settings"
    assert decision.persist_local_settings is True


def test_public_admin_can_persist_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    invalidate_settings_cache()

    creds = call(
        "POST",
        "/api/mcp/servers/github/credentials",
        body={"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": PLACEHOLDER}},
        headers={"authorization": "Bearer admin-secret"},
    )
    assert creds.status == 200
    assert creds.payload is not None
    assert creds.payload["applied"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]
    # Values are never echoed back over the API.
    assert PLACEHOLDER not in json.dumps(creds.payload)
    path = settings_path()
    stored = json.loads(Path(path).read_text(encoding="utf-8"))
    github_env = stored["server_overrides"]["github"]["env"]
    assert github_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == PLACEHOLDER
    # On-disk file stays 0600 (dir 0700), even on public deployments.
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_local_save_persists_and_masks_values(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    monkeypatch.delenv("KATER_ADMIN_KEY", raising=False)
    invalidate_settings_cache()

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
    try:
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)
    finally:
        pass
