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
