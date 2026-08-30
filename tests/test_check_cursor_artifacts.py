"""Run scripts/check_cursor_artifacts.sh — catalog cache, INDEX check, org guard."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_cursor_artifacts.sh"


def test_check_cursor_artifacts_script_exits_ok() -> None:
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "check_cursor_artifacts: ok" in proc.stdout


def test_check_cursor_artifacts_rejects_missing_source_and_mirror(tmp_path: Path) -> None:
    env = {
        **__import__("os").environ,
        "PR_REVIEW_LOG_SOURCE_SKILL": str(tmp_path / "missing-source.md"),
        "PR_REVIEW_LOG_MIRROR_SKILL": str(tmp_path / "missing-mirror.md"),
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode != 0
    assert "pr-review-log mirror drift" in proc.stderr
