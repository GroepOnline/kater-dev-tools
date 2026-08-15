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
_FAKE_TOKEN = "ghs_this_is_not_a_real_token_leak_test"
_FAKE_CRED_URL = f"https://x-access-token:{_FAKE_TOKEN}@127.0.0.1:1/example/chefgroep-skills.git"
_GIT_TRACE_FILE_VARS = (
    "GIT_TRACE",
    "GIT_TRACE2",
    "GIT_TRACE2_EVENT",
    "GIT_TRACE2_PERF",
    "GIT_TRACE_PACKET",
    "GIT_TRACE_PERFORMANCE",
    "GIT_TRACE_SETUP",
    "GIT_TRACE_CURL",
)
_GIT_TRACE_UNSET_VARS = (
    *_GIT_TRACE_FILE_VARS,
    "GIT_TRACE2_BRIEF",
    "GIT_TRACE2_EVENT_BRIEF",
    "GIT_TRACE2_PERF_BRIEF",
    "GIT_TRACE2_CONFIG_PARAMS",
    "GIT_TRACE2_ENV_VARS",
    "GIT_TRACE2_DST_DEBUG",
    "GIT_TRACE_SHALLOW",
    "GIT_TRACE_CURL_NO_DATA",
    "GIT_TRACE_PACK_ACCESS",
    "GIT_TRACE_PACKFILE",
    "GIT_CURL_VERBOSE",
)


_PLUGIN_ROOT = REPO / ".cursor" / "plugins"


def _cleanup_plugin_install() -> None:
    shutil.rmtree(PLUGIN_DEST, ignore_errors=True)
    shutil.rmtree(PLUGIN_INSTALLED, ignore_errors=True)
    if _PLUGIN_ROOT.is_dir() and not any(_PLUGIN_ROOT.iterdir()):
        _PLUGIN_ROOT.rmdir()


@pytest.fixture(autouse=True)
def _preserve_workspace_plugins(tmp_path_factory: pytest.TempPathFactory):
    """Do not delete a developer-installed .cursor/plugins tree."""
    snapshot = None
    if _PLUGIN_ROOT.exists():
        snapshot = tmp_path_factory.mktemp("plugins-snap") / "plugins"
        shutil.copytree(_PLUGIN_ROOT, snapshot, symlinks=True)
    yield
    if snapshot is not None:
        if _PLUGIN_ROOT.exists():
            shutil.rmtree(_PLUGIN_ROOT)
        shutil.copytree(snapshot, _PLUGIN_ROOT, symlinks=True)
    else:
        _cleanup_plugin_install()


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


def _assert_no_credential_text(text: str, secret: str, url: str, source: str) -> None:
    assert secret not in text, f"{source} leaked fake token"
    assert url not in text, f"{source} leaked credential URL"
    assert "x-access-token" not in text, f"{source} leaked token scheme"


def _assert_no_credential(proc: subprocess.CompletedProcess[str], secret: str, url: str) -> None:
    _assert_no_credential_text(f"{proc.stdout}{proc.stderr}", secret, url, "stdio")


def _inject_git_traces(tmp_path: Path) -> tuple[dict[str, str], list[Path]]:
    dest_dir = tmp_path / "git-traces"
    dest_dir.mkdir(parents=True, exist_ok=True)
    extra: dict[str, str] = {
        "GIT_CURL_VERBOSE": "1",
        "GIT_TRACE2_ENV_VARS": "*",
    }
    dests: list[Path] = []
    for name in _GIT_TRACE_FILE_VARS:
        path = dest_dir / f"{name.lower()}.log"
        path.write_text("", encoding="utf-8")
        dests.append(path)
        extra[name] = str(path)
    return extra, dests


def _assert_no_credential_in_traces(dests: list[Path], secret: str, url: str) -> None:
    for path in dests:
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        _assert_no_credential_text(text, secret, url, path.name)


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
    monkeypatch.delenv("CHEFGROEP_SKILLS_REPO", raising=False)
    monkeypatch.setenv("CHEFGROEP_SKILLS_GIT_URL", _FAKE_CRED_URL)
    proc = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    _assert_no_credential(proc, _FAKE_TOKEN, _FAKE_CRED_URL)
    assert "https://" not in f"{proc.stdout}{proc.stderr}"
    text = SCRIPT.read_text(encoding="utf-8")
    assert "git_quiet" in text
    assert "pull --ff-only" not in text
    for line in text.splitlines():
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


def test_upstream_scripts_sync_failure_exits_nonzero(tmp_path: Path) -> None:
    repo = tmp_path / "skills-src"
    _git_repo(
        repo,
        files={"README": "src\n", "scripts/sync.sh": "#!/bin/sh\nexit 7\n"},
        executable=("scripts/sync.sh",),
    )
    try:
        proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(repo),
                "CURSOR_PLUGINS_HOME": str(tmp_path / "plugins-home"),
            }
        )
        assert proc.returncode != 0
        assert "run upstream scripts/sync.sh" in proc.stdout
        assert "WARN: upstream" not in proc.stdout
        assert "done (" not in proc.stdout
        assert not PLUGIN_DEST.exists()
    finally:
        _cleanup_plugin_install()


def test_clone_fetch_failure_does_not_log_credentials(tmp_path: Path) -> None:
    plugins_home = tmp_path / "plugins-home"
    try:
        clone_proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": _FAKE_CRED_URL,
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert clone_proc.returncode != 0
        assert "ERROR: clone failed" in clone_proc.stdout
        assert "done (" not in clone_proc.stdout
        _assert_no_credential(clone_proc, _FAKE_TOKEN, _FAKE_CRED_URL)

        local = tmp_path / "skills-src"
        _git_repo(local, files={"marker": "ok\n"})
        first = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(local),
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert first.returncode == 0, first.stdout + first.stderr
        _cleanup_plugin_install()

        fetch_proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": _FAKE_CRED_URL,
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert fetch_proc.returncode != 0
        assert "ERROR: fetch failed" in fetch_proc.stdout
        assert "done (" not in fetch_proc.stdout
        _assert_no_credential(fetch_proc, _FAKE_TOKEN, _FAKE_CRED_URL)
        assert not PLUGIN_DEST.exists()
    finally:
        _cleanup_plugin_install()


def test_git_trace_env_does_not_leak_credentials(tmp_path: Path) -> None:
    plugins_home = tmp_path / "plugins-home"
    script = SCRIPT.read_text(encoding="utf-8")
    for name in _GIT_TRACE_UNSET_VARS:
        assert name in script
    assert 'git_quiet -C "${CACHE_ROOT}" checkout' in script
    for line in script.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("git ") and "checkout" in stripped:
            raise AssertionError(f"raw git checkout bypasses git_quiet: {stripped}")

    clone_env, clone_dests = _inject_git_traces(tmp_path / "clone")
    try:
        clone_proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": _FAKE_CRED_URL,
                "CURSOR_PLUGINS_HOME": str(plugins_home),
                **clone_env,
            }
        )
        assert clone_proc.returncode != 0
        assert "ERROR: clone failed" in clone_proc.stdout
        assert "done (" not in clone_proc.stdout
        _assert_no_credential(clone_proc, _FAKE_TOKEN, _FAKE_CRED_URL)
        _assert_no_credential_in_traces(clone_dests, _FAKE_TOKEN, _FAKE_CRED_URL)

        local = tmp_path / "skills-src"
        _git_repo(local, files={"marker": "ok\n"})
        seed_env, seed_dests = _inject_git_traces(tmp_path / "seed")
        seed = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(local),
                "CURSOR_PLUGINS_HOME": str(plugins_home),
                **seed_env,
            }
        )
        assert seed.returncode == 0, seed.stdout + seed.stderr
        _assert_no_credential(seed, _FAKE_TOKEN, _FAKE_CRED_URL)
        _assert_no_credential_in_traces(seed_dests, _FAKE_TOKEN, _FAKE_CRED_URL)
        _cleanup_plugin_install()

        fetch_env, fetch_dests = _inject_git_traces(tmp_path / "fetch")
        fetch_proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": _FAKE_CRED_URL,
                "CURSOR_PLUGINS_HOME": str(plugins_home),
                **fetch_env,
            }
        )
        assert fetch_proc.returncode != 0
        assert "ERROR: fetch failed" in fetch_proc.stdout
        assert "done (" not in fetch_proc.stdout
        _assert_no_credential(fetch_proc, _FAKE_TOKEN, _FAKE_CRED_URL)
        _assert_no_credential_in_traces(fetch_dests, _FAKE_TOKEN, _FAKE_CRED_URL)
        assert not PLUGIN_DEST.exists()

        update_env, update_dests = _inject_git_traces(tmp_path / "update")
        update = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(local),
                "CURSOR_PLUGINS_HOME": str(plugins_home),
                **update_env,
            }
        )
        assert update.returncode == 0, update.stdout + update.stderr
        assert "update " in update.stdout
        _assert_no_credential(update, _FAKE_TOKEN, _FAKE_CRED_URL)
        _assert_no_credential_in_traces(update_dests, _FAKE_TOKEN, _FAKE_CRED_URL)
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
    raw = (REPO / ".cursor" / "environment.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert "repositoryDependencies" not in payload
    assert "sync-chefgroep-skills.sh" in payload["install"]
    install = payload["install"]
    assert "CHEFGROEP_SKILLS_REPO=github.com/" not in install
    # Concatenate so this test file is not itself an org-handle leak.
    assert "Groep" + "Online" not in raw
    assert "Online" + "ChefGroep" not in raw
    uv_sync_at = install.find("uv sync --dev")
    index_at = install.find("uv run python scripts/generate_cursor_index.py")
    assert uv_sync_at >= 0
    assert index_at > uv_sync_at
    assert "python3 scripts/generate_cursor_index.py" not in install
    assert "posthog" not in install.lower()
    assert "harness" not in install.lower()


def test_cache_origin_never_stores_credentials(tmp_path: Path) -> None:
    local = tmp_path / "skills-src"
    _git_repo(local, files={"marker": "ok\n"})
    plugins_home = tmp_path / "plugins-home"
    cache = plugins_home / "sources" / "chefgroep-skills"
    cred_url = f"https://x-access-token:{_FAKE_TOKEN}@127.0.0.1:1/example/chefgroep-skills.git"
    try:
        first = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(local),
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert first.returncode == 0, first.stdout + first.stderr
        config = (cache / ".git" / "config").read_text(encoding="utf-8")
        _assert_no_credential_text(config, _FAKE_TOKEN, cred_url, "git-config-after-clone")

        failed = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": cred_url,
                "CURSOR_PLUGINS_HOME": str(plugins_home),
            }
        )
        assert failed.returncode != 0
        config = (cache / ".git" / "config").read_text(encoding="utf-8")
        _assert_no_credential_text(config, _FAKE_TOKEN, cred_url, "git-config-after-failed-fetch")
        origin = subprocess.run(
            ["git", "-C", str(cache), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert _FAKE_TOKEN not in origin
        assert "x-access-token" not in origin
    finally:
        _cleanup_plugin_install()


def test_upstream_sync_cannot_read_credential_env(tmp_path: Path) -> None:
    repo = tmp_path / "skills-src"
    dump = tmp_path / "env-dump"
    _git_repo(
        repo,
        files={
            "README": "src\n",
            "sync.sh": (
                "#!/bin/sh\n"
                f"umask 077; env > '{dump}'\n"
                "exit 0\n"
            ),
        },
        executable=("sync.sh",),
    )
    try:
        proc = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": f"https://x-access-token:{_FAKE_TOKEN}@127.0.0.1:1/example/chefgroep-skills.git",
                "CURSOR_PLUGINS_HOME": str(tmp_path / "plugins-home-fail"),
            }
        )
        assert proc.returncode != 0
        assert not dump.exists()

        ok = _run_sync(
            {
                "CHEFGROEP_SKILLS_GIT_URL": str(repo),
                "CURSOR_PLUGINS_HOME": str(tmp_path / "plugins-home-ok"),
                "GIT_TRACE": "1",
                "GIT_CURL_VERBOSE": "1",
            }
        )
        assert ok.returncode == 0, ok.stdout + ok.stderr
        text = dump.read_text(encoding="utf-8")
        assert "CHEFGROEP_SKILLS_GIT_URL=" not in text
        assert "GIT_TRACE=" not in text
        assert "GIT_CURL_VERBOSE=" not in text
        assert _FAKE_TOKEN not in text
    finally:
        _cleanup_plugin_install()
