#!/usr/bin/env python3
"""Validate a Kater release candidate against release-policy.json.

Checks, in order:
  1. The tag matches a channel in release-policy.json (stable or development)
     and its version matches the channel's version pattern.
  2. The version embedded in the tag equals the version declared in
     pyproject.toml and src/kater/__init__.py.
  3. Tag ancestry is immutable: the tag (or --commit) must point at a commit
     that is an ancestor of the main ref. This rejects rewritten/moved tags
     and tags on orphaned or non-mainline commits.
  4. If dist/ artifacts exist, every artifact filename carries the exact
     resolved version (artifact version == tag version).

Exit code 0 on success, 1 on the first violation. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = json.loads((ROOT / "release-policy.json").read_text())
PACKAGE_INIT = ROOT / "src" / "kater" / "__init__.py"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _package_versions() -> tuple[str, str]:
    with open(ROOT / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)["project"]["version"]
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', PACKAGE_INIT.read_text())
    if not match:
        raise SystemExit("ERROR: __version__ not found in src/kater/__init__.py")
    return pyproject, match.group(1)


def _resolve_channel(tag: str) -> dict | None:
    for channel in POLICY["channels"].values():
        if re.fullmatch(channel["tag_pattern"], tag):
            return channel
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag", help="release tag, e.g. v1.0.0 or v1.0.0.dev1")
    ap.add_argument(
        "--commit",
        default=None,
        help="commit to check ancestry for (default: resolve from the tag). "
        "Use HEAD for workflow_dispatch releases where the tag does not exist yet.",
    )
    ap.add_argument(
        "--main-ref", default="origin/main", help="mainline ref for the ancestry check"
    )
    ap.add_argument("--artifacts-dir", default="dist", help="dir scanned for built artifacts")
    args = ap.parse_args()

    tag = args.tag
    channel = _resolve_channel(tag)
    if channel is None:
        print(f"ERROR: tag {tag!r} matches no channel in release-policy.json", file=sys.stderr)
        return 1
    print(f"channel: {channel['name']} (prerelease={channel['prerelease']})")

    version = tag[1:]  # strip leading 'v'
    if not re.fullmatch(channel["version_pattern"], version):
        print(
            f"ERROR: version {version!r} does not match the {channel['name']} "
            f"version pattern {channel['version_pattern']!r}",
            file=sys.stderr,
        )
        return 1
    print(f"tag format ok: {tag} -> version {version}")

    pyproject_ver, init_ver = _package_versions()
    if pyproject_ver != version or init_ver != version:
        print(
            f"ERROR: tag version {version!r} != pyproject.toml ({pyproject_ver!r}) "
            f"or src/kater/__init__.py ({init_ver!r}). Bump the package in a PR first.",
            file=sys.stderr,
        )
        return 1
    print(f"version matches package sources: {version}")

    # ── immutable ancestry ──────────────────────────────────────────────
    if args.commit:
        commit = args.commit
    else:
        try:
            commit = _git("rev-parse", f"{tag}^{{commit}}")
        except subprocess.CalledProcessError:
            print(f"ERROR: {tag!r} does not resolve to a commit", file=sys.stderr)
            return 1
    try:
        _git("rev-parse", "--verify", args.main_ref)
    except subprocess.CalledProcessError:
        print(
            f"ERROR: main ref {args.main_ref!r} not found; cannot verify ancestry. "
            f"Fetch it first (e.g. `git fetch origin main`).",
            file=sys.stderr,
        )
        return 1
    anc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, args.main_ref],
        cwd=ROOT,
    )
    if anc.returncode != 0:
        print(
            f"ERROR: commit {commit[:12]} is NOT an ancestor of {args.main_ref} — "
            f"rewritten or orphaned tag",
            file=sys.stderr,
        )
        return 1
    print(f"immutable ancestry ok: {commit[:12]} is on {args.main_ref}")

    # ── artifact version check (optional; dist/ is empty before `uv build`) ──
    dist = ROOT / args.artifacts_dir
    artifacts = sorted(
        p.name
        for p in dist.iterdir()
        if p.is_file() and (p.name.endswith(".whl") or p.name.endswith(".tar.gz"))
    ) if dist.is_dir() else []
    if artifacts:
        for name in artifacts:
            if version not in name:
                print(
                    f"ERROR: artifact {name!r} does not contain version {version!r}",
                    file=sys.stderr,
                )
                return 1
        print(f"artifact version ok ({len(artifacts)} artifacts)")
    else:
        print("no artifacts found in dist/ - skipping artifact version check")

    print("validate_release: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())