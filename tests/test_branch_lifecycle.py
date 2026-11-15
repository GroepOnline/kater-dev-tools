from __future__ import annotations

import io
import json
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from kater.branch_lifecycle import (
    SALVAGE_ONLY_NAME,
    SHA_HEX_LEN,
    SUPERSEDED_NAMES,
    TOMBSTONE_BY_NAME,
    TOMBSTONES,
    _run_git,
    classify_branch,
    default_scan_kwargs,
    format_receipts_text,
    git_delete_ref,
    git_list_remote_branches,
    git_open_pr_heads,
    git_unique_commit_count,
    is_auto_deletable,
    is_protected_ref,
    is_unique_patch,
    main,
    normalize_branch_name,
    parse_remote_refs,
    resolve_apply,
    scan,
)

MERGED_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
UNIQUE_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
STALE_NAME = "chore/fully-merged-stale"


def _counts(mapping: dict[str, int | None]) -> Any:
    def _fn(sha: str, base: str = "main") -> int | None:
        _ = base
        return mapping.get(sha, 0)

    return _fn


def _scan(
    remotes: list[dict[str, str]],
    counts: dict[str, int | None],
    *,
    open_prs: set[str] | None = None,
    apply: bool = False,
    delete_ref: Any = None,
) -> list[dict[str, Any]]:
    return scan(
        list_remote_branches=lambda: remotes,
        unique_commit_count=_counts(counts),
        open_pr_heads=lambda: open_prs or set(),
        apply=apply,
        delete_ref=delete_ref,
    )


def _by_name(receipts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in receipts}


def _record_delete(deleted: list[str]):
    def _delete(name: str, expected_sha: str) -> bool:
        assert len(expected_sha) == 40
        deleted.append(name)
        return True

    return _delete


def test_unique_patch_never_auto_deletable() -> None:
    assert is_unique_patch(1) is True
    assert is_unique_patch(None) is True
    assert is_unique_patch(0) is False
    assert (
        is_auto_deletable(
            unique_commit_count=3,
            has_open_pr=False,
            branch_class="other",
        )
        is False
    )
    assert (
        is_auto_deletable(
            unique_commit_count=None,
            has_open_pr=False,
            branch_class="dependabot",
        )
        is False
    )


def test_superseded_with_unique_commits_is_retained() -> None:
    name = "feat/chefvault-integration"
    tombstone = TOMBSTONE_BY_NAME[name]
    receipts = _scan(
        [{"name": name, "sha": tombstone.sha}],
        {tombstone.sha: 12},
    )
    item = _by_name(receipts)[name]
    assert item["class"] == "superseded"
    assert item["unique_patch"] is True
    assert item["action"] == "tombstoned"
    assert item["sha"] == tombstone.sha
    assert (
        is_auto_deletable(
            unique_commit_count=12,
            has_open_pr=False,
            branch_class="superseded",
        )
        is False
    )


def test_superseded_live_non_tombstone_unique_is_retained() -> None:
    receipts = _scan(
        [{"name": "feat/chefvault-integration-extra", "sha": UNIQUE_SHA}],
        {UNIQUE_SHA: 4},
    )
    item = _by_name(receipts)["feat/chefvault-integration-extra"]
    assert item["action"] == "retained"
    assert item["unique_patch"] is True
    assert "never auto-delete" in item["reason"]


def test_fully_merged_stale_no_pr_would_delete() -> None:
    receipts = _scan(
        [{"name": STALE_NAME, "sha": MERGED_SHA}],
        {MERGED_SHA: 0},
    )
    item = _by_name(receipts)[STALE_NAME]
    assert item["action"] == "would-delete"
    assert item["unique_patch"] is False
    assert item["class"] == "other"
    assert item["sha"] == MERGED_SHA
    assert (
        is_auto_deletable(
            unique_commit_count=0,
            has_open_pr=False,
            branch_class="other",
        )
        is True
    )


def test_open_pr_blocks_delete() -> None:
    receipts = _scan(
        [{"name": STALE_NAME, "sha": MERGED_SHA}],
        {MERGED_SHA: 0},
        open_prs={STALE_NAME},
    )
    item = _by_name(receipts)[STALE_NAME]
    assert item["action"] == "retained"
    assert item["reason"] == "open PR"


def test_tombstone_sha_is_exact_40_char() -> None:
    assert len(TOMBSTONES) == 17
    seen: set[str] = set()
    for item in TOMBSTONES:
        assert len(item.sha) == SHA_HEX_LEN
        assert len(item.sha) == 40
        assert set(item.sha) <= set("0123456789abcdef")
        assert item.name not in seen
        seen.add(item.name)
        assert TOMBSTONE_BY_NAME[item.name].sha == item.sha


def test_dry_run_does_not_call_delete() -> None:
    deleted: list[str] = []
    _scan(
        [{"name": STALE_NAME, "sha": MERGED_SHA}],
        {MERGED_SHA: 0},
        apply=False,
        delete_ref=_record_delete(deleted),
    )
    assert deleted == []
    buf = io.StringIO()
    main(
        ["--dry-run"],
        list_remote_branches=lambda: [{"name": STALE_NAME, "sha": MERGED_SHA}],
        unique_commit_count=_counts({MERGED_SHA: 0}),
        open_pr_heads=lambda: set(),
        delete_ref=_record_delete(deleted),
        stdout=buf,
    )
    assert deleted == []
    assert "would-delete" in buf.getvalue()


def test_apply_skips_unique_patches_and_deletes_only_stale() -> None:
    deleted: list[str] = []
    unique_name = "fix/unique-work"
    receipts = _scan(
        [
            {"name": STALE_NAME, "sha": MERGED_SHA},
            {"name": unique_name, "sha": UNIQUE_SHA},
        ],
        {MERGED_SHA: 0, UNIQUE_SHA: 2},
        apply=True,
        delete_ref=_record_delete(deleted),
    )
    by_name = _by_name(receipts)
    assert by_name[STALE_NAME]["action"] == "would-delete"
    assert by_name[unique_name]["action"] == "retained"
    assert by_name[unique_name]["unique_patch"] is True
    assert deleted == [STALE_NAME]


def test_apply_refuses_tombstone_names() -> None:
    deleted: list[str] = []
    name = "chore/pin-mcp-lt-2"
    sha = TOMBSTONE_BY_NAME[name].sha
    receipts = _scan(
        [{"name": name, "sha": sha}],
        {sha: 0},
        apply=True,
        delete_ref=_record_delete(deleted),
    )
    item = _by_name(receipts)[name]
    assert item["action"] == "tombstoned"
    assert item["class"] == "obsolete"
    assert deleted == []


def test_classes_jules_palette_autoresearch_prototype_rescue_scaffold() -> None:
    assert classify_branch("jules-4802806421746281431-c2509d83") == "jules"
    assert classify_branch("origin/jules-new-donor") == "jules"
    assert classify_branch("palette-browser-loading-feedback-5480200343156298719") == "palette"
    assert classify_branch("palette-fresh-ux") == "palette"
    assert classify_branch("autoresearch/kater-mcp-85pct-20260828") == "autoresearch"
    assert classify_branch("autoresearch/next-study") == "autoresearch"
    assert classify_branch("prototype/pr-159-control-room") == "prototype"
    assert classify_branch("prototype/lab") == "prototype"
    assert classify_branch("rescue/pr-159-backup") == "rescue"
    assert classify_branch("rescue/hotfix") == "rescue"
    assert classify_branch("feat/scaffold-project-core-integration-types") == "salvage-only"
    assert classify_branch("dependabot/pip/foo") == "dependabot"
    assert classify_branch("feat/chefvault-integration") == "superseded"
    assert classify_branch("cursor/kater-browser-lane-ui-overhaul-1100") == "donor-history"


def test_retain_classes_never_auto_delete_even_when_merged() -> None:
    cases = (
        ("autoresearch/next-study", "autoresearch"),
        ("prototype/lab", "prototype"),
        ("rescue/hotfix", "rescue"),
        ("jules-new-donor", "jules"),
        ("palette-fresh-ux", "palette"),
    )
    remotes = [{"name": name, "sha": MERGED_SHA} for name, _cls in cases]
    receipts = _by_name(_scan(remotes, {MERGED_SHA: 0}))
    for name, branch_class in cases:
        item = receipts[name]
        assert item["class"] == branch_class
        assert item["action"] == "retained"
        assert item["unique_patch"] is False
        assert (
            is_auto_deletable(
                unique_commit_count=0,
                has_open_pr=False,
                branch_class=branch_class,
            )
            is False
        )


def test_tombstoned_salvage_and_donor_history_not_auto_deletable() -> None:
    for name in (
        "feat/scaffold-project-core-integration-types",
        "codesmith/pr180-lint-fix",
        "devin/fork-gate-and-control-plane-upgrade",
    ):
        assert (
            is_auto_deletable(
                unique_commit_count=0,
                has_open_pr=False,
                branch_class=classify_branch(name),
                tombstoned=True,
            )
            is False
        )


def test_tombstone_recreation_is_flagged() -> None:
    name = "prototype/pr-159-control-room"
    receipts = _scan(
        [{"name": name, "sha": UNIQUE_SHA}],
        {UNIQUE_SHA: 1},
    )
    item = _by_name(receipts)[name]
    assert item["action"] == "tombstoned"
    assert item["sha"] == UNIQUE_SHA
    assert "recreation of terminal name flagged" in item["reason"]
    assert TOMBSTONE_BY_NAME[name].sha in item["reason"]


def test_missing_tombstones_are_reported_with_exact_sha() -> None:
    receipts = _scan([], {})
    by_name = _by_name(receipts)
    for tombstone in TOMBSTONES:
        item = by_name[tombstone.name]
        assert item["action"] == "tombstoned"
        assert item["sha"] == tombstone.sha
        assert len(item["sha"]) == 40
        assert item["class"] == tombstone.branch_class


def test_origin_prefix_and_head_exclusion() -> None:
    assert normalize_branch_name("origin/feat/x") == "feat/x"
    assert normalize_branch_name("refs/heads/feat/x") == "feat/x"
    assert normalize_branch_name("refs/remotes/origin/feat/x") == "feat/x"
    parsed = parse_remote_refs(
        "\n".join(
            [
                f"origin/HEAD {MERGED_SHA}",
                f"HEAD {MERGED_SHA}",
                f"origin/main {MERGED_SHA}",
                f"origin {MERGED_SHA}",
                f"origin/{STALE_NAME} {MERGED_SHA}",
                "not-a-ref",
            ]
        )
    )
    assert parsed == [{"name": STALE_NAME, "sha": MERGED_SHA}]


def test_unrelated_history_is_unique_patch() -> None:
    receipts = _scan(
        [{"name": "experiment/orphan", "sha": UNIQUE_SHA}],
        {UNIQUE_SHA: None},
    )
    item = _by_name(receipts)["experiment/orphan"]
    assert item["unique_patch"] is True
    assert item["action"] == "retained"


def test_json_cli_and_dry_run_default() -> None:
    buf = io.StringIO()
    rc = main(
        ["--dry-run", "--json"],
        list_remote_branches=lambda: [{"name": STALE_NAME, "sha": MERGED_SHA}],
        unique_commit_count=_counts({MERGED_SHA: 0}),
        open_pr_heads=lambda: set(),
        delete_ref=lambda _name, _sha: True,
        stdout=buf,
    )
    assert rc == 0
    payload = json.loads(buf.getvalue())
    stale = next(item for item in payload if item["name"] == STALE_NAME)
    assert stale["action"] == "would-delete"
    assert stale["sha"] == MERGED_SHA
    assert set(stale) == {"name", "sha", "action", "reason", "class", "unique_patch"}


def test_resolve_apply_prefers_dry_run() -> None:
    assert resolve_apply(dry_run=False, apply=False) is False
    assert resolve_apply(dry_run=True, apply=True) is False
    assert resolve_apply(dry_run=False, apply=True) is True


def test_format_receipts_text_includes_sha() -> None:
    text = format_receipts_text(
        [
            {
                "name": STALE_NAME,
                "sha": MERGED_SHA,
                "action": "would-delete",
                "reason": "fully contained in main; no open PR",
                "class": "other",
                "unique_patch": False,
            }
        ]
    )
    assert MERGED_SHA in text
    assert STALE_NAME in text
    assert "would-delete" in text


def test_dependabot_merged_without_pr_would_delete() -> None:
    receipts = _scan(
        [{"name": "dependabot/pip/mcp-2.2", "sha": MERGED_SHA}],
        {MERGED_SHA: 0},
    )
    item = _by_name(receipts)["dependabot/pip/mcp-2.2"]
    assert item["class"] == "dependabot"
    assert item["action"] == "would-delete"


def test_documented_classification_constants() -> None:
    assert SALVAGE_ONLY_NAME == "feat/scaffold-project-core-integration-types"
    assert SUPERSEDED_NAMES == {
        "feat/chefvault-integration",
        "fix/browser-cgnat-egress",
        "chore/pin-mcp-lt-2",
        "fix/pr-gate-gh-json-fields",
        "fix/pr-gate-gh-reviewthreads",
    }


def test_parse_remote_refs_skips_bad_and_duplicates() -> None:
    parsed = parse_remote_refs(
        "\n".join(
            [
                "",
                f"origin/{STALE_NAME} {MERGED_SHA}",
                f"origin/{STALE_NAME} {MERGED_SHA}",
                f"weird {UNIQUE_SHA[:-1]}",
                "not-a-ref",
            ]
        )
    )
    assert parsed == [{"name": STALE_NAME, "sha": MERGED_SHA}]


def test_named_object_refs_and_positional_unique_count() -> None:
    def count_pos(sha: str, base: str = "main") -> int:
        _ = base
        return 0 if sha == MERGED_SHA else 1

    def count_only_pos(sha: str, *rest: str) -> int:
        _ = rest
        return count_pos(sha)

    receipts = scan(
        list_remote_branches=lambda: [
            SimpleNamespace(name=f"origin/{STALE_NAME}", sha=MERGED_SHA)
        ],
        unique_commit_count=count_only_pos,
        open_pr_heads=lambda: set(),
    )
    assert _by_name(receipts)[STALE_NAME]["action"] == "would-delete"
    again = scan(
        list_remote_branches=lambda: [{"name": STALE_NAME, "sha": MERGED_SHA}],
        unique_commit_count=count_pos,
        open_pr_heads=lambda: set(),
    )
    assert _by_name(again)[STALE_NAME]["action"] == "would-delete"


def test_apply_without_delete_ref_still_skips_unique() -> None:
    receipts = _scan(
        [
            {"name": STALE_NAME, "sha": MERGED_SHA},
            {"name": "fix/unique-work", "sha": UNIQUE_SHA},
        ],
        {MERGED_SHA: 0, UNIQUE_SHA: 9},
        apply=True,
        delete_ref=None,
    )
    by_name = _by_name(receipts)
    assert by_name[STALE_NAME]["action"] == "would-delete"
    assert by_name["fix/unique-work"]["unique_patch"] is True


def test_apply_cli_does_not_delete_unique_patch() -> None:
    deleted: list[str] = []
    buf = io.StringIO()
    main(
        ["--apply"],
        list_remote_branches=lambda: [
            {"name": STALE_NAME, "sha": MERGED_SHA},
            {"name": "fix/unique-work", "sha": UNIQUE_SHA},
        ],
        unique_commit_count=_counts({MERGED_SHA: 0, UNIQUE_SHA: 2}),
        open_pr_heads=lambda: set(),
        delete_ref=_record_delete(deleted),
        stdout=buf,
    )
    assert deleted == [STALE_NAME]
    assert "unique patch vs main" in buf.getvalue()


def test_git_helpers_use_injected_runner(monkeypatch: Any) -> None:
    calls: list[list[str]] = []

    def fake_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:1] == ["fetch"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:1] == ["for-each-ref"]:
            return subprocess.CompletedProcess(args, 0, f"origin/{STALE_NAME} {MERGED_SHA}\n", "")
        if args[:1] == ["ls-remote"]:
            output = f"{MERGED_SHA}\trefs/heads/{STALE_NAME}\n"
            return subprocess.CompletedProcess(args, 0, output, "")
        if args[:1] == ["merge-base"]:
            return subprocess.CompletedProcess(args, 0, "abc\n", "")
        if args[:1] == ["rev-list"]:
            return subprocess.CompletedProcess(args, 0, "0\n", "")
        return subprocess.CompletedProcess(args, 1, "", "fail")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", fake_git)
    assert git_list_remote_branches() == [{"name": STALE_NAME, "sha": MERGED_SHA}]
    assert git_unique_commit_count(MERGED_SHA) == 0
    assert git_delete_ref(f"origin/{STALE_NAME}", MERGED_SHA) is False
    assert ["fetch", "--prune", "origin"] in calls
    assert ["ls-remote", "--heads", "origin", f"refs/heads/{STALE_NAME}"] in calls

    kwargs = default_scan_kwargs()
    assert kwargs["delete_branch_on_merge_enabled"]() is True


def test_git_unique_unrelated_and_bad_count(monkeypatch: Any) -> None:
    def fail_merge(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:1] == ["merge-base"]:
            return subprocess.CompletedProcess(args, 1, "", "unrelated")
        return subprocess.CompletedProcess(args, 0, "0\n", "")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", fail_merge)
    assert git_unique_commit_count("deadbeef") is None

    def bad_int(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:1] == ["rev-list"]:
            return subprocess.CompletedProcess(args, 0, "nope\n", "")
        return subprocess.CompletedProcess(args, 0, "ok\n", "")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", bad_int)
    assert git_unique_commit_count(MERGED_SHA) is None

    def fail_rev(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:1] == ["rev-list"]:
            return subprocess.CompletedProcess(args, 1, "", "err")
        return subprocess.CompletedProcess(args, 0, "ok\n", "")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", fail_rev)
    assert git_unique_commit_count(MERGED_SHA) is None

    def empty_count(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:1] == ["rev-list"]:
            return subprocess.CompletedProcess(args, 0, "\n", "")
        return subprocess.CompletedProcess(args, 0, "ok\n", "")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", empty_count)
    assert git_unique_commit_count(MERGED_SHA) == 0


def test_git_open_pr_heads_parses_and_swallows(monkeypatch: Any) -> None:
    def ok_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert "--limit" in cmd and "10000" in cmd
        return subprocess.CompletedProcess(
            cmd, 0, json.dumps([{"headRefName": "origin/feat/open"}]), ""
        )

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", ok_run)
    assert git_open_pr_heads() == {"feat/open"}

    many = [{"headRefName": f"feat/open-{index}"} for index in range(45)]

    def many_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert "--limit" in cmd and "10000" in cmd
        return subprocess.CompletedProcess(cmd, 0, json.dumps(many), "")

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", many_run)
    assert git_open_pr_heads() == {f"feat/open-{index}" for index in range(45)}

    def bad_json(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "{", "")

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", bad_json)
    assert git_open_pr_heads() == set()

    def fail(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "err")

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", fail)
    assert git_open_pr_heads() == set()

    def obj_payload(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"headRefName": "x"}), "")

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", obj_payload)
    assert git_open_pr_heads() == set()

    def skip_rows(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, json.dumps([{"n": 1}, "x"]), "")

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", skip_rows)
    assert git_open_pr_heads() == set()


def test_git_list_and_delete_failure(monkeypatch: Any) -> None:
    def fail(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "nope")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", fail)
    assert git_list_remote_branches() == []
    try:
        git_delete_ref("stale", MERGED_SHA)
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_scan_skips_head_and_empty_names() -> None:
    receipts = scan(
        list_remote_branches=lambda: [
            {"name": "HEAD", "sha": MERGED_SHA},
            {"name": "origin/", "sha": MERGED_SHA},
            {"name": STALE_NAME, "sha": MERGED_SHA},
        ],
        unique_commit_count=_counts({MERGED_SHA: 0}),
        open_pr_heads=lambda: set(),
    )
    names = {item["name"] for item in receipts}
    assert STALE_NAME in names
    assert "HEAD" not in names
    assert "" not in names


def test_scan_never_would_delete_protected_base_or_origin() -> None:
    assert is_protected_ref("main") is True
    assert is_protected_ref("origin/main") is True
    assert is_protected_ref("origin") is True
    assert is_protected_ref("master") is True
    deleted: list[str] = []
    receipts = _scan(
        [
            {"name": "main", "sha": MERGED_SHA},
            {"name": "origin", "sha": MERGED_SHA},
            {"name": "origin/main", "sha": MERGED_SHA},
            {"name": STALE_NAME, "sha": MERGED_SHA},
        ],
        {MERGED_SHA: 0},
        apply=True,
        delete_ref=_record_delete(deleted),
    )
    names = {item["name"] for item in receipts}
    assert "main" not in names
    assert "origin" not in names
    assert STALE_NAME in names
    assert deleted == [STALE_NAME]


def test_git_delete_ref_refuses_protected_names() -> None:
    try:
        git_delete_ref("main", MERGED_SHA)
    except RuntimeError as exc:
        assert "protected" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    try:
        git_delete_ref("origin", MERGED_SHA)
    except RuntimeError as exc:
        assert "protected" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_dry_run_cli_without_delete_ref_never_deletes() -> None:
    buf = io.StringIO()
    rc = main(
        ["--dry-run"],
        list_remote_branches=lambda: [{"name": STALE_NAME, "sha": MERGED_SHA}],
        unique_commit_count=_counts({MERGED_SHA: 0}),
        open_pr_heads=lambda: set(),
        stdout=buf,
    )
    assert rc == 0
    assert "would-delete" in buf.getvalue()


def test_run_git_invokes_subprocess(monkeypatch: Any) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.setattr("kater.branch_lifecycle.subprocess.run", fake_run)
    completed = _run_git(["status", "--porcelain"])
    assert completed.stdout == "ok"
    assert seen == [["git", "status", "--porcelain"]]


def test_apply_cli_without_injected_delete_uses_git_helper(monkeypatch: Any) -> None:
    deleted: list[str] = []

    def fake_delete(name: str, expected_sha: str) -> bool:
        assert expected_sha == MERGED_SHA
        deleted.append(name)
        return True

    monkeypatch.setattr("kater.branch_lifecycle.git_delete_ref", fake_delete)
    buf = io.StringIO()
    main(
        ["--apply"],
        list_remote_branches=lambda: [{"name": STALE_NAME, "sha": MERGED_SHA}],
        unique_commit_count=_counts({MERGED_SHA: 0}),
        open_pr_heads=lambda: set(),
        stdout=buf,
    )
    assert deleted == [STALE_NAME]


def test_git_delete_ref_rejects_remote_tip_change(monkeypatch: Any) -> None:
    calls: list[list[str]] = []

    def fake_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:1] == ["ls-remote"]:
            output = f"{UNIQUE_SHA}\trefs/heads/{STALE_NAME}\n"
            return subprocess.CompletedProcess(args, 0, output, "")
        return subprocess.CompletedProcess(args, 1, "", "unexpected")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", fake_git)
    with pytest.raises(RuntimeError, match="expected"):
        git_delete_ref(STALE_NAME, MERGED_SHA)
    assert not any(args[:1] == ["push"] for args in calls)


def test_default_delete_retains_when_atomic_compare_delete_is_unavailable(monkeypatch: Any) -> None:
    def fake_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:1] == ["ls-remote"]:
            output = f"{MERGED_SHA}\trefs/heads/{STALE_NAME}\n"
            return subprocess.CompletedProcess(args, 0, output, "")
        return subprocess.CompletedProcess(args, 1, "", "unexpected")

    monkeypatch.setattr("kater.branch_lifecycle._run_git", fake_git)
    receipts = _scan(
        [{"name": STALE_NAME, "sha": MERGED_SHA}],
        {MERGED_SHA: 0},
        apply=True,
        delete_ref=git_delete_ref,
    )
    item = _by_name(receipts)[STALE_NAME]
    assert item["action"] == "retained"
    assert "compare-and-delete unavailable" in item["reason"]
