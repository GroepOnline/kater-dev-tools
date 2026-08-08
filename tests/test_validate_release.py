"""Tests for scripts/validate_release.py — the immutable release-contract gate.

These tests invoke the validator as a subprocess against the real
release-policy.json and package sources, exercising the same code path that
the GitHub Actions release job uses. They do NOT create tags, push, or mutate
the repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_release.py"


def _run(tag: str, extra: str = "--commit HEAD --main-ref HEAD") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), tag, *extra.split()],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


class TestValidateRelease:
    def test_valid_stable_tag_passes(self) -> None:
        result = _run("v1.0.0")
        assert result.returncode == 0, result.stderr
        assert "PASS" in result.stdout

    def test_version_mismatch_fails(self) -> None:
        result = _run("v1.0.1")
        assert result.returncode == 1
        assert "version" in result.stderr.lower() or "ERROR" in result.stderr

    def test_dev_tag_matches_development_channel(self) -> None:
        result = _run("v1.0.0.dev1")
        assert result.returncode == 1
        assert "channel" in result.stdout or "channel" in result.stderr

    def test_invalid_tag_format_rejected(self) -> None:
        result = _run("v1.0")
        assert result.returncode == 1
        assert "no channel" in result.stderr.lower() or "ERROR" in result.stderr

    def test_no_matching_channel_rejected(self) -> None:
        result = _run("release-1.0.0")
        assert result.returncode == 1
        assert "no channel" in result.stderr.lower() or "ERROR" in result.stderr

    def test_ancestry_check_rejects_non_ancestor(self) -> None:
        # Point --main-ref at HEAD~1 so the commit is NOT an ancestor (fails),
        # simulating a rewritten or orphaned tag.
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "v1.0.0",
             "--commit", "HEAD", "--main-ref", "HEAD~1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ancestor" in result.stderr.lower() or "ERROR" in result.stderr
