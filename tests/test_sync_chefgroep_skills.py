from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "sync-chefgroep-skills.sh"
PLUGIN_DEST = REPO / ".cursor" / "plugins" / "chefgroep-skills"
PLUGIN_INSTALLED = REPO / ".cursor" / "plugins" / "installed"


def _cleanup_plugin_install() -> None:
    shutil.rmtree(PLUGIN_DEST, ignore_errors=True)
    shutil.rmtree(PLUGIN_INSTALLED, ignore_errors=True)
    plugins = REPO / ".cursor" / "plugins"
    if plugins.is_dir() and not any(plugins.iterdir()):
        plugins.rmdir()


def _git_repo(path: Path, files: dict[str, str], executable: tuple[str, ...] = ()) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "sync-test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "sync-test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    for rel, content in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if rel in executable:
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _run_sync(extra_env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("CHEFGROEP_SKILLS_REPO", None)
    env.pop("CHEFGROEP_SKILLS_GIT_URL", None)
    env.update(extra_env)
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


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


def test_sync_dry_run_does_not_log_git_url(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "ghs_this_is_not_a_real_token_leak_test"
    url = f"https://x-access-token:{secret}@github.com/example/chefgroep-skills.git"
    monkeypatch.delenv("CHEFGROEP_SKILLS_REPO", raising=False)
    monkeypatch.setenv("CHEFGROEP_SKILLS_GIT_URL", url)
    proc = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = f"{proc.stdout}{proc.stderr}"
    assert proc.returncode == 0
    assert secret not in combined
    assert url not in combined
    assert "https://" not in combined
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("log "):
            assert "${GIT_URL}" not in line
            assert "$GIT_URL" not in line


def test_sync_script_does_not_mirror_agents_skills() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "AGENTS_SKILLS" not in text
    assert "${HOME}/.agents/skills" not in text
    assert "~/.agents/skills" not in text


def test_upstream_sync_failure_exits_nonzero(tmp_path: Path) -> None:
    repo = tmp_path / "skills-src"
    _git_repo(
        repo,
        files={"README": "src\n", "sync.sh": "#!/bin/sh\nexit 7\n"},
        executable=("sync.sh",),
    )
    try:
        proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(repo),
                "CURSOR_PLUGINS_HOME": str(tmp_path / "plugins-home"),
            }
        )
        assert proc.returncode != 0
        assert "WARN: upstream sync.sh" not in proc.stdout
        assert "done (" not in proc.stdout
        assert not PLUGIN_DEST.exists()
    finally:
        _cleanup_plugin_install()


def test_cache_origin_is_retargeted_before_fetch(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _git_repo(repo_a, files={"marker": "a\n"})
    _git_repo(repo_b, files={"marker": "b\n"})
    plugins_home = tmp_path / "plugins-home"
    cache = plugins_home / "sources" / "chefgroep-skills"
    try:
        first = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(repo_a),
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert first.returncode == 0, first.stdout + first.stderr
        assert (cache / "marker").read_text(encoding="utf-8") == "a\n"

        second = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(repo_b),
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert second.returncode == 0, second.stdout + second.stderr
        origin = subprocess.run(
            ["git", "-C", str(cache), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert origin == str(repo_b)
        assert (cache / "marker").read_text(encoding="utf-8") == "b\n"
    finally:
        _cleanup_plugin_install()


def test_environment_json_wires_skills_sync() -> None:
    payload = json.loads((REPO / ".cursor" / "environment.json").read_text(encoding="utf-8"))
    assert "repositoryDependencies" in payload
    assert any(dep.endswith("/chefgroep-skills") for dep in payload["repositoryDependencies"])
    assert "sync-chefgroep-skills.sh" in payload["install"]
    assert "CHEFGROEP_SKILLS_REPO=" in payload["install"]
    assert "posthog" not in payload["install"].lower()
    assert "harness" not in payload["install"].lower()
