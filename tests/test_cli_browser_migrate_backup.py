from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from kater.cli import app

runner = CliRunner()


def _seed_kater(root: Path) -> None:
    """
    Create the minimal `.kater` project state required by CLI tests.

    Parameters:
        root (Path): Project directory in which to create the `.kater` directory.
    """
    kater = root / ".kater"
    kater.mkdir(parents=True, exist_ok=True)
    (kater / "config.json").write_text(
        json.dumps({"version": 1, "default_profile": "core"}), encoding="utf-8"
    )
    (kater / "settings.json").write_text("{}", encoding="utf-8")


def test_migrate_status_json(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["migrate", "status", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "current_version" in payload
    assert "latest_version" in payload
    assert "pending" in payload
    assert "database" in payload


def test_backup_create_and_inspect(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_kater(tmp_path)
    out = tmp_path / "bundle.tar.gz"

    create = runner.invoke(app, ["backup", "create", "--output", str(out), "--json"])

    assert create.exit_code == 0, create.output
    created = json.loads(create.output)
    assert Path(created["path"]) == out
    assert created["bytes"] > 0
    assert "config.json" in created["files"]

    inspect = runner.invoke(app, ["backup", "inspect", str(out), "--json"])

    assert inspect.exit_code == 0, inspect.output
    report = json.loads(inspect.output)
    assert report["ok"] is True
    assert report["path"] == str(out)
    assert any(entry["name"] == "config.json" for entry in report["files"])


def test_browser_providers_json() -> None:
    result = runner.invoke(app, ["browser", "providers", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "providers" in payload
    assert len(payload["providers"]) >= 1
    kinds = {p.get("kind") for p in payload["providers"]}
    assert "local" in kinds


def test_browser_sessions_empty_json() -> None:
    result = runner.invoke(app, ["browser", "sessions", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["sessions"] == []
    assert "stats" in payload
