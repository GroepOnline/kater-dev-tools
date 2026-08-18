"""Tests for scripts/validate_release.py — the immutable release-contract gate.

These tests invoke the validator as a subprocess against the real
release-policy.json and package sources, exercising the same code path that
the GitHub Actions release job uses. They do NOT create tags, push, or mutate
the repository.

Tag strings are derived from the live package version so a bump PR does not
have to rewrite every assertion.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_release.py"
PACKAGE_INIT = ROOT / "src" / "kater" / "__init__.py"


def _package_versions() -> tuple[str, str]:
    with open(ROOT / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)["project"]["version"]
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', PACKAGE_INIT.read_text())
    assert match, "__version__ missing from src/kater/__init__.py"
    return pyproject, match.group(1)


def _current_version() -> str:
    pyproject, init = _package_versions()
    assert pyproject == init, f"version sources diverge: pyproject={pyproject} init={init}"
    return pyproject


def _run(tag: str, extra: str = "--commit HEAD --main-ref HEAD") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), tag, *extra.split()],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


class TestValidateRelease:
    def test_version_sources_match(self) -> None:
        pyproject, init = _package_versions()
        assert pyproject == init

    def test_valid_stable_tag_passes(self) -> None:
        result = _run(f"v{_current_version()}")
        assert result.returncode == 0, result.stderr
        assert "PASS" in result.stdout

    def test_version_mismatch_fails(self) -> None:
        result = _run("v0.0.0")
        assert result.returncode == 1
        assert "version" in result.stderr.lower() or "ERROR" in result.stderr

    def test_dev_tag_matches_development_channel(self) -> None:
        result = _run(f"v{_current_version()}.dev1")
        assert result.returncode == 1
        assert "channel" in result.stdout or "channel" in result.stderr or "ERROR" in result.stderr

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
            [sys.executable, str(VALIDATOR), f"v{_current_version()}",
             "--commit", "HEAD", "--main-ref", "HEAD~1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ancestor" in result.stderr.lower() or "ERROR" in result.stderr
