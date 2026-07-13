from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from kater.pr_control import (
    REASON_BASE_PROTECTED as BASE_PROTECTED,
)
from kater.pr_control import (
    REASON_DRAFT as DRAFT,
)
from kater.pr_control import (
    REASON_HEAD_STALE as HEAD_STALE,
)
from kater.pr_control import (
    REASON_MERGE_CONFLICT as MERGE_CONFLICT,
)
from kater.pr_control import (
    REASON_NO_REVIEWS as NO_REVIEWS,
)
from kater.pr_control import (
    REASON_OVERLAPPING_PR as OVERLAPPING_PR,
)
from kater.pr_control import (
    REASON_PENDING_CHECKS as PENDING_CHECKS,
)
from kater.pr_control import (
    REASON_UNRESOLVED_THREAD as UNRESOLVED_THREAD,
)
from kater.pr_control import (
    VERDICT_BLOCK as BLOCK,
)
from kater.pr_control import (
    VERDICT_PASS as PASS,
)
from kater.pr_control import (
    GatePolicy,
    GitHubPRClient,
    evaluate_gate,
    gate_for_pr,
    load_gate_policy,
    pr_gate_tool,
    pr_list_tool,
    pr_policy_tool,
    pr_status_tool,
)


def _pr(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "number": 42,
        "title": "demo pr",
        "url": "https://github.com/o/r/pull/42",
        "headRefName": "feat/x",
        "baseRefName": "main",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [],
        "reviewThreads": [],
        "commits": [{"oid": "abc123"}],
        "baseRefOid": "base000",
        "headRefOid": "head000",
    }
    base.update(overrides)
    return base


def test_gate_clean_pr_passes() -> None:
    res = evaluate_gate(
        pr_number=1,
        head_sha="h",
        base_sha="b",
        mergeable="MERGEABLE",
        draft=False,
        open_threads=0,
        pending_checks=0,
        approving_reviews=1,
        base_protected=False,
        overlapping_open=0,
    )
    assert res.verdict == PASS
    assert res.reasons == []


def test_gate_flags_each_reason() -> None:
    cases = [
        (dict(draft=True), DRAFT),
        (dict(open_threads=2), UNRESOLVED_THREAD),
        (dict(mergeable="CONFLICTING"), MERGE_CONFLICT),
        (dict(mergeable="UNKNOWN"), HEAD_STALE),
        (dict(overlapping_open=1), OVERLAPPING_PR),
        (dict(pending_checks=3), PENDING_CHECKS),
        (dict(approving_reviews=0), NO_REVIEWS),
        (dict(base_protected=True), BASE_PROTECTED),
    ]
    strict = GatePolicy(
        require_approvals=1,
        block_drafts=True,
        block_base_protected=True,
        allow_overlapping_prs=False,
        allow_pending_checks=False,
        allow_unresolved_threads=False,
    )
    for overrides, reason in cases:
        kwargs = dict(
            pr_number=1,
            head_sha="h",
            base_sha="b",
            mergeable="MERGEABLE",
            draft=False,
            open_threads=0,
            pending_checks=0,
            approving_reviews=1,
            base_protected=False,
            overlapping_open=0,
            policy=strict,
        )
        kwargs.update(overrides)
        res = evaluate_gate(**kwargs)
        assert reason in res.reasons
        assert res.verdict == BLOCK


def test_gate_block_overrides_warn() -> None:
    res = evaluate_gate(
        pr_number=1,
        head_sha="h",
        base_sha="b",
        mergeable="CONFLICTING",
        draft=False,
        open_threads=0,
        pending_checks=5,
        approving_reviews=0,
        base_protected=True,
        overlapping_open=0,
    )
    assert res.verdict == BLOCK
    assert MERGE_CONFLICT in res.reasons
    # Blocking reasons (conflict, missing approval, protected base) dominate
    # the non-blocking pending-checks reason under the default policy.
    assert NO_REVIEWS in res.reasons
    assert BASE_PROTECTED in res.reasons


def test_gate_details_recorded() -> None:
    res = evaluate_gate(
        pr_number=7,
        head_sha="headsha",
        base_sha="basesha",
        mergeable="MERGEABLE",
        draft=False,
        open_threads=1,
        pending_checks=0,
        approving_reviews=2,
        base_protected=False,
        overlapping_open=0,
    )
    assert res.details["pr_number"] == 7
    assert res.details["head_sha"] == "headsha"
    assert res.details["open_threads"] == 1


def test_client_pr_list_parses_gh_output() -> None:
    captured: dict[str, Any] = {}

    def fake_runner(args: list[str]) -> Any:
        captured["args"] = args
        payload = [_pr(), _pr(number=43, reviewDecision="REVIEW_REQUIRED")]
        return SimpleNamespace(returncode=0, stdout=__import__("json").dumps(payload), stderr="")

    client = GitHubPRClient(runner=fake_runner)
    rows = client.list_pull_requests(limit=10)
    assert len(rows) == 2
    assert "--limit" in captured["args"]
    assert "10" in captured["args"]


def test_client_pr_view_passes_number() -> None:
    captured: dict[str, Any] = {}

    def fake_runner(args: list[str]) -> Any:
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout=__import__("json").dumps(_pr()), stderr="")

    client = GitHubPRClient(runner=fake_runner)
    pr = client.pull_request(42)
    assert pr["number"] == 42
    assert str(42) in captured["args"]


def test_client_api_error_raises() -> None:
    def fake_runner(args: list[str]) -> Any:
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    client = GitHubPRClient(runner=fake_runner)
    try:
        client.list_pull_requests()
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_summarize_pr_aggregates_threads_and_checks() -> None:
    threads = [{"isResolved": True}, {"isResolved": False}, {"isResolved": False}]
    checks = [
        {"status": "COMPLETED", "conclusion": "SUCCESS"},
        {"status": "IN_PROGRESS"},
        {"conclusion": "ACTION_REQUIRED"},
    ]
    pr = _pr(reviewThreads=threads, statusCheckRollup=checks)
    from kater.pr_control import _summarize_pr

    summ = _summarize_pr(pr)
    assert summ["open_threads"] == 2
    assert summ["pending_checks"] == 2
    assert summ["approving_reviews"] == 1
    assert summ["head_sha"] == "head000"
    assert summ["base_sha"] == "base000"


def test_gate_for_pr_blocks_on_unresolved_threads() -> None:
    def fake_runner(args: list[str]) -> Any:
        return SimpleNamespace(returncode=0, stdout=__import__("json").dumps(_pr()), stderr="")

    client = GitHubPRClient(runner=fake_runner)
    pr = _pr(reviewThreads=[{"isResolved": False}])
    res = gate_for_pr(client, pr)
    assert res.verdict == BLOCK
    assert UNRESOLVED_THREAD in res.reasons


def test_tools_read_only_no_subprocess(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> Any:
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=__import__("json").dumps([_pr()]), stderr="")

    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.list_pull_requests",
        lambda self, **kw: [_pr()],
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(number=number),
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.is_base_protected",
        lambda self, base: False,
    )

    listing = pr_list_tool(state="open", limit=5)
    assert listing["count"] == 1
    status = pr_status_tool(42)
    assert status["gate"]["verdict"] == PASS
    gate = pr_gate_tool(42, expected_head_sha="head000")
    assert gate["verdict"] == PASS
    assert gate["details"]["head_sha_matches"] is True
    gate_mismatch = pr_gate_tool(42, expected_head_sha="wrong")
    assert gate_mismatch["details"]["head_sha_matches"] is False
    assert not calls  # no subprocess executed during the read path


def test_policy_defaults_block_drafts_and_require_approval() -> None:
    policy = GatePolicy()
    assert policy.block_drafts is True
    assert policy.require_approvals == 1
    assert policy.block_base_protected is True
    res = evaluate_gate(
        pr_number=1,
        head_sha="h",
        base_sha="b",
        mergeable="MERGEABLE",
        draft=True,
        open_threads=0,
        pending_checks=0,
        approving_reviews=0,
        base_protected=False,
        overlapping_open=0,
        policy=policy,
    )
    assert DRAFT in res.reasons
    assert NO_REVIEWS in res.reasons
    assert res.verdict == BLOCK


def test_policy_can_relax_draft_and_pending_checks() -> None:
    policy = GatePolicy(block_drafts=False, allow_pending_checks=True)
    res = evaluate_gate(
        pr_number=1,
        head_sha="h",
        base_sha="b",
        mergeable="MERGEABLE",
        draft=True,
        open_threads=0,
        pending_checks=2,
        approving_reviews=1,
        base_protected=False,
        overlapping_open=0,
        policy=policy,
    )
    assert DRAFT not in res.reasons
    assert PENDING_CHECKS not in res.reasons
    assert res.verdict == PASS


def test_policy_load_from_dict_ignores_unknown_keys() -> None:
    policy = GatePolicy.from_dict(
        {"require_approvals": 2, "unknown": "drop-me"}
    )
    assert policy.require_approvals == 2
    assert policy.block_drafts is True


def test_load_gate_policy_absent_returns_default(tmp_path) -> None:
    policy = load_gate_policy(path=str(tmp_path / "missing.json"))
    assert isinstance(policy, GatePolicy)
    assert policy.require_approvals == 1


def test_load_gate_policy_reads_file(tmp_path) -> None:
    path = tmp_path / "gate-policy.json"
    path.write_text('{"require_approvals": 3, "block_drafts": false}', encoding="utf-8")
    policy = load_gate_policy(path=str(path))
    assert policy.require_approvals == 3
    assert policy.block_drafts is False


def test_pr_policy_tool_returns_policy() -> None:
    result = pr_policy_tool()
    assert "policy" in result
    assert result["policy"]["require_approvals"] == 1
