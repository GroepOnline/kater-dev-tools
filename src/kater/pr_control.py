from __future__ import annotations

import json
import logging
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

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
REASON_FAILED_CHECKS = "FAILED_CHECKS"
REASON_P1_LATCH = "P1_LATCH"
REASON_NO_REVIEWS = "NO_REVIEWS"
REASON_DRAFT = "DRAFT"
REASON_BASE_PROTECTED = "BASE_PROTECTED"
REASON_REPO_DENIED = "REPO_DENIED"
REASON_MISSING_HEAD_SHA = "MISSING_HEAD_SHA"
REASON_REQUIRED_CHECK_LOOKUP = "REQUIRED_CHECK_LOOKUP"

_FAILED_CONCLUSIONS = frozenset(
    {"FAILURE", "CANCELLED", "CANCELED", "TIMED_OUT", "STARTUP_FAILURE", "ERROR"}
)
_PENDING_STATUSES = frozenset({"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"})
_PENDING_CONCLUSIONS = frozenset({"ACTION_REQUIRED", "STALE"})
_SUCCESS_CONCLUSIONS = frozenset({"SUCCESS", "SKIPPED"})
_TUPLE_POLICY_FIELDS = frozenset(
    {
        "independent_reviewer_allowlist",
        "independent_reviewer_denylist",
        "fixer_logins",
        "p1_label_names",
        "allowed_repos",
        "denied_repo_markers",
        "required_check_names",
        "allowed_planes",
    }
)
_DEFAULT_BOT_DENYLIST = (
    "github-actions[bot]",
    "dependabot[bot]",
    "renovate[bot]",
    "copilot",
    "copilot[bot]",
    "codesmith-bot",
    "cursor[bot]",
)
_DEFAULT_P1_LABELS = ("P1", "p1", "p1-latch")
_DEFAULT_DENIED_REPO_MARKERS = ("utrecht",)
_COMPANY_CONTROL_PLANE = "company-control"


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
    *independent* approving review, block drafts, failed required checks, and
    an open P1 latch, and deny private-data-plane repositories.
    """

    require_approvals: int = 1
    block_drafts: bool = True
    block_base_protected: bool = True
    allow_overlapping_prs: bool = False
    allow_pending_checks: bool = True
    allow_unresolved_threads: bool = False
    block_failed_checks: bool = True
    block_p1_latch: bool = True
    require_required_checks: bool = True
    reject_author_approval: bool = True
    reject_bot_approval: bool = True
    reject_fixer_approval: bool = True
    require_explicit_repo_on_write: bool = True
    require_company_control_plane: bool = True
    independent_reviewer_allowlist: tuple[str, ...] = ()
    independent_reviewer_denylist: tuple[str, ...] = _DEFAULT_BOT_DENYLIST
    fixer_logins: tuple[str, ...] = ()
    p1_label_names: tuple[str, ...] = _DEFAULT_P1_LABELS
    allowed_repos: tuple[str, ...] = ()
    denied_repo_markers: tuple[str, ...] = _DEFAULT_DENIED_REPO_MARKERS
    required_check_names: tuple[str, ...] = ()
    allowed_planes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GatePolicy:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        for key in _TUPLE_POLICY_FIELDS:
            value = filtered.get(key)
            if isinstance(value, list):
                filtered[key] = tuple(str(item) for item in value)
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


def _normalize_login(login: str) -> str:
    return (login or "").strip().lstrip("@").lower()


def _is_bot_login(login: str) -> bool:
    normalized = _normalize_login(login)
    return normalized.endswith("[bot]") or normalized.endswith("-bot")


def _login_set(values: tuple[str, ...] | list[str]) -> set[str]:
    return {_normalize_login(v) for v in values if str(v).strip()}


def repo_from_url(url: str) -> str:
    """Extract owner/name from a github.com PR or repo URL. Empty if unknown."""
    parsed = urlsplit(url or "")
    if parsed.hostname != "github.com":
        return ""
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def repo_is_denied(repo: str, markers: tuple[str, ...]) -> bool:
    """True when owner or name contains a denied marker as a path segment/prefix."""
    owner, _, name = (repo or "").strip().lower().partition("/")
    segments = [owner, name]
    haystacks = [*segments, (repo or "").strip().lower()]
    for marker in markers:
        token = marker.strip().lower()
        if not token:
            continue
        for hay in haystacks:
            if hay == token or hay.startswith(f"{token}-") or hay.startswith(f"{token}_"):
                return True
            if f"-{token}-" in f"-{hay}-" or f"_{token}_" in f"_{hay}_":
                return True
        # Separator-free variants (utrechtlab / utrechtdata) — owner/name only.
        for hay in segments:
            if token in hay:
                return True
    return False


def write_scope_rejection(repo: str, policy: GatePolicy) -> str | None:
    """Return a write-path rejection detail, or None if the repo/plane is allowed."""
    cleaned = (repo or "").strip()
    if policy.require_explicit_repo_on_write and not cleaned:
        return "explicit repository required for merge"
    if repo_is_denied(cleaned, policy.denied_repo_markers):
        return "repository is not allowed for this gate"
    if policy.allowed_repos:
        allowed = {r.strip().lower() for r in policy.allowed_repos if r.strip()}
        if cleaned.lower() not in allowed:
            return "repository is not on the company-control allowlist"
    plane = os.environ.get("KATER_PR_PLANE", "").strip().lower()
    allowed_planes = _login_set(policy.allowed_planes)
    if policy.require_company_control_plane or allowed_planes:
        required = allowed_planes or {_COMPANY_CONTROL_PLANE}
        if plane not in required:
            return "plane is not company-control"
    return None


def classify_check(check: dict[str, Any]) -> str:
    """Return 'failed', 'pending', 'success', or 'other' for one check/status."""
    status = str(check.get("status") or check.get("state") or "").upper()
    conclusion = str(check.get("conclusion") or check.get("state") or "").upper()
    if conclusion in _FAILED_CONCLUSIONS:
        return "failed"
    if status in _PENDING_STATUSES or conclusion in _PENDING_CONCLUSIONS:
        return "pending"
    if conclusion in _SUCCESS_CONCLUSIONS or status == "COMPLETED":
        return "success" if conclusion in _SUCCESS_CONCLUSIONS else "other"
    return "other"


def summarize_checks(
    checks: list[dict[str, Any]],
    *,
    required_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Aggregate rollup/check-run rows, including required-name coverage."""
    failed = 0
    pending = 0
    by_name: dict[str, str] = {}
    required_from_flags: list[str] = []
    latest: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or check.get("context") or "").strip()
        if not name:
            kind = classify_check(check)
            if kind == "failed":
                failed += 1
            elif kind == "pending":
                pending += 1
            continue
        attempt = check.get("run_attempt", check.get("attempt", check.get("runAttempt")))
        timestamp = str(
            check.get("completed_at") or check.get("completedAt") or check.get("started_at") or ""
        )
        attempt_text = "" if attempt is None else str(attempt)
        key = (int(attempt_text) if attempt_text.isdigit() else -1, timestamp, index)
        previous = latest.get(name)
        if previous is None or key >= previous[0]:
            latest[name] = (key, check)
        if check.get("isRequired") is True:
            required_from_flags.append(name)

    for name, (_, check) in latest.items():
        kind = classify_check(check)
        if kind == "failed":
            failed += 1
        elif kind == "pending":
            pending += 1
        by_name[name] = kind

    required = tuple(
        dict.fromkeys(n.strip() for n in (*required_names, *required_from_flags) if n.strip())
    )
    required_failed = 0
    required_pending = 0
    required_missing = 0
    required_success = 0
    for name in required:
        state = by_name.get(name)
        if state == "success":
            required_success += 1
        elif state == "failed":
            required_failed += 1
        elif state == "pending":
            required_pending += 1
        else:
            required_missing += 1
    return {
        "failed": failed,
        "pending": pending,
        "required_names": list(required),
        "required_failed": required_failed,
        "required_pending": required_pending,
        "required_missing": required_missing,
        "required_success": required_success,
    }


def p1_latch_open(labels: list[Any], policy: GatePolicy) -> bool:
    """True when a configured P1 latch label is present on the PR."""
    names: list[str] = []
    for label in labels:
        if isinstance(label, str):
            names.append(label)
        elif isinstance(label, dict):
            names.append(str(label.get("name") or ""))
    wanted = {n.strip().lower() for n in policy.p1_label_names if n.strip()}
    return any(n.strip().lower() in wanted for n in names if n.strip())


def _review_login(review: dict[str, Any]) -> str:
    author = review.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "")
    if isinstance(author, str):
        return author
    return str(review.get("authorLogin") or "")


def _review_is_bot(review: dict[str, Any], login: str) -> bool:
    author = review.get("author")
    if isinstance(author, dict) and author.get("is_bot") is True:
        return True
    assoc = str(review.get("authorAssociation") or "").upper()
    if assoc == "BOT":
        return True
    return _is_bot_login(login)


def count_independent_approvals(
    reviews: list[dict[str, Any]],
    *,
    author_login: str,
    policy: GatePolicy,
    fixer_logins: tuple[str, ...] = (),
) -> int:
    """Count APPROVED reviews that are not author/bot/fixer (allowlist-aware)."""
    latest_state: dict[str, str] = {}
    latest_review: dict[str, dict[str, Any]] = {}
    for review in reviews:
        if not isinstance(review, dict):
            continue
        login = _normalize_login(_review_login(review))
        if not login:
            continue
        state = str(review.get("state") or review.get("decision") or "").upper()
        latest_state[login] = state
        latest_review[login] = review

    allow = _login_set(policy.independent_reviewer_allowlist)
    deny = _login_set(policy.independent_reviewer_denylist)
    fixers = _login_set(policy.fixer_logins) | _login_set(fixer_logins)
    author = _normalize_login(author_login)
    count = 0
    for login, state in latest_state.items():
        if state != "APPROVED":
            continue
        if allow and login not in allow:
            continue
        if policy.reject_author_approval and author and login == author:
            continue
        review = latest_review[login]
        if policy.reject_bot_approval and (login in deny or _review_is_bot(review, login)):
            continue
        if policy.reject_fixer_approval and login in fixers:
            continue
        count += 1
    return count


def _collapse(
    verdict: str,
    reasons: list[str],
    policy: GatePolicy,
    *,
    required_incomplete: bool = False,
) -> str:
    # A reason blocks only when the policy treats it as blocking; otherwise it
    # is a WARN. This keeps the verdict purely a function of (reasons, policy).
    blocking_here = {
        REASON_HEAD_STALE,
        REASON_MERGE_CONFLICT,
        REASON_UNRESOLVED_THREAD,
        REASON_OVERLAPPING_PR,
        REASON_REPO_DENIED,
        REASON_MISSING_HEAD_SHA,
        REASON_REQUIRED_CHECK_LOOKUP,
    }
    if policy.block_drafts:
        blocking_here.add(REASON_DRAFT)
    if policy.block_base_protected:
        blocking_here.add(REASON_BASE_PROTECTED)
    if policy.require_approvals > 0:
        blocking_here.add(REASON_NO_REVIEWS)
    if not policy.allow_pending_checks or required_incomplete:
        blocking_here.add(REASON_PENDING_CHECKS)
    if not policy.allow_overlapping_prs:
        blocking_here.add(REASON_OVERLAPPING_PR)
    if not policy.allow_unresolved_threads:
        blocking_here.add(REASON_UNRESOLVED_THREAD)
    if policy.block_failed_checks:
        blocking_here.add(REASON_FAILED_CHECKS)
    if policy.block_p1_latch:
        blocking_here.add(REASON_P1_LATCH)

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
    failed_checks: int = 0,
    p1_latch_open: bool = False,
    independent_approvals: int | None = None,
    repo: str = "",
    required_failed: int = 0,
    required_pending: int = 0,
    required_missing: int = 0,
) -> GateResult:
    """Deterministic PR merge-readiness gate.

    Pure function (no I/O) so it is fully unit-testable. The returned verdict
    is PASS only when no blocking or warning reason applies; WARN for soft
    issues; BLOCK for anything that must prevent a merge.

    The optional ``policy`` tunes which signals block vs. warn. When omitted,
    the safe-default :class:`GatePolicy` is used.

    New optional inputs default to PR19-compatible behavior: failed checks,
    P1 latch, independent-approval override, and repo denylist are inert
    unless the caller supplies a non-zero / non-empty value.
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
    required_incomplete = required_pending > 0
    if pending_checks > 0 and not policy.allow_pending_checks:
        reasons.append(REASON_PENDING_CHECKS)
    elif required_incomplete:
        reasons.append(REASON_PENDING_CHECKS)
    if (
        failed_checks > 0
        or required_failed > 0
        or (policy.require_required_checks and required_missing > 0)
    ) and policy.block_failed_checks:
        reasons.append(REASON_FAILED_CHECKS)
    if p1_latch_open and policy.block_p1_latch:
        reasons.append(REASON_P1_LATCH)
    approvals = approving_reviews if independent_approvals is None else independent_approvals
    if approvals < policy.require_approvals:
        reasons.append(REASON_NO_REVIEWS)
    if base_protected and policy.block_base_protected:
        reasons.append(REASON_BASE_PROTECTED)
    if repo and repo_is_denied(repo, policy.denied_repo_markers):
        reasons.append(REASON_REPO_DENIED)
    elif repo and policy.allowed_repos:
        allowed = {r.strip().lower() for r in policy.allowed_repos if r.strip()}
        if repo.strip().lower() not in allowed:
            reasons.append(REASON_REPO_DENIED)

    verdict = _collapse(VERDICT_PASS, reasons, policy, required_incomplete=required_incomplete)
    return GateResult(
        verdict=verdict,
        reasons=reasons,
        details={
            "pr_number": pr_number,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "open_threads": open_threads,
            "pending_checks": pending_checks,
            "failed_checks": failed_checks,
            "approving_reviews": approving_reviews,
            "independent_approvals": approvals,
            "overlapping_open": overlapping_open,
            "p1_latch_open": p1_latch_open,
            "repo": repo,
            "required_failed": required_failed,
            "required_pending": required_pending,
            "required_missing": required_missing,
        },
    )


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _default_repo() -> str | None:
    """Resolve the target repo for PR tools.

    ``KATER_PR_REPO`` (owner/name) pins the repo explicitly; without it the
    `gh` CLI falls back to the server process cwd, which for a daemonized
    kater is the repo in the working tree rather than whichever repo a caller
    asked to gate.
    """
    return os.environ.get("KATER_PR_REPO", "").strip() or None


@dataclass
class GitHubPRClient:
    """Read-only GitHub provider backed by the `gh` CLI.

    Network and auth are isolated behind ``runner`` so the client is testable
    without a live GitHub connection. Only GET-style operations are used; no
    writes occur here.
    """

    repo: str | None = None
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_gh

    def __post_init__(self) -> None:
        if self.repo is None:
            self.repo = _default_repo()

    def _target(self, ref: str) -> str:
        repo = getattr(self, "repo", None)
        return f"{repo}#{ref}" if repo else ref

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
                "isDraft,mergeable,reviewDecision,statusCheckRollup,commits,"
                "url,labels,author,latestReviews"
            ),
        ]
        repo = getattr(self, "repo", None)
        if repo:
            args += ["--repo", repo]
        proc = self.runner(args)
        if proc.returncode != 0:
            raise RuntimeError(f"gh pr list failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)

    def pull_request(self, number: int) -> dict[str, Any]:
        # NOTE: `reviewThreads` and `baseRefOid` are intentionally absent from
        # the --json field list: `gh pr view` does not expose them (fails with
        # "Unknown JSON field"). Both are fetched via GraphQL below.
        args = [
            "pr",
            "view",
            str(number),
            "--json",
            (
                "number,title,headRefName,baseRefName,state,url,"
                "isDraft,mergeable,reviewDecision,statusCheckRollup,"
                "commits,headRefOid,reviews,latestReviews,author,labels"
            ),
        ]
        repo = getattr(self, "repo", None)
        if repo:
            args += ["--repo", repo]
        proc = self.runner(args)
        if proc.returncode != 0:
            raise RuntimeError(f"gh pr view {number} failed: {proc.stderr.strip()}")
        pr: dict[str, Any] = json.loads(proc.stdout)
        extras = self._graphql_extras(number, url=pr.get("url") or "")
        pr["reviewThreads"] = extras["reviewThreads"]
        pr["baseRefOid"] = extras["baseRefOid"]
        return pr

    def review_threads(self, number: int, *, url: str = "") -> list[dict[str, Any]]:
        """Fetch review-thread resolution state via the GraphQL API."""
        return self._graphql_extras(number, url=url)["reviewThreads"]

    def _graphql_extras(self, number: int, *, url: str = "") -> dict[str, Any]:
        """Fetch fields `gh pr view --json` cannot provide, via GraphQL.

        Covers reviewThreads (unresolved-thread gating, paginated so threads
        beyond the first page still block) and baseRefOid (pinned base SHA).
        Fail-closed: any transport or GraphQL error raises rather than
        returning an optimistic empty result.
        """
        repo = getattr(self, "repo", None)
        if not repo and url:
            repo = repo_from_url(url) or None
        if not repo:
            raise RuntimeError(
                f"cannot resolve owner/repo for PR {number} review threads (set KATER_PR_REPO)"
            )
        owner, name = repo.split("/", 1)
        query = (
            "query($owner:String!,$name:String!,$number:Int!,$after:String){"
            "repository(owner:$owner,name:$name){pullRequest(number:$number){"
            "baseRefOid reviewThreads(first:100,after:$after){"
            "pageInfo{hasNextPage endCursor}nodes{isResolved isOutdated}}}}}"
        )
        base_args = [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={number}",
        ]
        threads: list[dict[str, Any]] = []
        base_oid = ""
        after: str | None = None
        while True:
            args = list(base_args)
            if after:
                args += ["-f", f"after={after}"]
            proc = self.runner(args)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"gh api graphql reviewThreads for PR {number} failed: {proc.stderr.strip()}"
                )
            data = json.loads(proc.stdout)
            if data.get("errors"):
                raise RuntimeError(
                    f"GraphQL errors for PR {number}: {json.dumps(data['errors'])[:500]}"
                )
            pull = ((data.get("data") or {}).get("repository") or {}).get("pullRequest")
            if pull is None:
                raise RuntimeError(f"PR {number} not found in {repo} via GraphQL")
            base_oid = pull.get("baseRefOid") or ""
            conn = pull.get("reviewThreads")
            if not isinstance(conn, dict):
                # Partial data without an errors array: never fail open on
                # missing thread state.
                raise RuntimeError(f"reviewThreads missing in GraphQL response for PR {number}")
            threads.extend(n for n in (conn.get("nodes") or []) if isinstance(n, dict))
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            after = page.get("endCursor")
            if not after:
                # hasNextPage with no endCursor would silently truncate the
                # thread list and under-count open threads, letting the merge
                # gate pass on partial data. Fail closed instead.
                raise RuntimeError(
                    f"gh api graphql reviewThreads for PR {number} reported "
                    "hasNextPage without an endCursor"
                )
        return {"baseRefOid": base_oid, "reviewThreads": threads}

    def is_base_protected(self, base_ref: str) -> bool:
        if not getattr(self, "repo", None):
            return False
        try:
            data = self._api(f"repos/{self.repo}/branches/{base_ref}/protection")
        except RuntimeError:
            return False
        return bool(data)

    def required_status_contexts(self, base_ref: str) -> list[str]:
        """Branch-protection required contexts. Empty when unprotected (404)."""
        if not getattr(self, "repo", None) or not base_ref:
            return []
        try:
            data = self._api(
                f"repos/{self.repo}/branches/{base_ref}/protection/required_status_checks"
            )
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "404" in msg or "not found" in msg:
                return []
            raise
        if not isinstance(data, dict):
            raise RuntimeError("required status-check policy response was invalid")
        contexts = data.get("contexts") or []
        checks = data.get("checks") or []
        names: list[str] = []
        for ctx in contexts:
            if isinstance(ctx, str) and ctx.strip():
                names.append(ctx.strip())
        for check in checks:
            if isinstance(check, dict):
                app_ctx = str(check.get("context") or "").strip()
                if app_ctx:
                    names.append(app_ctx)
        return list(dict.fromkeys(names))

    def commit_check_runs(self, sha: str) -> list[dict[str, Any]] | None:
        """Check runs for an exact commit SHA.

        Returns ``None`` on transport/shape errors so callers can fail closed
        instead of treating a lookup failure as an empty (green) result.
        Successful empty lists are returned as ``[]``.
        """
        if not getattr(self, "repo", None) or not sha:
            return []
        runs: list[dict[str, Any]] = []
        page = 1
        try:
            while page <= 20:
                data = self._api(
                    f"repos/{self.repo}/commits/{sha}/check-runs",
                    params={"per_page": "100", "page": str(page)},
                )
                if not isinstance(data, dict):
                    return None
                batch = data.get("check_runs") or []
                runs.extend(row for row in batch if isinstance(row, dict))
                if len(batch) < 100:
                    break
                page += 1
        except RuntimeError:
            return None
        return runs


def _label_list(pr: dict[str, Any]) -> list[Any]:
    labels = pr.get("labels") or []
    if isinstance(labels, dict):
        labels = labels.get("nodes") or labels.get("edges") or []
    return labels if isinstance(labels, list) else []


def _author_login(pr: dict[str, Any]) -> str:
    author = pr.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "")
    if isinstance(author, str):
        return author
    return ""


def _review_list(pr: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = pr.get("latestReviews") or pr.get("reviews") or []
    if isinstance(reviews, dict):
        reviews = reviews.get("nodes") or []
    return [r for r in reviews if isinstance(r, dict)] if isinstance(reviews, list) else []


def _commit_author_logins(pr: dict[str, Any]) -> tuple[str, ...]:
    logins: list[str] = []
    for commit in pr.get("commits") or []:
        if not isinstance(commit, dict):
            continue
        authors = commit.get("authors") or []
        if isinstance(authors, list):
            for author in authors:
                if isinstance(author, dict) and author.get("login"):
                    logins.append(str(author["login"]))
        author = commit.get("author")
        if isinstance(author, dict) and author.get("login"):
            logins.append(str(author["login"]))
    return tuple(dict.fromkeys(logins))


def _summarize_pr(pr: dict[str, Any], *, policy: GatePolicy | None = None) -> dict[str, Any]:
    policy = policy or GatePolicy()
    threads = pr.get("reviewThreads") or []
    open_threads = sum(1 for t in threads if not t.get("isResolved"))
    checks = [c for c in (pr.get("statusCheckRollup") or []) if isinstance(c, dict)]
    check_summary = summarize_checks(checks, required_names=policy.required_check_names)
    pending_checks = check_summary["pending"]
    failed_checks = check_summary["failed"]
    decision = (pr.get("reviewDecision") or "").upper()
    approving = 1 if decision == "APPROVED" else 0
    reviews = _review_list(pr)
    author_login = _author_login(pr)
    independent: int | None = None
    if reviews:
        independent = count_independent_approvals(
            reviews,
            author_login=author_login,
            policy=policy,
            fixer_logins=_commit_author_logins(pr),
        )
    commits = pr.get("commits") or []
    head_sha = pr.get("headRefOid") or (commits[-1].get("oid") if commits else "")
    base_sha = pr.get("baseRefOid") or ""
    repo = repo_from_url(str(pr.get("url") or ""))
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
        "failed_checks": failed_checks,
        "approving_reviews": approving,
        "independent_approvals": independent,
        "author_login": author_login,
        "p1_latch_open": p1_latch_open(_label_list(pr), policy),
        "repo": repo,
        "required_failed": check_summary["required_failed"],
        "required_pending": check_summary["required_pending"],
        "required_missing": check_summary["required_missing"],
        "required_success": check_summary["required_success"],
        "required_names": check_summary["required_names"],
    }


def gate_for_pr(
    client: GitHubPRClient,
    pr: dict[str, Any],
    *,
    overlapping_open: int = 0,
    policy: GatePolicy | None = None,
) -> GateResult:
    policy = policy or GatePolicy()
    summary = _summarize_pr(pr, policy=policy)
    base_protected = client.is_base_protected(summary["base_ref"] or "")
    repo = (getattr(client, "repo", None) or summary.get("repo") or "").strip()
    required_names = tuple(policy.required_check_names)
    required_lookup_failed = False
    if policy.require_required_checks:
        try:
            discovered = client.required_status_contexts(summary["base_ref"] or "")
        except RuntimeError:
            required_lookup_failed = True
            discovered = []
        required_names = tuple(dict.fromkeys([*required_names, *discovered]))
    head_sha = str(summary["head_sha"] or "")
    rollup = [c for c in (pr.get("statusCheckRollup") or []) if isinstance(c, dict)]
    check_runs_failed = False
    if head_sha:
        exact_runs = client.commit_check_runs(head_sha)
        if exact_runs is None:
            check_runs_failed = True
            check_rows: list[dict[str, Any]] = []
        else:
            # Successful exact-SHA lookup wins even when empty — do not fall
            # back to rollup (which can hide a missing required check).
            check_rows = exact_runs
    else:
        check_rows = rollup
    check_summary = summarize_checks(check_rows, required_names=required_names)
    result = evaluate_gate(
        pr_number=summary["number"],
        head_sha=summary["head_sha"],
        base_sha=summary["base_sha"],
        mergeable=summary["mergeable"],
        draft=summary["draft"],
        open_threads=summary["open_threads"],
        pending_checks=check_summary["pending"],
        approving_reviews=summary["approving_reviews"],
        base_protected=base_protected,
        overlapping_open=overlapping_open,
        policy=policy,
        failed_checks=check_summary["failed"],
        p1_latch_open=bool(summary["p1_latch_open"]),
        independent_approvals=summary["independent_approvals"],
        repo=repo,
        required_failed=check_summary["required_failed"],
        required_pending=check_summary["required_pending"],
        required_missing=check_summary["required_missing"],
    )
    if required_lookup_failed or check_runs_failed:
        if REASON_REQUIRED_CHECK_LOOKUP not in result.reasons:
            result.reasons.append(REASON_REQUIRED_CHECK_LOOKUP)
        result.verdict = _collapse(
            result.verdict,
            result.reasons,
            policy,
            required_incomplete=check_summary["required_pending"] > 0,
        )
    return result


# ── MCP tool handlers (read-only) ─────────────────────────────────────────


def pr_list_tool(state: str = "open", limit: int = 30) -> dict[str, Any]:
    client = GitHubPRClient()
    rows = client.list_pull_requests(state=state, limit=limit)
    pulls = []
    for r in rows:
        summary = _summarize_pr(r)
        # List view skips the per-PR base-protection lookup (one extra API call
        # each) to stay cheap; the single-PR gate/status paths still check it.
        summary["gate"] = evaluate_gate(
            pr_number=summary["number"],
            head_sha=summary["head_sha"],
            base_sha=summary["base_sha"],
            mergeable=summary["mergeable"],
            draft=summary["draft"],
            open_threads=summary["open_threads"],
            pending_checks=summary["pending_checks"],
            approving_reviews=summary["approving_reviews"],
            base_protected=False,
            overlapping_open=0,
            failed_checks=summary.get("failed_checks") or 0,
            p1_latch_open=bool(summary.get("p1_latch_open")),
            independent_approvals=summary.get("independent_approvals"),
            repo=summary.get("repo") or "",
            required_failed=summary.get("required_failed") or 0,
            required_pending=summary.get("required_pending") or 0,
            required_missing=summary.get("required_missing") or 0,
        ).as_dict()
        pulls.append(summary)
    return {
        "state": state,
        "count": len(pulls),
        "pulls": pulls,
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
    head before acting. Write-tools must require a nonempty SHA; this read
    path still allows an empty pin and reports ``head_sha_matches`` when one
    is supplied.
    """
    client = GitHubPRClient()
    pr = client.pull_request(number)
    gate = gate_for_pr(client, pr)
    result = gate.as_dict()
    if expected_head_sha:
        head = result["details"].get("head_sha", "")
        result["details"]["head_sha_matches"] = head == expected_head_sha if head else None
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
    """Gate-then-merge a PR (§6 write-path). Requires a PASS gate and a nonempty
    pinned expected head SHA; refuses the merge otherwise and records it in
    the audit trail. Empty ``expected_head_sha`` is always a hard reject.
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
    gate is PASS, the caller pins a nonempty expected head SHA, the
    repository is company-control (not a denied private-data-plane name),
    and required checks succeeded on that exact SHA. Records the attempt in
    the audit trail regardless of outcome.
    """
    from kater.storage import record_gate_audit

    policy = policy or load_gate_policy()
    pinned = (expected_head_sha or "").strip()
    client = GitHubPRClient()
    pr = client.pull_request(number)
    repo = (getattr(client, "repo", None) or repo_from_url(str(pr.get("url") or "")) or "").strip()
    scope_error = write_scope_rejection(repo, policy)
    if scope_error:
        record_gate_audit(
            action="merge_rejected",
            pr_number=number,
            verdict=VERDICT_BLOCK,
            reasons=[REASON_REPO_DENIED],
            expected_head_sha=pinned or None,
            applied_head_sha=None,
            actor=actor or None,
            detail=scope_error,
        )
        raise MergeRejected(f"merge blocked: {scope_error}")

    if not pinned:
        record_gate_audit(
            action="merge_rejected",
            pr_number=number,
            verdict=VERDICT_BLOCK,
            reasons=[REASON_MISSING_HEAD_SHA],
            expected_head_sha=None,
            applied_head_sha=None,
            actor=actor or None,
            detail="expected_head_sha is required for merge",
        )
        raise MergeRejected("expected_head_sha is required for merge")

    gate = gate_for_pr(client, pr, policy=policy)
    reasons = gate.reasons
    verdict = gate.verdict
    head = str(gate.details.get("head_sha") or "")

    if verdict != VERDICT_PASS:
        record_gate_audit(
            action="merge_rejected",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
            applied_head_sha=None,
            actor=actor or None,
            detail="gate not PASS",
        )
        raise MergeRejected(f"merge blocked: verdict={verdict} reasons={reasons}")

    if not head or head != pinned:
        record_gate_audit(
            action="merge_rejected",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
            applied_head_sha=head or None,
            actor=actor or None,
            detail="expected head SHA mismatch",
        )
        raise MergeRejected(f"expected head {pinned} != current head {head}")

    args = [
        "pr",
        "merge",
        str(number),
        "--squash",
        "--delete-branch",
        "--match-head-commit",
        pinned,
    ]
    # Reuse the validated ``repo`` from write-scope resolution — do not
    # re-read client.repo after the gate passed.
    if repo:
        args += ["--repo", repo]
    result = client.runner(args)
    if result.returncode != 0:
        record_gate_audit(
            action="merge_failed",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
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
        expected_head_sha=pinned,
        applied_head_sha=head,
        actor=actor or None,
        detail="squash merge",
    )
    return {"merged": True, "pr_number": number, "head_sha": head, "gate": gate.as_dict()}
