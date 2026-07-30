"""Tests for the Cursor project config files added by this PR.

Covers `.cursor/environment.json`, `.cursor/hooks.json`,
`.cursor/hooks/.gitignore`, `.vscode/settings.json`, `.pre-commit-config.yaml`
(the new no-org-leak hook), and the reworked root `.gitignore`.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# .cursor/environment.json
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def environment_json() -> dict:
    path = ROOT / ".cursor/environment.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_environment_json_is_valid_json() -> None:
    path = ROOT / ".cursor/environment.json"
    assert path.is_file()
    json.loads(path.read_text(encoding="utf-8"))


def test_environment_json_install_bootstraps_hooks_and_deps(environment_json) -> None:
    install = environment_json["install"]
    assert "fetch-cursor-artifacts.sh" in install
    assert "chmod +x" in install
    assert "uv sync --dev" in install


def test_environment_json_terminal_serves_core_profile_without_proxy(environment_json) -> None:
    terminals = environment_json["terminals"]
    assert len(terminals) == 1
    terminal = terminals[0]
    assert terminal["name"] == "kater-gateway"
    assert "kater serve" in terminal["command"]
    assert "--profile core" in terminal["command"]
    assert "--no-proxy" in terminal["command"]
    assert "127.0.0.1" in terminal["command"]


def test_environment_json_declares_expected_ports(environment_json) -> None:
    ports = {p["name"]: p["port"] for p in environment_json["ports"]}
    assert ports == {"mcp-sse": 9090, "api-dashboard": 9091, "websocket": 9092}


# --------------------------------------------------------------------------
# .cursor/hooks.json
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hooks_json() -> dict:
    path = ROOT / ".cursor/hooks.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_hooks_json_is_valid_json() -> None:
    path = ROOT / ".cursor/hooks.json"
    assert path.is_file()
    json.loads(path.read_text(encoding="utf-8"))


def test_hooks_json_declares_expected_events(hooks_json) -> None:
    assert hooks_json["version"] == 1
    assert set(hooks_json["hooks"].keys()) == {
        "sessionStart",
        "beforeSubmitPrompt",
        "postToolUse",
        "workspaceOpen",
    }


def test_hooks_json_every_event_runs_the_fetch_script_with_positive_timeout(
    hooks_json,
) -> None:
    for event, entries in hooks_json["hooks"].items():
        assert entries, f"{event} has no hook entries"
        for entry in entries:
            assert entry["command"] == ".cursor/hooks/fetch-cursor-artifacts.sh"
            assert isinstance(entry["timeout"], int)
            assert entry["timeout"] > 0


def test_hooks_json_referenced_script_exists_and_is_executable(hooks_json) -> None:
    commands = {
        entry["command"]
        for entries in hooks_json["hooks"].values()
        for entry in entries
    }
    assert len(commands) == 1
    script_path = ROOT / next(iter(commands))
    assert script_path.is_file()
    assert os.access(script_path, os.X_OK), "hook script must be executable"


# --------------------------------------------------------------------------
# .cursor/hooks/.gitignore
# --------------------------------------------------------------------------


def test_cursor_hooks_gitignore_ignores_state_dir() -> None:
    path = ROOT / ".cursor/hooks/.gitignore"
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip() == ".state/"


def test_git_check_ignore_hides_hook_state_but_not_skills() -> None:
    # .cursor/hooks/.state/* must be ignored...
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".cursor/hooks/.state/catalog.md"],
        cwd=ROOT,
        capture_output=True,
    )
    assert ignored.returncode == 0

    # ...but committed SSOT under .cursor/skills and .cursor/agents must not be.
    for tracked in (
        ".cursor/skills/pr-gate/SKILL.md",
        ".cursor/agents/pr-gate.md",
        ".cursor/hooks.json",
        ".cursor/hooks/fetch-cursor-artifacts.sh",
    ):
        not_ignored = subprocess.run(
            ["git", "check-ignore", "-q", tracked],
            cwd=ROOT,
            capture_output=True,
        )
        assert not_ignored.returncode == 1, f"{tracked} should not be gitignored"


# --------------------------------------------------------------------------
# .gitignore (root)
# --------------------------------------------------------------------------


def test_root_gitignore_targets_cursor_runtime_outputs_only() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (
        ".cursor/hooks/.state/",
        ".cursor/mcp.json",
        ".cursor/mcp.kater.json",
        ".cursor/.env.runtime",
        ".agents/",
        ".claude/",
    ):
        assert entry in text
    # The old blanket `.cursor/` ignore must be gone — SSOT is tracked now.
    lines = [line.strip() for line in text.splitlines()]
    assert ".cursor/" not in lines


# --------------------------------------------------------------------------
# .vscode/settings.json
# --------------------------------------------------------------------------


def test_vscode_settings_json_is_valid_json() -> None:
    path = ROOT / ".vscode/settings.json"
    assert path.is_file()
    settings = json.loads(path.read_text(encoding="utf-8"))
    assert settings["files.associations"]["SKILL.md"] == "markdown"
    assert settings["files.associations"]["*.mdc"] == "markdown"


def test_vscode_settings_json_excludes_hook_state_dir() -> None:
    path = ROOT / ".vscode/settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    assert settings["files.exclude"]["**/.cursor/hooks/.state"] is True
    assert settings["search.exclude"]["**/.cursor/hooks/.state"] is True
    assert settings["files.watcherExclude"]["**/.cursor/hooks/.state/**"] is True


# --------------------------------------------------------------------------
# .pre-commit-config.yaml
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pre_commit_config() -> dict:
    path = ROOT / ".pre-commit-config.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_pre_commit_config_is_valid_yaml(pre_commit_config) -> None:
    assert "repos" in pre_commit_config


def test_pre_commit_config_has_local_no_org_leak_hook(pre_commit_config) -> None:
    local_repos = [
        repo for repo in pre_commit_config["repos"] if repo.get("repo") == "local"
    ]
    assert local_repos, "expected a local repo block for the no-org-leak hook"
    hooks = [hook for repo in local_repos for hook in repo["hooks"]]
    matches = [hook for hook in hooks if hook["id"] == "no-org-leak"]
    assert len(matches) == 1
    hook = matches[0]
    assert hook["entry"] == "uv run python scripts/no_org_leak.py"
    assert hook["language"] == "system"
    assert hook["pass_filenames"] is False
    assert hook["stages"] == ["pre-commit"]


def test_pre_commit_config_no_org_leak_referenced_script_exists() -> None:
    assert (ROOT / "scripts/no_org_leak.py").is_file()


def test_pre_commit_config_has_cursor_index_hook(pre_commit_config) -> None:
    local_repos = [
        repo for repo in pre_commit_config["repos"] if repo.get("repo") == "local"
    ]
    hooks = [hook for repo in local_repos for hook in repo["hooks"]]
    matches = [hook for hook in hooks if hook["id"] == "cursor-index"]
    assert len(matches) == 1
    hook = matches[0]
    assert hook["entry"] == "bash scripts/check_cursor_artifacts.sh"
    assert hook["language"] == "system"
    assert hook["pass_filenames"] is False
    assert hook["stages"] == ["pre-commit"]


def test_pre_commit_config_cursor_index_referenced_script_exists() -> None:
    assert (ROOT / "scripts/check_cursor_artifacts.sh").is_file()