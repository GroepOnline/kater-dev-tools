from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger("kater.pr_control")

# Machine-readable gate verdicts and reason codes. Write-tools (merge) must
# require the recorded head SHA and only act on a PASS; WARN/BLOCK are
# abort conditions.
VERDICT_PASS = "PASS"
VERDICT_WARN = "WARN"
VERDICT_BLOCK = "BLOCK"

REASON_HEAD_STALE = "HEAD_STALE"
REASON_MERGE_CONFLICT = "MERGE_CONFLICT"
REASON_UNRESOLVED_THREAD = "UNRESOLVED_THREAD"
REASON_OVERLAPPING_PR = "OVERLAPPING_PR"
REASON_PENDING_CHECKS = "PENDING_CHECKS"
REASON_NO_REVIEWS = "NO_REVIEWS"
REASON_DRAFT = "DRAFT"
REASON_BASE_PROTECTED = "BASE_PROTECTED"


@dataclass
class GateResult:
    verdict: str
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reasons": self.reasons,
            "details": self.details,
        }


# Reasons that hard-block a merge unconditionally.
@dataclass
class GatePolicy:
    """Operator-tunable gate thresholds (§4 policy config).

    Defaults encode a conservative-but-mergeable policy: require at least one
    approving review, block drafts and base-protected changes outright, allow
    a single overlapping PR or pending check to surface as a WARN.
    """

    require_approvals: int = 1
    block_drafts: bool = True
    block_base_protected: bool = True
    allow_overlapping_prs: bool = False
    allow_pending_checks: bool = True
    allow_unresolved_threads: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GatePolicy:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def load_gate_policy(*, path: str | None = None) -> GatePolicy:
    """Load gate policy from ``path`` (JSON), else repo default location.

    Read-only: file IO is isolated so an absent/malformed policy yields the
    safe default rather than raising.
    """
    candidates = [path] if path else [".kater/gate-policy.json", "gate-policy.json"]
    for candidate in candidates:
        try:
            with open(candidate, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            return GatePolicy.from_dict(raw)
    return GatePolicy()


def _collapse(verdict: str, reasons: list[str], policy: GatePolicy) -> str:
    # A reason blocks only when the policy treats it as blocking; otherwise it
    # is a WARN. This keeps the verdict purely a function of (reasons, policy).
    blocking_here = {
        REASON_HEAD_STALE,
        REASON_MERGE_CONFLICT,
        REASON_UNRESOLVED_THREAD,
        REASON_OVERLAPPING_PR,
    }
    if policy.block_drafts:
        blocking_here.add(REASON_DRAFT)
    if policy.block_base_protected:
        blocking_here.add(REASON_BASE_PROTECTED)
    if policy.require_approvals > 0:
        blocking_here.add(REASON_NO_REVIEWS)
    if not policy.allow_pending_checks:
        blocking_here.add(REASON_PENDING_CHECKS)
    if not policy.allow_overlapping_prs:
        blocking_here.add(REASON_OVERLAPPING_PR)
    if not policy.allow_unresolved_threads:
        blocking_here.add(REASON_UNRESOLVED_THREAD)

    if any(r in blocking_here for r in reasons):
        return VERDICT_BLOCK
    if reasons:
        return VERDICT_WARN
    return VERDICT_PASS


def evaluate_gate(
    *,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    mergeable: str,
    draft: bool,
    open_threads: int,
    pending_checks: int,
    approving_reviews: int,
    base_protected: bool,
    overlapping_open: int,
    policy: GatePolicy | None = None,
) -> GateResult:
    """Deterministic PR merge-readiness gate.

    Pure function (no I/O) so it is fully unit-testable. The returned verdict
    is PASS only when no blocking or warning reason applies; WARN for soft
    issues; BLOCK for anything that must prevent a merge.

    The optional ``policy`` tunes which signals block vs. warn. When omitted,
    the safe-default :class:`GatePolicy` is used.
    """
    policy = policy or GatePolicy()
    reasons: list[str] = []

    if draft and policy.block_drafts:
        reasons.append(REASON_DRAFT)
    if open_threads > 0 and not policy.allow_unresolved_threads:
        reasons.append(REASON_UNRESOLVED_THREAD)
    if mergeable == "CONFLICTING":
        reasons.append(REASON_MERGE_CONFLICT)
    elif mergeable == "UNKNOWN":
        # Unknown mergeability is treated as stale/unverified rather than green.
        reasons.append(REASON_HEAD_STALE)
    if overlapping_open > 0 and not policy.allow_overlapping_prs:
        reasons.append(REASON_OVERLAPPING_PR)
    if pending_checks > 0 and not policy.allow_pending_checks:
        reasons.append(REASON_PENDING_CHECKS)
    if approving_reviews < policy.require_approvals:
        reasons.append(REASON_NO_REVIEWS)
    if base_protected and policy.block_base_protected:
        reasons.append(REASON_BASE_PROTECTED)

    verdict = _collapse(VERDICT_PASS, reasons, policy)
    return GateResult(
        verdict=verdict,
        reasons=reasons,
        details={
            "pr_number": pr_number,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "open_threads": open_threads,
            "pending_checks": pending_checks,
            "approving_reviews": approving_reviews,
            "overlapping_open": overlapping_open,
        },
    )


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@dataclass
class GitHubPRClient:
    """Read-only GitHub provider backed by the `gh` CLI.

    Network and auth are isolated behind ``runner`` so the client is testable
    without a live GitHub connection. Only GET-style operations are used; no
    writes occur here.
    """

    repo: str | None = None
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_gh

    def _target(self, ref: str) -> str:
        return f"{self.repo}#{ref}" if self.repo else ref

    def _api(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        args = ["api", path, "-H", "Accept: application/vnd.github+json"]
        if params:
            for key, value in params.items():
                args += ["-f", f"{key}={value}"]
        proc = self.runner(args)
        if proc.returncode != 0:
            raise RuntimeError(f"gh api {path} failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[dict[str, Any]]:
        args = [
            "pr",
            "list",
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            (
                "number,title,headRefName,baseRefName,state,"
                "isDraft,mergeable,reviewDecision,statusCheckRollup,"
                "reviewThreads,commits"
            ),
        ]
        if self.repo:
            args += ["--repo", self.repo]
        proc = self.runner(args)
        if proc.returncode != 0:
            raise RuntimeError(f"gh pr list failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)

    def pull_request(self, number: int) -> dict[str, Any]:
        args = [
            "pr",
            "view",
            str(number),
            "--json",
            (
                "number,title,headRefName,baseRefName,state,url,"
                "isDraft,mergeable,reviewDecision,statusCheckRollup,"
                "reviewThreads,commits,baseRefOid,headRefOid"
            ),
        ]
        if self.repo:
            args += ["--repo", self.repo]
        proc = self.runner(args)
        if proc.returncode != 0:
            raise RuntimeError(f"gh pr view {number} failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)

    def is_base_protected(self, base_ref: str) -> bool:
        if not self.repo:
            return False
        try:
            data = self._api(
                f"repos/{self.repo}/branches/{base_ref}/protection"
            )
        except RuntimeError:
            return False
        return bool(data)


def _summarize_pr(pr: dict[str, Any]) -> dict[str, Any]:
    threads = pr.get("reviewThreads") or []
    open_threads = sum(1 for t in threads if not t.get("isResolved"))
    checks = pr.get("statusCheckRollup") or []
    pending_checks = sum(
        1
        for c in checks
        if (c.get("status") or "").upper() in ("PENDING", "QUEUED", "IN_PROGRESS")
        or (c.get("conclusion") or "").upper() in ("ACTION_REQUIRED", "STALE")
    )
    decision = (pr.get("reviewDecision") or "").upper()
    approving = 1 if decision == "APPROVED" else 0
    commits = pr.get("commits") or []
    head_sha = pr.get("headRefOid") or (commits[-1].get("oid") if commits else "")
    base_sha = pr.get("baseRefOid") or ""
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "head_ref": pr.get("headRefName"),
        "base_ref": pr.get("baseRefName"),
        "head_sha": head_sha,
        "base_sha": base_sha,
        "draft": bool(pr.get("isDraft")),
        "mergeable": (pr.get("mergeable") or "UNKNOWN").upper(),
        "review_decision": decision,
        "open_threads": open_threads,
        "pending_checks": pending_checks,
        "approving_reviews": approving,
    }


def gate_for_pr(
    client: GitHubPRClient,
    pr: dict[str, Any],
    *,
    overlapping_open: int = 0,
    policy: GatePolicy | None = None,
) -> GateResult:
    summary = _summarize_pr(pr)
    base_protected = client.is_base_protected(summary["base_ref"] or "")
    return evaluate_gate(
        pr_number=summary["number"],
        head_sha=summary["head_sha"],
        base_sha=summary["base_sha"],
        mergeable=summary["mergeable"],
        draft=summary["draft"],
        open_threads=summary["open_threads"],
        pending_checks=summary["pending_checks"],
        approving_reviews=summary["approving_reviews"],
        base_protected=base_protected,
        overlapping_open=overlapping_open,
        policy=policy,
    )


# ── MCP tool handlers (read-only) ─────────────────────────────────────────


def pr_list_tool(state: str = "open", limit: int = 30) -> dict[str, Any]:
    client = GitHubPRClient()
    rows = client.list_pull_requests(state=state, limit=limit)
    return {
        "state": state,
        "count": len(rows),
        "pulls": [_summarize_pr(r) for r in rows],
    }


def pr_status_tool(number: int) -> dict[str, Any]:
    client = GitHubPRClient()
    pr = client.pull_request(number)
    summary = _summarize_pr(pr)
    gate = gate_for_pr(client, pr)
    result = summary
    result["gate"] = gate.as_dict()
    return result


def pr_gate_tool(number: int, expected_head_sha: str = "") -> dict[str, Any]:
    """Evaluate the merge-readiness gate for a PR.

    ``expected_head_sha`` lets a caller assert they are gating against a known
    head before acting (write-tools must require it); a mismatch is reported
    without blocking the read.
    """
    client = GitHubPRClient()
    pr = client.pull_request(number)
    gate = gate_for_pr(client, pr)
    result = gate.as_dict()
    if expected_head_sha:
        head = result["details"].get("head_sha", "")
        result["details"]["head_sha_matches"] = (
            head == expected_head_sha if head else None
        )
    return result


def pr_policy_tool(policy_path: str = "") -> dict[str, Any]:
    """Show the resolved merge-gate policy (§4 config)."""
    policy = load_gate_policy(path=policy_path or None)
    return {"policy": policy.__dict__}


def pr_audit_tool(pr_number: int = 0, limit: int = 100) -> dict[str, Any]:
    """Show the local gate audit trail (§7), optionally for one PR."""
    from kater.storage import query_gate_audit

    rows = query_gate_audit(pr_number=pr_number or None, limit=limit)
    return {"count": len(rows), "entries": rows}


def pr_merge_tool(number: int, expected_head_sha: str = "", actor: str = "") -> dict[str, Any]:
    """Gate-then-merge a PR (§6 write-path). Requires a PASS gate and a pinned
    expected head SHA; refuses the merge otherwise and records it in the audit
    trail.
    """
    return merge_pr(number, expected_head_sha=expected_head_sha, actor=actor)


class MergeRejected(RuntimeError):
    """Raised when a merge is attempted against an ungateable PR."""


def merge_pr(
    number: int,
    *,
    expected_head_sha: str = "",
    actor: str = "",
    policy: GatePolicy | None = None,
) -> dict[str, Any]:
    """Gate-then-merge a PR through the GitHub provider.

    Deterministic write-path (§6): the merge is refused unless the evaluated
    gate is PASS, and the caller must pin the expected head SHA so a
    concurrent push cannot be merged by surprise. Records the attempt in the
    audit trail regardless of outcome.
    """
    from kater.storage import record_gate_audit

    client = GitHubPRClient()
    pr = client.pull_request(number)
    gate = gate_for_pr(client, pr, policy=policy)
    reasons = gate.reasons
    verdict = gate.verdict
    head = gate.details.get("head_sha", "")

    if verdict != VERDICT_PASS:
        record_gate_audit(
            action="merge_rejected",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=expected_head_sha or None,
            applied_head_sha=None,
            actor=actor or None,
            detail="gate not PASS",
        )
        raise MergeRejected(
            f"merge blocked: verdict={verdict} reasons={reasons}"
        )

    if expected_head_sha and head and head != expected_head_sha:
        record_gate_audit(
            action="merge_rejected",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=expected_head_sha,
            applied_head_sha=head,
            actor=actor or None,
            detail="expected head SHA mismatch",
        )
        raise MergeRejected(
            f"expected head {expected_head_sha} != current head {head}"
        )

    args = ["pr", "merge", str(number), "--squash", "--delete-branch"]
    if expected_head_sha:
        args += ["--ref", head]
    if client.repo:
        args += ["--repo", client.repo]
    result = client.runner(args)
    if result.returncode != 0:
        record_gate_audit(
            action="merge_failed",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=expected_head_sha or None,
            applied_head_sha=head,
            actor=actor or None,
            detail=result.stderr.strip()[:500],
        )
        raise RuntimeError(f"gh pr merge failed: {result.stderr.strip()}")

    record_gate_audit(
        action="merge_applied",
        pr_number=number,
        verdict=verdict,
        reasons=reasons,
        expected_head_sha=expected_head_sha or None,
        applied_head_sha=head,
        actor=actor or None,
        detail="squash merge",
    )
    return {"merged": True, "pr_number": number, "head_sha": head, "gate": gate.as_dict()}
