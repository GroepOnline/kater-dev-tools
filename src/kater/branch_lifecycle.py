"""Remote-branch lifecycle scanner: tombstones, dry-run, never unique patches.

GitHub repository invariant: ``delete_branch_on_merge`` stays enabled
(``DELETE_BRANCH_ON_MERGE is True``). This module never mutates that setting.
Default CLI mode is dry-run and never runs ``git push --delete``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TextIO, TypedDict, cast

DELETE_BRANCH_ON_MERGE: bool = True
SHA_HEX_LEN = 40
DEFAULT_BASE = "main"
PROTECTED_REF_NAMES = frozenset({"HEAD", "origin", "master", DEFAULT_BASE})

Action = Literal["would-delete", "retained", "tombstoned"]

Receipt = TypedDict(
    "Receipt",
    {
        "name": str,
        "sha": str,
        "action": Action,
        "reason": str,
        "class": str,
        "unique_patch": bool,
    },
)

RETAIN_CLASSES = frozenset(
    {
        "autoresearch",
        "prototype",
        "rescue",
        "jules",
        "palette",
        "parked",
        "salvage-only",
        "donor-history",
    }
)

SUPERSEDED_NAMES = frozenset(
    {
        "feat/chefvault-integration",
        "fix/browser-cgnat-egress",
        "chore/pin-mcp-lt-2",
        "fix/pr-gate-gh-json-fields",
        "fix/pr-gate-gh-reviewthreads",
    }
)
SALVAGE_ONLY_NAME = "feat/scaffold-project-core-integration-types"


@dataclass(frozen=True)
class Tombstone:
    name: str
    sha: str
    branch_class: str
    reason: str


TOMBSTONES: tuple[Tombstone, ...] = (
    Tombstone(
        "chore/pin-mcp-lt-2",
        "d0322a37ba95b560ff82cd3bef23238f87c5bc24",
        "obsolete",
        "tree uses MCP 2.x",
    ),
    Tombstone(
        "feat/chefvault-integration",
        "759d13c4d8bad56111f98f950051786a172bbb58",
        "superseded",
        "ChefVault on main",
    ),
    Tombstone(
        "fix/browser-cgnat-egress",
        "2f4b3117d67b74b25787f47cb3f2bb1d8bfcff59",
        "superseded",
        "CGNAT on main",
    ),
    Tombstone(
        "fix/pr-gate-gh-json-fields",
        "332dc48763264ef9ca17444897b30fdd436bdfa2",
        "superseded",
        "reviewThreads/fail-closed on main",
    ),
    Tombstone(
        "fix/pr-gate-gh-reviewthreads",
        "84c37e8651e839f50ae60b1f125fbb8e7b7b5891",
        "superseded",
        "reviewThreads/fail-closed on main",
    ),
    Tombstone(
        "feat/scaffold-project-core-integration-types",
        "c70699de552fe52becda7886454e9afaeb74e1ea",
        "salvage-only",
        "never merge wholesale",
    ),
    Tombstone(
        "palette-profile-recovery-14826043716077132865",
        "3ee3aa6c57ec0c5416c27355a84a8cd8706a764b",
        "palette",
        "donor; extract UX only",
    ),
    Tombstone(
        "palette-browser-loading-feedback-5480200343156298719",
        "5efe3f9d4c9f1a3b3c2c3dd833238b9033bdc2e0",
        "palette",
        "donor; extract UX only",
    ),
    Tombstone(
        "jules-4802806421746281431-c2509d83",
        "457e8e0e193c540010b77a7c6b13ab413d515ff2",
        "jules",
        "sibling profile-recovery donor",
    ),
    Tombstone(
        "jules-15172571045138015352-c5bfdfd3",
        "e7743e0615611479693e5a61a78cb2a27e0b98cd",
        "jules",
        "donor history",
    ),
    Tombstone(
        "jules-15640634542643590975-b271e696",
        "312926ca48ac408f7f0dbc742a422ca0d6a1097c",
        "jules",
        "donor history",
    ),
    Tombstone(
        "autoresearch/kater-mcp-85pct-20260828",
        "5f3b0041dc4167604b31a416c379f933f17d7ef4",
        "autoresearch",
        "retain",
    ),
    Tombstone(
        "prototype/pr-159-control-room",
        "8fce0613488c105d3fdbc315c6524426d25b7cc8",
        "prototype",
        "retain",
    ),
    Tombstone(
        "rescue/pr-159-backup",
        "8d8b9def955ec8e37fbb4b53b3d2fe644f880248",
        "rescue",
        "retain",
    ),
    Tombstone(
        "cursor/kater-browser-lane-ui-overhaul-1100",
        "0a953a4d4d5067d59add9446bc1df4277bcd2e5e",
        "donor-history",
        "huge overhaul; not auto-delete",
    ),
    Tombstone(
        "codesmith/pr180-lint-fix",
        "7d2321240d86c8b258b84d4eb71906f36617e2a9",
        "donor-history",
        "not auto-delete",
    ),
    Tombstone(
        "devin/fork-gate-and-control-plane-upgrade",
        "20278167bb0d1647d9a5278828094ee1723d152c",
        "donor-history",
        "not auto-delete",
    ),
)

TOMBSTONE_BY_NAME: dict[str, Tombstone] = {item.name: item for item in TOMBSTONES}

ListRemoteBranches = Callable[[], Sequence[object]]
UniqueCommitCount = Callable[..., int | None]
OpenPrHeads = Callable[[], set[str]]
DeleteRef = Callable[[str], None]


class _NamedSha(Protocol):
    name: object
    sha: object


def delete_branch_on_merge_enabled() -> bool:
    """Documented GitHub setting; never call ``gh`` to mutate it."""
    return DELETE_BRANCH_ON_MERGE


def normalize_branch_name(name: str) -> str:
    n = name.strip()
    prefixes = (
        "refs/remotes/origin/",
        "refs/heads/",
        "origin/",
    )
    for prefix in prefixes:
        if n.startswith(prefix):
            n = n[len(prefix) :]
            break
    return n


def is_protected_ref(name: str, base: str = DEFAULT_BASE) -> bool:
    n = normalize_branch_name(name)
    return (not n) or n in PROTECTED_REF_NAMES or n == base or n.endswith("/HEAD")


def classify_branch(name: str) -> str:
    n = normalize_branch_name(name)
    tombstone = TOMBSTONE_BY_NAME.get(n)
    if tombstone is not None:
        return tombstone.branch_class
    if n.startswith("autoresearch/"):
        return "autoresearch"
    if n.startswith("prototype/"):
        return "prototype"
    if n.startswith("rescue/"):
        return "rescue"
    if n.startswith("jules-"):
        return "jules"
    if n.startswith("palette-"):
        return "palette"
    if n.startswith("dependabot/"):
        return "dependabot"
    return "other"


def is_unique_patch(unique_commit_count: int | None) -> bool:
    return unique_commit_count != 0


def is_auto_deletable(
    *,
    unique_commit_count: int | None,
    has_open_pr: bool,
    branch_class: str,
    tombstoned: bool = False,
) -> bool:
    if tombstoned:
        return False
    if unique_commit_count != 0:
        return False
    if has_open_pr:
        return False
    if branch_class in RETAIN_CLASSES:
        return False
    return True


def parse_remote_refs(output: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in output.splitlines():
        line = raw.strip()
        if not line or (" " not in line and "\t" not in line):
            continue
        name_part, sha = line.rsplit(None, 1)
        if len(sha) != SHA_HEX_LEN or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
            continue
        name = normalize_branch_name(name_part)
        if is_protected_ref(name):
            continue
        if name in seen:
            continue
        seen.add(name)
        refs.append({"name": name, "sha": sha.lower()})
    return refs


def _coerce_ref(item: object) -> tuple[str, str]:
    if isinstance(item, Mapping):
        name = str(item["name"])
        sha = str(item["sha"])
        return normalize_branch_name(name), sha.lower()
    named = cast(_NamedSha, item)
    return normalize_branch_name(str(named.name)), str(named.sha).lower()


def _call_unique_count(fn: UniqueCommitCount, sha: str, base: str = DEFAULT_BASE) -> int | None:
    try:
        return fn(sha, base=base)
    except TypeError:
        return fn(sha, base)


def _receipt(
    *,
    name: str,
    sha: str,
    action: Action,
    reason: str,
    branch_class: str,
    unique_patch: bool,
) -> Receipt:
    return {
        "name": name,
        "sha": sha,
        "action": action,
        "reason": reason,
        "class": branch_class,
        "unique_patch": unique_patch,
    }


def _tombstone_reason(tombstone: Tombstone, live_sha: str) -> str:
    if live_sha != tombstone.sha:
        return (
            f"{tombstone.reason}; recreation of terminal name flagged "
            f"(tombstone sha {tombstone.sha})"
        )
    return tombstone.reason


def scan(
    *,
    list_remote_branches: ListRemoteBranches,
    unique_commit_count: UniqueCommitCount,
    open_pr_heads: OpenPrHeads,
    delete_branch_on_merge_enabled: Callable[[], bool] = delete_branch_on_merge_enabled,
    delete_ref: DeleteRef | None = None,
    apply: bool = False,
    base: str = DEFAULT_BASE,
) -> list[Receipt]:
    """Scan remotes + tombstones. ``apply`` never deletes unique patches."""
    _ = delete_branch_on_merge_enabled()
    open_heads = {normalize_branch_name(n) for n in open_pr_heads()}
    live: dict[str, str] = {}
    for item in list_remote_branches():
        name, sha = _coerce_ref(item)
        if is_protected_ref(name, base=base):
            continue
        live[name] = sha

    receipts: list[Receipt] = []
    names = sorted(set(live) | set(TOMBSTONE_BY_NAME))
    for name in names:
        tombstone = TOMBSTONE_BY_NAME.get(name)
        sha = live[name] if name in live else TOMBSTONE_BY_NAME[name].sha
        branch_class = classify_branch(name)
        count = _call_unique_count(unique_commit_count, sha, base)
        unique = is_unique_patch(count)
        has_pr = name in open_heads
        if tombstone is not None:
            receipts.append(
                _receipt(
                    name=name,
                    sha=sha,
                    action="tombstoned",
                    reason=_tombstone_reason(tombstone, sha),
                    branch_class=branch_class,
                    unique_patch=unique,
                )
            )
            continue
        if is_auto_deletable(
            unique_commit_count=count,
            has_open_pr=has_pr,
            branch_class=branch_class,
            tombstoned=False,
        ):
            receipts.append(
                _receipt(
                    name=name,
                    sha=sha,
                    action="would-delete",
                    reason="fully contained in main; no open PR",
                    branch_class=branch_class,
                    unique_patch=False,
                )
            )
            continue
        if unique:
            reason = "unique patch vs main; never auto-delete"
        elif has_pr:
            reason = "open PR"
        else:
            reason = f"class {branch_class} is retained"
        receipts.append(
            _receipt(
                name=name,
                sha=sha,
                action="retained",
                reason=reason,
                branch_class=branch_class,
                unique_patch=unique,
            )
        )

    if apply:
        for receipt in receipts:
            if receipt["unique_patch"]:
                continue
            if receipt["action"] != "would-delete":
                continue
            if is_protected_ref(receipt["name"], base=base):
                continue
            if delete_ref is not None:
                delete_ref(receipt["name"])
    return receipts


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )


def git_list_remote_branches() -> list[dict[str, str]]:
    completed = _run_git(
        ["for-each-ref", "--format=%(refname:short) %(objectname)", "refs/remotes/origin"]
    )
    if completed.returncode != 0:
        return []
    return parse_remote_refs(completed.stdout)


def git_unique_commit_count(sha: str, base: str = DEFAULT_BASE) -> int | None:
    merge_base = _run_git(["merge-base", sha, base])
    if merge_base.returncode != 0:
        return None
    counted = _run_git(["rev-list", "--count", f"{base}..{sha}"])
    if counted.returncode != 0:
        return None
    try:
        return int(counted.stdout.strip() or "0")
    except ValueError:
        return None


def git_open_pr_heads() -> set[str]:
    completed = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "headRefName"],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return set()
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return set()
    heads: set[str] = set()
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, Mapping) and row.get("headRefName"):
                heads.add(normalize_branch_name(str(row["headRefName"])))
    return heads


def git_delete_ref(name: str) -> None:
    branch = normalize_branch_name(name)
    if is_protected_ref(branch):
        raise RuntimeError(f"refusing to delete protected ref {branch}")
    completed = _run_git(["push", "origin", "--delete", branch])
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"refusing incomplete delete of {branch}: {err}")


def default_scan_kwargs() -> dict[str, Any]:
    return {
        "list_remote_branches": git_list_remote_branches,
        "unique_commit_count": git_unique_commit_count,
        "open_pr_heads": git_open_pr_heads,
        "delete_branch_on_merge_enabled": delete_branch_on_merge_enabled,
        "delete_ref": git_delete_ref,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kater.branch_lifecycle",
        description=(
            "Dry-run stale/no-PR/superseded scanner. Never auto-deletes unique patches. "
            "GitHub delete_branch_on_merge must stay true."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report receipts only (default; never git push --delete)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete auto_deletable refs only; unique patches are always skipped",
    )
    parser.add_argument("--json", action="store_true", help="emit receipts as JSON")
    return parser


def resolve_apply(*, dry_run: bool, apply: bool) -> bool:
    if dry_run:
        return False
    return apply


def format_receipts_text(receipts: Sequence[Receipt]) -> str:
    lines = [
        (
            f"{item['action']:<12} {item['class']:<14} {item['name']} "
            f"{item['sha']} unique_patch={str(item['unique_patch']).lower()} "
            f"{item['reason']}"
        )
        for item in receipts
    ]
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    list_remote_branches: ListRemoteBranches | None = None,
    unique_commit_count: UniqueCommitCount | None = None,
    open_pr_heads: OpenPrHeads | None = None,
    delete_ref: DeleteRef | None = None,
    stdout: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    apply = resolve_apply(dry_run=bool(args.dry_run), apply=bool(args.apply))
    list_fn = list_remote_branches or git_list_remote_branches
    count_fn = unique_commit_count or git_unique_commit_count
    pr_fn = open_pr_heads or git_open_pr_heads
    delete_fn: DeleteRef | None
    if delete_ref is not None:
        delete_fn = delete_ref
    elif apply:
        delete_fn = git_delete_ref
    else:
        delete_fn = None
    receipts = scan(
        apply=apply,
        list_remote_branches=list_fn,
        unique_commit_count=count_fn,
        open_pr_heads=pr_fn,
        delete_ref=delete_fn,
    )
    out = stdout if stdout is not None else sys.stdout
    if args.json:
        json.dump(receipts, out, indent=2)
        out.write("\n")
    else:
        out.write(format_receipts_text(receipts) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
