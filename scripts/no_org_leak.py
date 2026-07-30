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
# split audit, license, code-owner routing, changelog). Anything outside these is a leak.
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
        # CODEOWNERS exists specifically to map paths to GitHub owners, so the
        # org handle is the file's whole purpose — not a leak.
        ".github/CODEOWNERS",
        # CHANGELOG.md links to compare/release views under the org's GitHub
        # domain; the org handle appears in every URL by design.
        "CHANGELOG.md",
        # The four vendored contract schemas below are pinned by content digest
        # (see ``GENERATED_CONTRACT_DIGEST`` in
        # ``src/kater/capabilities/computer.py``). Their $id URLs are emitted by
        # the upstream contract generator and cannot be renamed independently;
        # migrating them to a neutral host is a generator-side change tracked
        # outside this script's audit scope. Treat as package-internal JSON
        # Schema references only — never dereference over the network.
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
        # Same four vendored contract schemas as above. See the
        # ALLOWED_ORG_HANDLE note for the rationale; this exemption will be
        # lifted once the contract generator ships with neutral hostnames.
        "src/kater/capabilities/generated/error-envelope.json",
        "src/kater/capabilities/generated/guest-invocation-result.schema.json",
        "src/kater/capabilities/generated/guest-invocation.schema.json",
        "src/kater/capabilities/generated/staged-artifact.schema.json",
    }
)
# Audit-allowlist for ``CHE-*`` references. Project-tracker IDs only appear in
# the split-record documents; the test fixture (illustrative) and the
# capability-manifest comment shipped in P0. Anything else is a leak.
ALLOWED_INTERNAL_ID = frozenset(
    {
        "AUDIT.md",
        "SPLIT_DECISION.md",
        "tests/fixtures/private_extension.py",
        "src/kater/capabilities/schemas/capability-manifest.schema.json",
        # The detector itself encodes the patterns as literal regex text and
        # comments; self-allowlist is required so the scanner can describe
        # what it scans for. Same pattern as gitleaks allowing its own
        # ``.gitleaks.toml`` to mention its own secret-keyword names.
        "scripts/no_org_leak.py",
    }
)
# Audit-allowlist for the private Utrecht Data OS / overlay references. These
# only appear in the OSS-private-split audit docs and the private acceptance
# lane (CI workflow + gated test). The detector itself is also allowlisted
# because its regex literals and comments contain the same substrings.
ALLOWED_PRIVATE_DATA_PLANE = frozenset(
    {
        "AUDIT.md",
        "SPLIT_DECISION.md",
        ".github/workflows/ci.yml",
        "tests/acceptance/computer_lane.py",
        "tests/acceptance/kater_server.py",
        "tests/test_computer_acceptance_e2e.py",
        "tests/test_ci_dependabot_policy.py",
        "scripts/no_org_leak.py",
    }
)
# ``kater-utrecht`` was a legacy gateway alias before the ``utrecht`` profile
# was moved to the extension hook. The detector still flags any residual
# reference; only the audit docs and the detector itself are allowlisted
# (the latter because its regex literal and comments mention the alias).
ALLOWED_LEGACY_ALIAS = frozenset(
    {
        "AUDIT.md",
        "SPLIT_DECISION.md",
        "scripts/no_org_leak.py",
    }
)

# Regex sources of truth. Anything outside the explicit allowlists below trips
# the detector. Tightened after the P0/P1 OSS-private split audits:
#   - ``PROD_DOMAIN_RE``   — the org production domains
#   - ``ORG_HANDLE_RE``    — the org GitHub handle across all forms
#   - ``CREDENTIAL_CONN_RE`` — credential-shaped connection strings
#   - ``INTERNAL_ID_RE``   — org-internal Jira/Linear/CHE-* ticket IDs
#   - ``PRIVATE_DATA_PLANE_RE`` — references to the private data-plane repo
#     and the Utrecht Data OS overlay (in any upper/lower-case form)
#   - ``LEGACY_ALIAS_RE``  — the legacy ``kater-utrecht`` overlap alias
PROD_DOMAIN_RE = re.compile(r"chefgroep\.(nl|online)", re.IGNORECASE)
ORG_HANDLE_RE = re.compile(r"online" + r"chefgroep", re.IGNORECASE)
CREDENTIAL_CONN_RE = re.compile(r"(postgres|redis|upstash)://[^\"'\s]+@")
INTERNAL_ID_RE = re.compile(r"\bCHE-[0-9]+\b", re.IGNORECASE)
PRIVATE_DATA_PLANE_RE = re.compile(
    r"\b(utrecht[-_]katermcp|utrecht[-_]data[-_]os|\bUDO\b|\butrecht[-_]data\b)\b",
    re.IGNORECASE,
)
LEGACY_ALIAS_RE = re.compile(r"\bkater[-_]utrecht\b", re.IGNORECASE)


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

        if INTERNAL_ID_RE.search(text):
            # Internal Jira/Linear ticket IDs (e.g. CHE-659, CHE-693) only live
            # in the OSS/private-split audit docs; references anywhere else —
            # including the embedding ``(CHE-659)`` parenthetical I saw in
            # .env.example — are leaks of the org's internal tracking structure.
            if rel not in ALLOWED_INTERNAL_ID:
                errors.append(f"{rel}: internal tracking id outside audit allowlist")

        if PRIVATE_DATA_PLANE_RE.search(text):
            if rel not in ALLOWED_PRIVATE_DATA_PLANE:
                errors.append(f"{rel}: private data-plane reference outside audit allowlist")

        if LEGACY_ALIAS_RE.search(text):
            if rel not in ALLOWED_LEGACY_ALIAS:
                errors.append(f"{rel}: legacy kater-utrecht alias outside allowlist")

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
