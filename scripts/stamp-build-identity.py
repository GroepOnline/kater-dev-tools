#!/usr/bin/env python3
"""Write ``src/kater/_build_identity.json`` at build or install time.

Install/build only. The running service never calls this and never reads git
to invent a deployed identity. ``git describe --exact-match --tags`` plus
``git rev-parse HEAD`` are used here solely when the operator did not pass
those values, which matches a git-checkout install on the host.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parent.parent
if str(ROOT_DEFAULT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "src"))

from kater.build_identity import STAMP_NAME, write_stamp  # noqa: E402


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _package_version(root: Path) -> str:
    with open(root / "pyproject.toml", "rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT_DEFAULT), help="checkout or release tree")
    parser.add_argument("--version", default=None, help="package version; default: pyproject.toml")
    parser.add_argument("--sha", default=None, help="40-char lowercase commit SHA")
    parser.add_argument(
        "--release",
        default=None,
        help="exact tag such as v1.1.1; omit to try git describe --exact-match",
    )
    parser.add_argument("--digest", default=None, help="optional sha256 of a built artifact")
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="do not read git; --sha and --version must be provided",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    git_root = Path.cwd().resolve()

    version = args.version
    if version is None:
        if args.no_git:
            print("ERROR: --version is required with --no-git", file=sys.stderr)
            return 1
        version = _package_version(root)

    sha = args.sha
    if sha is None:
        if args.no_git:
            print("ERROR: --sha is required with --no-git", file=sys.stderr)
            return 1
        try:
            sha = _git(git_root, "rev-parse", "HEAD")
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: git rev-parse HEAD failed: {exc.stderr}", file=sys.stderr)
            return 1

    release = args.release
    if release is None and not args.no_git:
        try:
            release = _git(git_root, "describe", "--exact-match", "--tags", sha)
        except subprocess.CalledProcessError:
            release = None

    identity = write_stamp(
        root / "src" / "kater" / STAMP_NAME,
        version=version,
        source_sha=sha,
        release=release,
        artifact_digest=args.digest,
    )
    print(f"stamped {root / 'src' / 'kater' / STAMP_NAME}")
    for key, value in identity.items():
        print(f"{key}={value if value is not None else 'null'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
