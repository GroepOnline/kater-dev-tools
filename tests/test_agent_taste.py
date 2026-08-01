"""Smoke tests for agent-taste generator, drift check, and eval gate."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
GENERATE = ROOT / ".agents/scripts/generate-taste.py"
EVAL = ROOT / ".agents/scripts/eval-score.py"
TASTE_SIGNAL = ROOT / ".agents/scripts/taste-signal.py"


def _run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_generate_taste_check_passes_on_repo() -> None:
    r = _run(str(GENERATE), "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_generate_taste_check_fails_on_body_drift(tmp_path: Path) -> None:
    import shutil

    target = tmp_path / "repo"
    for rel in (
        ".agents/registry",
        ".agents/scripts",
        ".commandcode/taste",
        ".cursor/rules",
    ):
        src = ROOT / rel
        dst = target / rel
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    shutil.copy2(ROOT / "CLAUDE.md", target / "CLAUDE.md")
    claude = target / "CLAUDE.md"
    claude.write_text(
        claude.read_text(encoding="utf-8").replace("Nederlands", "Klingon", 1),
        encoding="utf-8",
    )
    r = _run(str(GENERATE), "--check", "--target", str(target))
    assert r.returncode == 1
    assert "DRIFT" in r.stdout


def _seed_target(tmp_path: Path, claude_md: str) -> Path:
    import shutil

    target = tmp_path / "repo"
    for rel in (".agents/registry", ".agents/scripts"):
        shutil.copytree(ROOT / rel, target / rel)
    (target / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
    return target


def test_generate_taste_check_fails_on_missing_end_marker(tmp_path: Path) -> None:
    target = _seed_target(tmp_path, "<!-- TASTE:START -->\nstale\n")
    r = _run(str(GENERATE), "--check", "--target", str(target))
    assert r.returncode == 1
    assert "expected exactly one" in r.stderr


def test_generate_taste_fails_on_reversed_markers(tmp_path: Path) -> None:
    target = _seed_target(
        tmp_path, "<!-- TASTE:END -->\n<!-- TASTE:START -->\n"
    )
    r = _run(str(GENERATE), "--check", "--target", str(target))
    assert r.returncode == 1
    assert "occurs before" in r.stderr


def test_generate_taste_fails_on_stray_end_marker(tmp_path: Path) -> None:
    # A stray end marker above an otherwise valid pair must not be accepted:
    # substituting only the pair would leave the stray delimiter behind.
    target = _seed_target(
        tmp_path,
        "<!-- TASTE:END -->\n\n"
        "<!-- TASTE:START -->\nstale\n<!-- TASTE:END -->\n",
    )
    r = _run(str(GENERATE), "--check", "--target", str(target))
    assert r.returncode == 1
    assert "expected exactly one" in r.stderr


def test_generate_taste_fails_on_duplicate_marker_pairs(tmp_path: Path) -> None:
    target = _seed_target(
        tmp_path,
        "<!-- TASTE:START -->\nstale\n<!-- TASTE:END -->\n\n"
        "<!-- TASTE:START -->\nstale\n<!-- TASTE:END -->\n",
    )
    r = _run(str(GENERATE), "--check", "--target", str(target))
    assert r.returncode == 1
    assert "expected exactly one" in r.stderr


def test_eval_score_gate_passes() -> None:
    r = _run(str(EVAL), "--gate")
    assert r.returncode == 0, r.stdout + r.stderr
    card = json.loads(r.stdout)
    assert card["pass"] is True
    assert card["metrics"]["taste_drift"] == 0


def test_days_since_refresh_ignores_scorecard_mtime() -> None:
    spec = importlib.util.spec_from_file_location(
        "eval_score_mod", EVAL
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    scorecard = mod.SCORECARD
    old = scorecard.read_text(encoding="utf-8")
    try:
        scorecard.write_text("{}", encoding="utf-8")
        assert mod.days_since_refresh([]) is None
    finally:
        scorecard.write_text(old, encoding="utf-8")


def _load_taste_signal():
    sys.path.insert(0, str(TASTE_SIGNAL.parent))
    spec = importlib.util.spec_from_file_location("taste_signal_mod", TASTE_SIGNAL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_taste_signal_score_hint_range(tmp_path: Path, monkeypatch) -> None:
    mod = _load_taste_signal()
    signals = tmp_path / "signals.yaml"
    signals.write_text("version: 1\nentries: []\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "SIGNALS", signals)

    def _args(hint):
        return SimpleNamespace(
            signal="range-check",
            plane="agent-taste",
            kind="observation",
            source="human",
            status="open",
            ref=[],
            score_hint=hint,
        )

    for bad in (float("nan"), float("inf"), float("-inf"), 2.0, -0.5):
        with pytest.raises(SystemExit) as exc:
            mod.cmd_add(_args(bad))
        assert exc.value.code == "--score-hint must be between 0 and 1"

    for good in (0.0, 0.5, 1.0, None):
        assert mod.cmd_add(_args(good)) == 0
