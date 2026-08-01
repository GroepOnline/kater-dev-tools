from __future__ import annotations

import json
from pathlib import Path

from kater.init import (
    _render_env_file,
    _render_kater_config,
    _write_gitignore,
    init_project,
    load_project_config,
)


def test_render_kater_config_includes_servers() -> None:
    config = _render_kater_config("core")
    assert config["version"] == 1
    assert config["default_profile"] == "core"
    assert "servers" in config
    assert "profiles" in config


def test_render_env_file_includes_profile_and_placeholder() -> None:
    result = _render_env_file("core")
    assert "KATER_PROFILE=core" in result
    assert "# Kater environment" in result


def test_write_gitignore_creates_file(tmp_path: Path) -> None:
    kater_dir = tmp_path / ".kater"
    kater_dir.mkdir()
    _write_gitignore(kater_dir)
    gitignore = kater_dir / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert ".env" in content


def test_load_project_config_returns_none_when_no_dir() -> None:
    result = load_project_config(Path("/nonexistent/path/abc123"))
    assert result is None


def test_load_project_config_reads_config(tmp_path: Path) -> None:
    kater_dir = tmp_path / ".kater"
    kater_dir.mkdir()
    config = {"version": 1, "default_profile": "test"}
    (kater_dir / "config.json").write_text(json.dumps(config))
    result = load_project_config(tmp_path)
    assert result is not None
    assert result["default_profile"] == "test"


def test_init_project_creates_kater_dir(tmp_path: Path) -> None:
    result = init_project(tmp_path, profile="core")
    assert "created" in result
    kater_dir = tmp_path / ".kater"
    assert kater_dir.exists()
    assert (kater_dir / "config.json").exists()
    assert (kater_dir / ".env").exists()
    assert (kater_dir / ".gitignore").exists()


def test_init_project_skips_when_exists(tmp_path: Path) -> None:
    kater_dir = tmp_path / ".kater"
    kater_dir.mkdir()
    result = init_project(tmp_path, profile="core")
    assert "skipped" in result
    assert len(result["skipped"]) > 0


def test_init_project_force_overwrites(tmp_path: Path) -> None:
    kater_dir = tmp_path / ".kater"
    kater_dir.mkdir()
    (kater_dir / "config.json").write_text("{}")
    result = init_project(tmp_path, profile="ops", force=True)
    assert "created" in result
    config = json.loads((kater_dir / "config.json").read_text())
    assert config["default_profile"] == "ops"
