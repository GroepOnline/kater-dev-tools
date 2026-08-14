from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "sync-chefgroep-skills.sh"


def test_sync_script_is_executable() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_sync_check_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHEFGROEP_SKILLS_REPO", raising=False)
    monkeypatch.delenv("CHEFGROEP_SKILLS_GIT_URL", raising=False)
    proc = subprocess.run(
        [str(SCRIPT), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "CHEFGROEP_SKILLS_REPO" in proc.stdout or "CHEFGROEP_SKILLS_REPO" in proc.stderr


def test_sync_check_ok_with_repo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEFGROEP_SKILLS_REPO", "github.com/example/chefgroep-skills")
    proc = subprocess.run(
        [str(SCRIPT), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0


def test_sync_dry_run_mentions_dest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEFGROEP_SKILLS_REPO", "github.com/example/chefgroep-skills")
    proc = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "chefgroep-skills" in proc.stdout


def test_environment_json_wires_skills_sync() -> None:
    payload = json.loads((REPO / ".cursor" / "environment.json").read_text(encoding="utf-8"))
    assert "repositoryDependencies" in payload
    assert any(dep.endswith("/chefgroep-skills") for dep in payload["repositoryDependencies"])
    assert "sync-chefgroep-skills.sh" in payload["install"]
    assert "CHEFGROEP_SKILLS_REPO=" in payload["install"]
    assert "posthog" not in payload["install"].lower()
    assert "harness" not in payload["install"].lower()
