#!/usr/bin/env python3
"""Org-leak guard: a self-contained, testable checker.

Scans the working tree (or a git diff range) for org production domains,
the org GitHub handle outside attribution files, and credential-shaped
connection strings. The allowlist is explicit so reviewers can see exactly
what is permitted and why.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Files where the org handle / domain are legitimately expected (attribution,
# split audit, license). Anything outside these is a leak.
ALLOWED_ORG_HANDLE = frozenset(
    {
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "pyproject.toml",
        "docs/deploy-server.md",
        "SPLIT_DECISION.md",
        "AUDIT.md",
        "no-org-leak.yml",
        "src/kater/capabilities/generated/error-envelope.json",
        "src/kater/capabilities/generated/guest-invocation-result.schema.json",
        "src/kater/capabilities/generated/guest-invocation.schema.json",
        "src/kater/capabilities/generated/staged-artifact.schema.json",
    }
)
ALLOWED_PROD_DOMAIN = frozenset(
    {
        "SPLIT_DECISION.md",
        "AUDIT.md",
        "no-org-leak.yml",
        "docs/deploy-server.md",
        "src/kater/capabilities/generated/error-envelope.json",
        "src/kater/capabilities/generated/guest-invocation-result.schema.json",
        "src/kater/capabilities/generated/guest-invocation.schema.json",
        "src/kater/capabilities/generated/staged-artifact.schema.json",
    }
)

PROD_DOMAIN_RE = re.compile(r"chefgroep\.(nl|online)", re.IGNORECASE)
ORG_HANDLE_RE = re.compile(r"online" + r"chefgroep", re.IGNORECASE)
CREDENTIAL_CONN_RE = re.compile(r"(postgres|redis|upstash)://[^\"'\s]+@")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [f for f in out if not f.startswith("node_modules/")]


def _diff_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [f for f in out if f]


def scan(targets: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in targets:
        path = Path(rel)
        if not path.exists():
            continue
        if path.is_dir():
            continue
        # Allowlist entries are repository-relative paths, never basenames. A
        # nested README.md must not inherit the root README's attribution exemption.
        rel = path.as_posix()
        try:
            text = path.read_text(errors="ignore")
        except (OSError, UnicodeError):
            continue

        if PROD_DOMAIN_RE.search(text):
            if rel not in ALLOWED_PROD_DOMAIN:
                errors.append(f"{rel}: org production domain outside allowlist")

        if ORG_HANDLE_RE.search(text):
            if rel not in ALLOWED_ORG_HANDLE:
                errors.append(f"{rel}: org handle outside attribution allowlist")

        if CREDENTIAL_CONN_RE.search(text):
            errors.append(f"{rel}: credential-shaped connection string")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None, help="git diff base (default: full tree)")
    args = ap.parse_args()

    targets = _diff_files(args.base) if args.base else _tracked_files()
    errors = scan(targets)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("no-org-leak: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
