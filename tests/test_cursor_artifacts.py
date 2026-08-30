from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".cursor/hooks/fetch-cursor-artifacts.sh"
STATE_DIR = ROOT / ".cursor/hooks/.state"
MINIMAL_ENV = {"PATH": "/usr/bin:/bin"}


def _clear_markers(conv: str) -> None:
    for marker in STATE_DIR.glob(f"injected-{conv}-*"):
        marker.unlink()


def _run(payload: dict | None = None, args: list[str] | None = None):
    return subprocess.run(
        [str(SCRIPT), *(args or [])],
        cwd=ROOT,
        input=json.dumps(payload) if payload is not None else "",
        check=True,
        capture_output=True,
        text=True,
        env=MINIMAL_ENV,
    )


def test_fetch_cursor_artifacts_print_markdown() -> None:
    assert SCRIPT.is_file(), f"missing hook script: {SCRIPT}"
    proc = subprocess.run(
        [str(SCRIPT), "--print-markdown"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    out = proc.stdout
    assert "Cursor artifact catalog" in out
    assert "kater-gateway" in out
    assert "pr-gate" in out
    assert "SSOT: `.cursor/` only" in out


def test_print_markdown_lists_expected_kinds_and_paths() -> None:
    proc = subprocess.run(
        [str(SCRIPT), "--print-markdown"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    out = proc.stdout
    # Table header + at least one row per artifact kind present in this repo.
    assert "| Kind | Name | Path |" in out
    assert "| skill | `kater-gateway` | `.cursor/skills/kater-gateway/SKILL.md` |" in out
    assert "| skill | `pr-gate` | `.cursor/skills/pr-gate/SKILL.md` |" in out
    assert "| skill | `kater-poteto-mode` | `.cursor/skills/kater-poteto-mode/SKILL.md` |" in out
    assert "| agent | `pr-gate` | `.cursor/agents/pr-gate.md` |" in out
    assert "| hook | `sessionStart` | `.cursor/hooks.json` |" in out
    assert "Skills: 12 |" in out
    assert "Agents: 4 |" in out
    # kater-project + verify-before-claim + the generated taste rule.
    assert "Rules: 3 |" in out
    assert "Commands: 11 |" in out
    assert "Hook events: 4 |" in out
    assert "| rule | `kater-project` |" in out
    assert "| skill | `ci-fix-loop` |" in out
    assert "| command | `local-verify` |" in out
    assert ".cursor/commands/" in out


def test_print_markdown_writes_cache_files() -> None:
    cache_file = STATE_DIR / "catalog.md"
    hash_file = STATE_DIR / "catalog.sha256"
    proc = subprocess.run(
        [str(SCRIPT), "--print-markdown"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert cache_file.is_file()
    assert hash_file.is_file()
    assert hash_file.read_text().strip()
    # Cached markdown matches what was printed to stdout.
    assert cache_file.read_text().strip() == proc.stdout.strip()


def test_post_tool_use_dedupes_per_conversation() -> None:
    conv = f"test-conv-dedup-{Path(__file__).stem}"
    _clear_markers(conv)
    payload = {"hook_event_name": "postToolUse", "conversation_id": conv}
    try:
        first = _run(payload)
        first_json = json.loads(first.stdout)
        assert first_json.get("additional_context")
        assert "env" in first_json
        assert first_json["env"]["KATER_CURSOR_CATALOG_HASH"]

        second = _run(payload)
        second_json = json.loads(second.stdout)
        assert second_json == {}

        markers = list(STATE_DIR.glob(f"injected-{conv}-*"))
        assert len(markers) == 1
    finally:
        _clear_markers(conv)


def test_concurrent_post_tool_use_injects_exactly_once() -> None:
    """Two hooks racing on the same conversation must not both inject.

    The marker is claimed atomically (``noclobber``), so the invariant holds
    regardless of how the two processes interleave.
    """
    conv = f"test-conv-race-{Path(__file__).stem}"
    _clear_markers(conv)
    payload = json.dumps({"hook_event_name": "postToolUse", "conversation_id": conv})
    try:
        procs = [
            subprocess.Popen(
                [str(SCRIPT)],
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=MINIMAL_ENV,
            )
            for _ in range(2)
        ]
        outs = [proc.communicate(payload)[0] for proc in procs]
        assert all(proc.returncode == 0 for proc in procs)

        injected = [out for out in outs if json.loads(out).get("additional_context")]
        assert len(injected) == 1, outs
        assert len(list(STATE_DIR.glob(f"injected-{conv}-*"))) == 1
    finally:
        _clear_markers(conv)


def test_post_tool_use_force_inject_bypasses_existing_marker() -> None:
    conv = f"test-conv-force-{Path(__file__).stem}"
    _clear_markers(conv)
    payload = {"hook_event_name": "postToolUse", "conversation_id": conv}
    try:
        first = _run(payload)
        assert json.loads(first.stdout).get("additional_context")

        # Without --force-inject, a second call is a no-op (already injected).
        second = _run(payload)
        assert json.loads(second.stdout) == {}

        # With --force-inject, injection happens again despite the marker.
        third = _run(payload, args=["--force-inject"])
        third_json = json.loads(third.stdout)
        assert third_json.get("additional_context")

        # Exactly one marker remains for the conversation (old ones replaced).
        markers = list(STATE_DIR.glob(f"injected-{conv}-*"))
        assert len(markers) == 1
    finally:
        _clear_markers(conv)


def test_session_start_always_injects_and_keeps_single_marker() -> None:
    conv = f"test-conv-session-{Path(__file__).stem}"
    _clear_markers(conv)
    payload = {"hook_event_name": "sessionStart", "conversation_id": conv}
    try:
        first = _run(payload)
        first_json = json.loads(first.stdout)
        assert first_json.get("additional_context")

        # sessionStart injects unconditionally, even if already injected.
        second = _run(payload)
        second_json = json.loads(second.stdout)
        assert second_json.get("additional_context")

        # mark_injected replaces prior markers, so only one remains.
        markers = list(STATE_DIR.glob(f"injected-{conv}-*"))
        assert len(markers) == 1
    finally:
        _clear_markers(conv)


def test_before_submit_prompt_allows_continue_without_context() -> None:
    payload = {"hook_event_name": "beforeSubmitPrompt", "conversation_id": "irrelevant"}
    proc = _run(payload)
    out = json.loads(proc.stdout)
    assert out == {"continue": True}


def test_workspace_open_returns_plugin_paths_key() -> None:
    payload = {"hook_event_name": "workspaceOpen"}
    proc = _run(payload)
    out = json.loads(proc.stdout)
    assert "pluginPaths" in out
    assert isinstance(out["pluginPaths"], list)
    # No .cursor/plugins directory exists in this repo, so it must be empty.
    assert out["pluginPaths"] == []


def test_collect_plugins_excludes_installed_metadata_dir() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("! -name installed") >= 2

    plugins = ROOT / ".cursor" / "plugins"
    snapshot = None
    if plugins.exists():
        snapshot = Path(tempfile.mkdtemp(prefix="kater-plugins-snap-"))
        inner = snapshot / "plugins"
        shutil.copytree(plugins, inner)
        snapshot = inner
    created_root = snapshot is None
    installed = plugins / "installed"
    real = plugins / "chefgroep-skills"
    try:
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "manifest.json").write_text("{}\n", encoding="utf-8")
        real.mkdir(parents=True, exist_ok=True)

        md = subprocess.run(
            [str(SCRIPT), "--print-markdown"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "| plugin | `chefgroep-skills` |" in md
        assert "| plugin | `installed` |" not in md

        opened = json.loads(_run({"hook_event_name": "workspaceOpen"}).stdout)
        names = {Path(path).name for path in opened["pluginPaths"]}
        assert "chefgroep-skills" in names
        assert "installed" not in names
    finally:
        if snapshot is not None:
            shutil.rmtree(plugins, ignore_errors=True)
            shutil.copytree(snapshot, plugins)
            shutil.rmtree(snapshot.parent, ignore_errors=True)
        else:
            shutil.rmtree(real, ignore_errors=True)
            shutil.rmtree(installed, ignore_errors=True)
            if created_root and plugins.is_dir() and not any(plugins.iterdir()):
                plugins.rmdir()


def test_unknown_hook_event_returns_empty_object() -> None:
    payload = {"hook_event_name": "someUnhandledEvent", "conversation_id": "x"}
    proc = _run(payload)
    assert json.loads(proc.stdout) == {}


def test_no_stdin_payload_returns_empty_object() -> None:
    # Piped-but-empty stdin (no hook_event_name, no conversation_id).
    proc = _run(payload=None)
    assert json.loads(proc.stdout) == {}


def _bash_tr_cd_alnum_dot_underscore_dash(raw: str) -> str:
    """Mirror the script's `tr -cd 'A-Za-z0-9._-'` sanitization."""
    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
    )
    return "".join(ch for ch in raw if ch in allowed)


def test_conversation_id_is_sanitized_for_marker_filenames() -> None:
    raw_conv = "weird/../id;rm -rf$(x)"
    sanitized = _bash_tr_cd_alnum_dot_underscore_dash(raw_conv)
    assert sanitized, "sanitization helper should keep at least some characters"
    payload = {"hook_event_name": "postToolUse", "conversation_id": raw_conv}
    _clear_markers(sanitized)
    try:
        proc = _run(payload)
        out = json.loads(proc.stdout)
        assert out.get("additional_context")

        # Exactly one marker was created, named using only the sanitized id —
        # no path separators or shell metacharacters from the raw input.
        markers = list(STATE_DIR.glob(f"injected-{sanitized}-*"))
        assert len(markers) == 1
        marker_name = markers[0].name
        assert "/" not in marker_name
        assert ";" not in marker_name
        assert " " not in marker_name
        assert "$" not in marker_name
        assert "(" not in marker_name
    finally:
        _clear_markers(sanitized)
