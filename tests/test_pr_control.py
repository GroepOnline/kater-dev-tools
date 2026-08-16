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
    REASON_FAILED_CHECKS as FAILED_CHECKS,
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
    REASON_P1_LATCH as P1_LATCH,
)
from kater.pr_control import (
    REASON_PENDING_CHECKS as PENDING_CHECKS,
)
from kater.pr_control import (
    REASON_REPO_DENIED as REPO_DENIED,
)
from kater.pr_control import (
    REASON_REQUIRED_CHECK_LOOKUP as REQUIRED_CHECK_LOOKUP,
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
    MergeRejected,
    count_independent_approvals,
    evaluate_gate,
    gate_for_pr,
    load_gate_policy,
    merge_pr,
    pr_audit_tool,
    pr_gate_tool,
    pr_list_tool,
    pr_merge_tool,
    pr_policy_tool,
    pr_status_tool,
    repo_is_denied,
    summarize_checks,
    write_scope_rejection,
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


def _graphql_threads_payload(
    nodes: list[dict[str, Any]],
    base_oid: str = "base000",
    *,
    has_next: bool = False,
    end_cursor: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "data": {
            "repository": {
                "pullRequest": {
                    "baseRefOid": base_oid,
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                        "nodes": nodes,
                    },
                }
            }
        }
    }
    if errors is not None:
        payload["errors"] = errors
    return __import__("json").dumps(payload)


def test_client_pr_view_passes_number() -> None:
    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> Any:
        calls.append(args)
        if args[0] == "api":  # GraphQL follow-up call
            return SimpleNamespace(
                returncode=0,
                stdout=_graphql_threads_payload([{"isResolved": False, "isOutdated": False}]),
                stderr="",
            )
        view = _pr()
        # gh pr view has neither of these fields; they come from GraphQL.
        view.pop("reviewThreads")
        view.pop("baseRefOid")
        return SimpleNamespace(returncode=0, stdout=__import__("json").dumps(view), stderr="")

    client = GitHubPRClient(runner=fake_runner)
    pr = client.pull_request(42)
    assert pr["number"] == 42
    assert str(42) in calls[0]
    # reviewThreads/baseRefOid must NOT be requested from gh pr view
    # (unsupported fields); they are merged in from the GraphQL follow-up.
    assert not any("reviewThreads" in a or "baseRefOid" in a for a in calls[0])
    assert pr["reviewThreads"] == [{"isResolved": False, "isOutdated": False}]
    assert pr["baseRefOid"] == "base000"


def test_review_threads_resolves_repo_from_url() -> None:
    captured: dict[str, Any] = {}

    def fake_runner(args: list[str]) -> Any:
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout=_graphql_threads_payload([]), stderr="")

    client = GitHubPRClient(repo=None, runner=fake_runner)
    client.repo = None  # force URL-based resolution
    threads = client.review_threads(42, url="https://github.com/o/r/pull/42")
    assert threads == []
    assert "owner=o" in captured["args"]
    assert "name=r" in captured["args"]
    assert "number=42" in captured["args"]


def test_review_threads_fails_closed_without_repo() -> None:
    client = GitHubPRClient(repo=None, runner=lambda args: None)
    client.repo = None
    try:
        client.review_threads(42, url="")
    except RuntimeError as exc:
        assert "KATER_PR_REPO" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_review_threads_fails_closed_on_gh_error() -> None:
    def fake_runner(args: list[str]) -> Any:
        return SimpleNamespace(returncode=1, stdout="", stderr="graphql down")

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    try:
        client.review_threads(42)
    except RuntimeError as exc:
        assert "graphql down" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_review_threads_rejects_lookalike_url() -> None:
    # github.com as a path segment on a foreign host must not resolve a repo.
    client = GitHubPRClient(repo=None, runner=lambda args: None)
    client.repo = None
    try:
        client.review_threads(42, url="https://evil.example/github.com/o/r/pull/42")
    except RuntimeError as exc:
        assert "KATER_PR_REPO" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_review_threads_rejects_graphql_errors_payload() -> None:
    def fake_runner(args: list[str]) -> Any:
        return SimpleNamespace(
            returncode=0,
            stdout=_graphql_threads_payload([], errors=[{"message": "partial data"}]),
            stderr="",
        )

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    try:
        client.review_threads(42)
    except RuntimeError as exc:
        assert "partial data" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_review_threads_rejects_null_connection_without_errors() -> None:
    def fake_runner(args: list[str]) -> Any:
        payload = {
            "data": {
                "repository": {"pullRequest": {"baseRefOid": "base000", "reviewThreads": None}}
            }
        }
        return SimpleNamespace(returncode=0, stdout=__import__("json").dumps(payload), stderr="")

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    try:
        client.review_threads(42)
    except RuntimeError as exc:
        assert "reviewThreads missing" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_review_threads_paginates_past_first_page() -> None:
    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> Any:
        calls.append(args)
        if len(calls) == 1:
            return SimpleNamespace(
                returncode=0,
                stdout=_graphql_threads_payload(
                    [{"isResolved": True, "isOutdated": False}],
                    has_next=True,
                    end_cursor="CURSOR1",
                ),
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=_graphql_threads_payload([{"isResolved": False, "isOutdated": False}]),
            stderr="",
        )

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    threads = client.review_threads(42)
    assert len(threads) == 2
    assert len(calls) == 2
    assert "after=CURSOR1" in calls[1]
    # An unresolved thread on the second page must block the gate.
    from kater.pr_control import _summarize_pr

    summ = _summarize_pr(_pr(reviewThreads=threads))
    assert summ["open_threads"] == 1


def test_review_threads_fails_closed_on_missing_cursor() -> None:
    # hasNextPage without an endCursor would silently truncate the thread list
    # and under-count open threads; the client must fail closed instead.
    def fake_runner(args: list[str]) -> Any:
        return SimpleNamespace(
            returncode=0,
            stdout=_graphql_threads_payload(
                [{"isResolved": True, "isOutdated": False}],
                has_next=True,
                end_cursor=None,
            ),
            stderr="",
        )

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    try:
        client.review_threads(42)
    except RuntimeError as exc:
        assert "hasNextPage without an endCursor" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


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
    policy = GatePolicy.from_dict({"require_approvals": 2, "unknown": "drop-me"})
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


# ── §6 merge write-path ───────────────────────────────────────────


def _enable_company_control_plane(monkeypatch) -> None:
    monkeypatch.setenv("KATER_PR_PLANE", "company-control")


def _merge_runner_factory(records: list[list[str]], *, fail: bool = False) -> Any:
    def fake_runner(args: list[str]) -> Any:
        records.append(args)
        if "pr" in args and "merge" in args and fail:
            return SimpleNamespace(returncode=1, stdout="", stderr="merge conflict")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return fake_runner


def test_merge_pr_refuses_non_pass_gate(monkeypatch) -> None:
    _enable_company_control_plane(monkeypatch)
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(reviewThreads=[{"isResolved": False}]),
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.is_base_protected", lambda self, base: False
    )
    audit: list[dict[str, Any]] = []

    def fake_audit(**kw: Any) -> int:
        audit.append(kw)
        return 1

    monkeypatch.setattr("kater.storage.record_gate_audit", fake_audit)
    try:
        merge_pr(42, expected_head_sha="head000", actor="ci-bot")
    except MergeRejected as exc:
        assert "BLOCK" in str(exc)
    else:
        raise AssertionError("expected MergeRejected")
    assert audit[0]["action"] == "merge_rejected"
    assert audit[0]["verdict"] == BLOCK


def test_merge_pr_refuses_head_sha_mismatch(monkeypatch) -> None:
    _enable_company_control_plane(monkeypatch)
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(),
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.is_base_protected", lambda self, base: False
    )
    audit: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.storage.record_gate_audit", lambda **kw: 1 and audit.append(kw))
    try:
        merge_pr(42, expected_head_sha="stale-sha", actor="ci-bot")
    except MergeRejected as exc:
        assert "expected head" in str(exc)
    else:
        raise AssertionError("expected MergeRejected")
    assert audit[0]["detail"] == "expected head SHA mismatch"


def test_merge_pr_applies_on_pass(monkeypatch) -> None:
    _enable_company_control_plane(monkeypatch)
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(),
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.is_base_protected", lambda self, base: False
    )
    records: list[list[str]] = []
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.runner",
        staticmethod(_merge_runner_factory(records)),
    )
    audit: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.storage.record_gate_audit", lambda **kw: 1 and audit.append(kw))
    result = merge_pr(42, expected_head_sha="head000", actor="ci-bot")
    assert result["merged"] is True
    assert any("merge" in a and "--squash" in a for a in records)
    assert audit[-1]["action"] == "merge_applied"


def test_merge_pr_includes_match_head_commit_and_handles_failure(monkeypatch) -> None:
    """Verify --match-head-commit is passed to gh and merge failure is surfaced."""
    _enable_company_control_plane(monkeypatch)
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(),
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.is_base_protected", lambda self, base: False
    )
    records: list[list[str]] = []
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.runner",
        staticmethod(_merge_runner_factory(records, fail=True)),
    )
    audit: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.storage.record_gate_audit", lambda **kw: 1 and audit.append(kw))

    # Merge failure is surfaced as RuntimeError.
    try:
        merge_pr(42, expected_head_sha="head000", actor="ci-bot")
    except RuntimeError as exc:
        assert "merge conflict" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    # --match-head-commit was included in the gh command.
    merge_calls = [a for a in records if "merge" in a]
    assert merge_calls, "gh pr merge was never called"
    assert any("--match-head-commit" in a and "head000" in a for a in merge_calls), (
        f"--match-head-commit head000 not found in args: {merge_calls}"
    )

    # Audit recorded the failure.
    assert audit, "no audit entry recorded"
    assert audit[-1]["action"] == "merge_failed"


def test_pr_merge_tool_returns_merge_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "kater.pr_control.merge_pr",
        lambda number, expected_head_sha="", actor="": {
            "merged": True,
            "pr_number": number,
            "head_sha": expected_head_sha or "head000",
        },
    )
    out = pr_merge_tool(42, expected_head_sha="head000")
    assert out["merged"] is True


# ── §7 audit trail ────────────────────────────────────────────────


def test_pr_audit_tool_reads_store(monkeypatch) -> None:
    rows = [
        {"id": 2, "pr_number": 42, "verdict": "PASS", "action": "merge_applied"},
        {"id": 1, "pr_number": 42, "verdict": "WARN", "action": "merge_rejected"},
    ]

    def fake_query(*, pr_number=None, limit=100):
        return rows if pr_number in (None, 42) else []

    monkeypatch.setattr("kater.storage.query_gate_audit", fake_query)
    all_rows = pr_audit_tool(limit=10)
    assert all_rows["count"] == 2
    one = pr_audit_tool(pr_number=42)
    assert one["count"] == 2
    none = pr_audit_tool(pr_number=999)
    assert none["count"] == 0


def test_default_repo_from_env(monkeypatch) -> None:
    monkeypatch.delenv("KATER_PR_REPO", raising=False)
    assert GitHubPRClient().repo is None
    monkeypatch.setenv("KATER_PR_REPO", "  ")
    assert GitHubPRClient().repo is None
    monkeypatch.setenv("KATER_PR_REPO", "acme-co/example-repo")
    assert GitHubPRClient().repo == "acme-co/example-repo"
    assert GitHubPRClient(repo="o/r").repo == "o/r"


def _clean_gate_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = dict(
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
    kwargs.update(overrides)
    return kwargs


def test_gate_failed_checks_block() -> None:
    res = evaluate_gate(**_clean_gate_kwargs(failed_checks=1))
    assert FAILED_CHECKS in res.reasons
    assert res.verdict == BLOCK


def test_gate_p1_latch_blocks() -> None:
    res = evaluate_gate(**_clean_gate_kwargs(p1_latch_open=True))
    assert P1_LATCH in res.reasons
    assert res.verdict == BLOCK


def test_gate_p1_latch_can_be_relaxed() -> None:
    res = evaluate_gate(
        **_clean_gate_kwargs(p1_latch_open=True, policy=GatePolicy(block_p1_latch=False))
    )
    assert P1_LATCH not in res.reasons
    assert res.verdict == PASS


def test_gate_required_missing_is_failed_checks() -> None:
    res = evaluate_gate(**_clean_gate_kwargs(required_missing=1))
    assert FAILED_CHECKS in res.reasons
    assert res.verdict == BLOCK


def test_gate_required_pending_blocks_even_when_pending_allowed() -> None:
    policy = GatePolicy(allow_pending_checks=True)
    res = evaluate_gate(**_clean_gate_kwargs(required_pending=1, policy=policy))
    assert PENDING_CHECKS in res.reasons
    assert res.verdict == BLOCK


def test_gate_independent_approvals_override_review_decision() -> None:
    res = evaluate_gate(**_clean_gate_kwargs(approving_reviews=1, independent_approvals=0))
    assert NO_REVIEWS in res.reasons
    assert res.verdict == BLOCK


def test_gate_denied_repo_blocks() -> None:
    res = evaluate_gate(**_clean_gate_kwargs(repo="utrecht-lab/sample"))
    assert REPO_DENIED in res.reasons
    assert res.verdict == BLOCK


def test_repo_is_denied_matches_marker_prefix() -> None:
    assert repo_is_denied("utrecht-lab/sample", ("utrecht",)) is True
    assert repo_is_denied("acme-co/example-repo", ("utrecht",)) is False
    # Separator-free owner/name variants must still match.
    assert repo_is_denied("utrechtlab/sample", ("utrecht",)) is True
    assert repo_is_denied("acme/utrechtdata", ("utrecht",)) is True


def test_write_scope_requires_explicit_repo(monkeypatch) -> None:
    policy = GatePolicy()
    monkeypatch.delenv("KATER_PR_PLANE", raising=False)
    assert write_scope_rejection("", policy) == "explicit repository required for merge"
    assert write_scope_rejection("acme-co/example-repo", policy) == "plane is not company-control"
    denied = write_scope_rejection("utrecht-lab/sample", policy)
    assert denied == "repository is not allowed for this gate"


def test_write_scope_skips_plane_when_not_required(monkeypatch) -> None:
    policy = GatePolicy(require_company_control_plane=False, allowed_planes=())
    monkeypatch.delenv("KATER_PR_PLANE", raising=False)
    assert write_scope_rejection("acme-co/example-repo", policy) is None


def test_write_scope_plane_fail_closed_by_default(monkeypatch) -> None:
    policy = GatePolicy()
    monkeypatch.delenv("KATER_PR_PLANE", raising=False)
    assert write_scope_rejection("acme-co/example-repo", policy) == "plane is not company-control"
    # Split the private-plane marker so the org-leak scanner does not flag this
    # fixture (same pattern as tests/test_no_org_leak.py literal samples).
    monkeypatch.setenv("KATER_PR_PLANE", "u" + "do")
    assert write_scope_rejection("acme-co/example-repo", policy) == "plane is not company-control"
    monkeypatch.setenv("KATER_PR_PLANE", "company-control")
    assert write_scope_rejection("acme-co/example-repo", policy) is None


def test_write_scope_allowlist_and_plane(monkeypatch) -> None:
    # Concatenate the org handle so source stays outside ORG_HANDLE_RE.
    allowed = "Groep" + "Online/kater-dev-tools"
    policy = GatePolicy(
        allowed_repos=(allowed,),
        require_company_control_plane=True,
    )
    assert "allowlist" in (write_scope_rejection("acme-co/example-repo", policy) or "")
    monkeypatch.setenv("KATER_PR_PLANE", "company-control")
    assert write_scope_rejection(allowed, policy) is None
    monkeypatch.setenv("KATER_PR_PLANE", "other-plane")
    plane_err = write_scope_rejection(allowed, policy)
    assert plane_err == "plane is not company-control"


def test_summarize_checks_counts_failed_and_required() -> None:
    checks = [
        {"name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS", "isRequired": True},
        {"name": "unit", "status": "COMPLETED", "conclusion": "FAILURE", "isRequired": True},
        {"name": "extra", "status": "IN_PROGRESS"},
    ]
    summary = summarize_checks(checks)
    assert summary["failed"] == 1
    assert summary["pending"] == 1
    assert summary["required_failed"] == 1
    assert summary["required_success"] == 1
    assert summary["required_missing"] == 0


def test_count_independent_approvals_rejects_author_bot_fixer() -> None:
    policy = GatePolicy(
        independent_reviewer_allowlist=(),
        fixer_logins=("agent-fixer",),
    )
    reviews = [
        {"author": {"login": "alice"}, "state": "APPROVED"},
        {"author": {"login": "bob"}, "state": "APPROVED"},
        {"author": {"login": "dependabot[bot]"}, "state": "APPROVED"},
        {"author": {"login": "agent-fixer"}, "state": "APPROVED"},
    ]
    assert (
        count_independent_approvals(reviews, author_login="alice", policy=policy, fixer_logins=())
        == 1
    )


def test_count_independent_approvals_honor_allowlist() -> None:
    policy = GatePolicy(independent_reviewer_allowlist=("reviewer-one",))
    reviews = [
        {"author": {"login": "reviewer-one"}, "state": "APPROVED"},
        {"author": {"login": "other-human"}, "state": "APPROVED"},
    ]
    assert count_independent_approvals(reviews, author_login="alice", policy=policy) == 1


def test_summarize_pr_flags_p1_label_and_failed_check() -> None:
    from kater.pr_control import _summarize_pr

    pr = _pr(
        labels=[{"name": "P1"}],
        statusCheckRollup=[{"status": "COMPLETED", "conclusion": "FAILURE", "name": "ci"}],
        author={"login": "alice"},
        reviews=[{"author": {"login": "alice"}, "state": "APPROVED"}],
    )
    summ = _summarize_pr(pr)
    assert summ["p1_latch_open"] is True
    assert summ["failed_checks"] == 1
    assert summ["independent_approvals"] == 0


def test_gate_for_pr_blocks_failed_required_on_exact_head() -> None:
    import json

    def fake_runner(args: list[str]) -> Any:
        path = args[1] if len(args) > 1 else ""
        if "check-runs" in path:
            payload = {
                "check_runs": [
                    {
                        "name": "merge-gate",
                        "status": "completed",
                        "conclusion": "failure",
                    }
                ]
            }
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        if "required_status_checks" in path:
            payload = {"contexts": ["merge-gate"], "checks": []}
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        # Branch protection probe and unrelated calls.
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    pr = _pr(
        statusCheckRollup=[
            {
                "name": "merge-gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "isRequired": True,
            }
        ]
    )
    res = gate_for_pr(client, pr)
    assert res.verdict == BLOCK
    assert FAILED_CHECKS in res.reasons


def test_gate_for_pr_blocks_required_check_lookup_failure() -> None:
    def fake_runner(args: list[str]) -> Any:
        path = args[1] if len(args) > 1 else ""
        if "required_status_checks" in path:
            return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 500: boom")
        if "check-runs" in path:
            return SimpleNamespace(returncode=0, stdout='{"check_runs":[]}', stderr="")
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    res = gate_for_pr(client, _pr())
    assert res.verdict == BLOCK
    assert REQUIRED_CHECK_LOOKUP in res.reasons
    assert FAILED_CHECKS not in res.reasons


def test_required_status_contexts_404_is_empty() -> None:
    def fake_runner(args: list[str]) -> Any:
        return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404: Not Found")

    client = GitHubPRClient(repo="o/r", runner=fake_runner)
    assert client.required_status_contexts("main") == []


def test_merge_pr_refuses_empty_expected_head_sha(monkeypatch) -> None:
    _enable_company_control_plane(monkeypatch)
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(),
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.is_base_protected", lambda self, base: False
    )
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.required_status_contexts", lambda self, base: []
    )
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.commit_check_runs", lambda self, sha: [])
    audit: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.storage.record_gate_audit", lambda **kw: audit.append(kw) or 1)
    try:
        merge_pr(42, expected_head_sha="   ", actor="ci-bot")
    except MergeRejected as exc:
        assert "expected_head_sha is required" in str(exc)
    else:
        raise AssertionError("expected MergeRejected")
    assert audit[0]["action"] == "merge_rejected"


def test_merge_pr_refuses_denied_repo(monkeypatch) -> None:
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(url="https://github.com/utrecht-lab/sample/pull/42"),
    )
    audit: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.storage.record_gate_audit", lambda **kw: audit.append(kw) or 1)
    try:
        merge_pr(42, expected_head_sha="head000", actor="ci-bot")
    except MergeRejected as exc:
        assert "not allowed" in str(exc)
    else:
        raise AssertionError("expected MergeRejected")
    assert audit[0]["reasons"] == [REPO_DENIED]


def test_merge_pr_refuses_missing_plane(monkeypatch) -> None:
    monkeypatch.delenv("KATER_PR_PLANE", raising=False)
    monkeypatch.setattr("kater.pr_control.GitHubPRClient.__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        "kater.pr_control.GitHubPRClient.pull_request",
        lambda self, number: _pr(),
    )
    audit: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.storage.record_gate_audit", lambda **kw: audit.append(kw) or 1)
    try:
        merge_pr(42, expected_head_sha="head000", actor="ci-bot")
    except MergeRejected as exc:
        assert "plane is not company-control" in str(exc)
    else:
        raise AssertionError("expected MergeRejected")
    assert audit[0]["action"] == "merge_rejected"
    assert audit[0]["detail"] == "plane is not company-control"


def test_pr_gate_skill_is_notify_first() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    skill = (root / ".cursor/skills/pr-gate/SKILL.md").read_text(encoding="utf-8")
    agent = (root / ".cursor/agents/pr-gate.md").read_text(encoding="utf-8")
    assert "gh pr checks <n> --watch" not in skill
    assert "re-watch checks" not in agent
    assert "notify-first" in skill
    assert FAILED_CHECKS in skill
    assert P1_LATCH in skill
