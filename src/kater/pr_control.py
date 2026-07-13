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
_BLOCKING = {
    REASON_HEAD_STALE,
    REASON_MERGE_CONFLICT,
    REASON_UNRESOLVED_THREAD,
    REASON_OVERLAPPING_PR,
}

# Reasons that warn but do not block.
_WARN = {
    REASON_PENDING_CHECKS,
    REASON_NO_REVIEWS,
    REASON_DRAFT,
    REASON_BASE_PROTECTED,
}


def _collapse(verdict: str, reasons: list[str]) -> str:
    if any(r in _BLOCKING for r in reasons):
        return VERDICT_BLOCK
    if any(r in _WARN for r in reasons):
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
) -> GateResult:
    """Deterministic PR merge-readiness gate.

    Pure function (no I/O) so it is fully unit-testable. The returned verdict
    is PASS only when no blocking or warning reason applies; WARN for soft
    issues; BLOCK for anything that must prevent a merge.
    """
    reasons: list[str] = []

    if draft:
        reasons.append(REASON_DRAFT)
    if open_threads > 0:
        reasons.append(REASON_UNRESOLVED_THREAD)
    if mergeable == "CONFLICTING":
        reasons.append(REASON_MERGE_CONFLICT)
    elif mergeable == "UNKNOWN":
        # Unknown mergeability is treated as stale/unverified rather than green.
        reasons.append(REASON_HEAD_STALE)
    if overlapping_open > 0:
        reasons.append(REASON_OVERLAPPING_PR)
    if pending_checks > 0:
        reasons.append(REASON_PENDING_CHECKS)
    if approving_reviews == 0:
        reasons.append(REASON_NO_REVIEWS)
    if base_protected:
        reasons.append(REASON_BASE_PROTECTED)

    verdict = _collapse(VERDICT_PASS, reasons)
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
