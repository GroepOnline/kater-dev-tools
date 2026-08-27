from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import urlencode, urlsplit

from kater.github_transport import (
    GitHubTransportError,
    TransportConfig,
    classify_github_failure,
    load_transport_config,
    parse_json_body,
    redact_secrets,
    run_github_command,
)

_log = logging.getLogger("kater.pr_control")
_SHA40 = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)

# Machine-readable gate verdicts and reason codes. Write-tools (merge) must
# require the recorded head SHA and only act on a PASS; WARN/BLOCK are
# abort conditions.
VERDICT_PASS = "PASS"
VERDICT_WARN = "WARN"
VERDICT_BLOCK = "BLOCK"
VERDICT_UNKNOWN = "UNKNOWN"

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
REASON_REVIEWER_APP_LOOKUP = "REVIEWER_APP_LOOKUP_FAILED"
REASON_ALREADY_MERGED = "ALREADY_MERGED"
REASON_ALREADY_CLOSED = "ALREADY_CLOSED"
REASON_GATE_INCOMPLETE = "GATE_INCOMPLETE"

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
    "cursoragent",
    "devin-ai-integration",
    "devin-ai-integration[bot]",
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


@dataclass(frozen=True)
class ReviewerAppLookup:
    identities: frozenset[str]
    failed: bool = False


# Reasons that hard-block a merge unconditionally.
@dataclass
class GatePolicy:
    """Operator-tunable gate thresholds (§4 policy config).

    Defaults encode a conservative-but-mergeable policy: require at least one
    *independent* approving review, block drafts, failed required checks, and
    an open P1 latch, and deny private-data-plane repositories. A protected
    base is expected (GitHub rulesets/branch protection) and does not block
    unless ``block_base_protected`` is opted in.
    """

    require_approvals: int = 1
    block_drafts: bool = True
    block_base_protected: bool = False
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


def _review_commit_oid(review: dict[str, Any]) -> str:
    """Commit SHA this review covers, if GitHub included one."""
    commit = review.get("commit")
    if isinstance(commit, dict):
        oid = str(commit.get("oid") or commit.get("sha") or "").strip()
        if oid:
            return oid
    for key in ("commit_id", "commitId", "commitOid"):
        value = str(review.get(key) or "").strip()
        if value:
            return value
    return ""


def count_independent_approvals(
    reviews: list[dict[str, Any]],
    *,
    author_login: str,
    policy: GatePolicy,
    fixer_logins: tuple[str, ...] = (),
    expected_head_sha: str = "",
    trusted_reviewer_apps: set[str] | None = None,
) -> int:
    """Count APPROVED reviews that are not author/bot/fixer (allowlist-aware).

    When ``expected_head_sha`` is nonempty, only APPROVE covering that exact
    commit OID counts. Missing review commit metadata fails closed.

    ``fixer_logins`` is the caller/policy set only. GitHub-mapped commit
    authors are not auto-unioned: the SSH push identity is often a different
    login from the PR author, and treating it as a fixer self-rejects the
    independent reviewer.
    """
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

    allow = {
        _normalize_login(v)
        for v in policy.independent_reviewer_allowlist
        if str(v).strip()
    }
    trusted_apps = {str(v).strip().lower() for v in (trusted_reviewer_apps or set())}
    deny = _login_set(policy.independent_reviewer_denylist)
    fixers = _login_set(policy.fixer_logins) | _login_set(fixer_logins)
    author = _normalize_login(author_login)
    pin = (expected_head_sha or "").strip()
    count = 0
    for login, state in latest_state.items():
        if state != "APPROVED":
            continue
        # App identity is credited only to the exact GitHub bot login.
        app_identity = ""
        if login.endswith("[bot]"):
            slug_prefix = f"{login.removesuffix('[bot]')}:"
            app_identity = next(
                (v for v in trusted_apps if v.startswith(slug_prefix)), ""
            )
        # App approvals are independent evidence only when pinned to a real
        # commit; never credit an App on a missing/short caller-supplied pin.
        if app_identity and not _SHA40.fullmatch(pin):
            app_identity = ""
        if allow and login not in allow and app_identity not in allow:
            continue
        if policy.reject_author_approval and author and login == author:
            continue
        review = latest_review[login]
        if policy.reject_bot_approval and (
            login in deny or app_identity in deny
            or (_review_is_bot(review, login) and app_identity not in allow)
        ):
            continue
        if policy.reject_fixer_approval and (login in fixers or app_identity in fixers):
            continue
        if pin and _review_commit_oid(review) != pin:
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
        REASON_REVIEWER_APP_LOOKUP,
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
    pr_state: str = "OPEN",
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

    ``pr_state`` defaults to ``OPEN`` for backward compatibility. Landed PRs
    (``MERGED`` / ``CLOSED``, or ``merged: true`` upstream) skip
    ``HEAD_STALE`` for ``mergeable == UNKNOWN`` because GitHub often reports
    unknown mergeability after merge/close.
    """
    policy = policy or GatePolicy()
    reasons: list[str] = []
    state = str(pr_state or "OPEN").strip().upper()
    landed = state in ("MERGED", "CLOSED")

    if landed:
        reasons.append(REASON_ALREADY_MERGED if state == "MERGED" else REASON_ALREADY_CLOSED)

    if draft and policy.block_drafts:
        reasons.append(REASON_DRAFT)
    if open_threads > 0 and not policy.allow_unresolved_threads:
        reasons.append(REASON_UNRESOLVED_THREAD)
    if mergeable == "CONFLICTING":
        reasons.append(REASON_MERGE_CONFLICT)
    elif mergeable == "UNKNOWN" and not landed:
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
            "base_protected": base_protected,
            "repo": repo,
            "required_failed": required_failed,
            "required_pending": required_pending,
            "required_missing": required_missing,
        },
    )


def _gh_environ() -> dict[str, str]:
    """Build an env for ``gh`` that honors Kater's GitHub adapter token.

    ``gh`` reads ``GH_TOKEN`` / ``GITHUB_TOKEN``, not
    ``GITHUB_PERSONAL_ACCESS_TOKEN``. Company-control Kater often has only the
    latter in the unit env, so PR tools 401 even when the adapter token is set.
    """
    env = os.environ.copy()
    if env.get("GH_TOKEN") or env.get("GITHUB_TOKEN"):
        return env
    pat = (env.get("GITHUB_PERSONAL_ACCESS_TOKEN") or "").strip()
    if pat:
        env["GH_TOKEN"] = pat
    return env


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    timeout = load_transport_config().timeout_sec
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
        env=_gh_environ(),
        timeout=timeout,
    )


def _pr_client(repo: str = "") -> GitHubPRClient:
    """PR client pinned to ``repo`` or ``KATER_PR_REPO``."""
    return GitHubPRClient(repo=repo.strip() or None)


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
    """GitHub provider backed by the `gh` CLI.

    Network and auth are isolated behind ``runner`` so the client is testable
    without a live GitHub connection. Read calls retry transient transport
    errors; write/merge calls do not.
    """

    repo: str | None = None
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_gh
    transport: TransportConfig | None = None

    def __post_init__(self) -> None:
        if self.repo is None:
            self.repo = _default_repo()
        if self.transport is None:
            self.transport = load_transport_config()

    def _config(self) -> TransportConfig:
        return getattr(self, "transport", None) or load_transport_config()

    def exec_command(
        self, args: list[str], *, mutate: bool = False
    ) -> subprocess.CompletedProcess[str]:
        runner = getattr(self, "runner", None) or _run_gh
        return run_github_command(
            args,
            invoke=runner,
            mutate=mutate,
            config=self._config(),
        )

    def _target(self, ref: str) -> str:
        repo = getattr(self, "repo", None)
        return f"{repo}#{ref}" if repo else ref

    def _api(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        # ``gh api -f k=v`` switches the method to POST. GET endpoints such as
        # commit check-runs then 404, which the gate reports as
        # REQUIRED_CHECK_LOOKUP. Keep reads as GET by putting query params in
        # the path.
        if params:
            encoded = urlencode(params)
            path = f"{path}&{encoded}" if "?" in path else f"{path}?{encoded}"
        args = ["api", path, "-H", "Accept: application/vnd.github+json"]
        proc = self.exec_command(args)
        return parse_json_body(proc, args)

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[dict[str, Any]]:
        repo = getattr(self, "repo", None)
        if repo:
            return self._list_pull_requests_rest(state=state, limit=limit)
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
        proc = self.exec_command(args)
        rows = parse_json_body(proc, args)
        if not isinstance(rows, list):
            raise classify_github_failure(args=args, malformed=True, stdout=proc.stdout)
        return [normalize_rest_pull(row) if isinstance(row, dict) else row for row in rows]

    def _list_pull_requests_rest(
        self, *, state: str = "open", limit: int = 30
    ) -> list[dict[str, Any]]:
        per_page = max(1, min(int(limit), 100))
        data = self._api(
            f"repos/{self.repo}/pulls",
            params={"state": state, "per_page": str(per_page)},
        )
        if not isinstance(data, list):
            raise classify_github_failure(
                args=["api", f"repos/{self.repo}/pulls"],
                malformed=True,
                stdout=json.dumps(data)[:200] if data is not None else "",
            )
        return [normalize_rest_pull(row) for row in data if isinstance(row, dict)]

    def pull_request(self, number: int) -> dict[str, Any]:
        repo = getattr(self, "repo", None)
        if repo:
            pr = self._pull_request_rest(number)
        else:
            pr = self._pull_request_graphql_cli(number)
        extras = self._graphql_extras(number, url=pr.get("url") or "")
        pr["reviewThreads"] = extras["reviewThreads"]
        if not pr.get("baseRefOid"):
            pr["baseRefOid"] = extras["baseRefOid"]
        return pr

    def trusted_reviewer_app_identities(self) -> ReviewerAppLookup:
        """Return provider-verified App identities installed for this repo.

        Missing/failed provider evidence is deliberately empty (fail closed).
        """
        repo = getattr(self, "repo", None)
        if not repo or "/" not in repo:
            return ReviewerAppLookup(frozenset(), True)
        owner = repo.split("/", 1)[0]
        try:
            installations: list[Any] = []
            page = 1
            while True:
                if page > 100:
                    return ReviewerAppLookup(frozenset(), True)
                payload = self._api(
                    f"orgs/{owner}/installations",
                    params={"per_page": "100", "page": str(page)},
                )
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("installations"), list
                ):
                    return ReviewerAppLookup(frozenset(), True)
                batch = payload["installations"]
                installations.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            # Verify that each candidate installation is actually attached to
            # this repository; org installation listing alone is insufficient.
            verified_installations: set[str] = set()
            for item in installations:
                if not isinstance(item, dict):
                    continue
                installation_id = str(item.get("id") or "").strip()
                if not installation_id:
                    continue
                repos: list[Any] = []
                repo_page = 1
                while True:
                    if repo_page > 100:
                        return ReviewerAppLookup(frozenset(), True)
                    payload = self._api(
                        f"user/installations/{installation_id}/repositories",
                        params={"per_page": "100", "page": str(repo_page)},
                    )
                    if not isinstance(payload, dict) or not isinstance(
                        payload.get("repositories"), list
                    ):
                        return ReviewerAppLookup(frozenset(), True)
                    batch = payload["repositories"]
                    repos.extend(batch)
                    if len(batch) < 100:
                        break
                    repo_page += 1
                if not any(isinstance(r, dict) and r.get("full_name") == repo for r in repos):
                    continue
                verified_installations.add(installation_id)
            result: set[str] = set()
            for item in installations:
                if not isinstance(item, dict):
                    continue
                installation_id = str(item.get("id") or "").strip()
                if installation_id not in verified_installations:
                    continue
                app = item.get("app_slug") or item.get("app")
                slug = str(app.get("slug") if isinstance(app, dict) else app or "").strip().lower()
                app_id = str(
                    item.get("app_id") or (app.get("id") if isinstance(app, dict) else "")
                ).strip()
                if not (slug and app_id and installation_id):
                    continue
                # App slugs are globally unique and the review itself proves
                # this installation reached the target repository; no
                # user-token repository-membership endpoint is required.
                result.add(f"{slug}:{app_id}:{installation_id}")
            return ReviewerAppLookup(frozenset(result))
        except (OSError, RuntimeError, ValueError, TypeError):
            return ReviewerAppLookup(frozenset(), True)

    def _pull_request_graphql_cli(self, number: int) -> dict[str, Any]:
        # ``reviewThreads`` / ``baseRefOid`` are not valid ``gh pr view --json``
        # fields ("Unknown JSON field"). Threads stay on the GraphQL extras hop.
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
        proc = self.exec_command(args)
        raw = parse_json_body(proc, args)
        if not isinstance(raw, dict):
            raise classify_github_failure(args=args, malformed=True, stdout=proc.stdout)
        return raw

    def _pull_request_rest(self, number: int) -> dict[str, Any]:
        raw = self._api(f"repos/{self.repo}/pulls/{number}")
        if not isinstance(raw, dict):
            raise classify_github_failure(
                args=["api", f"repos/{self.repo}/pulls/{number}"],
                malformed=True,
            )
        reviews = self._api(f"repos/{self.repo}/pulls/{number}/reviews")
        if not isinstance(reviews, list):
            raise classify_github_failure(
                args=["api", f"repos/{self.repo}/pulls/{number}/reviews"],
                malformed=True,
            )
        commits = self._api(f"repos/{self.repo}/pulls/{number}/commits")
        if not isinstance(commits, list):
            raise classify_github_failure(
                args=["api", f"repos/{self.repo}/pulls/{number}/commits"],
                malformed=True,
            )
        return normalize_rest_pull(raw, reviews=reviews, commits=commits)

    def pull_merge_evidence(self, number: int) -> dict[str, Any]:
        """Read merged/head only. Used to reconcile a timed-out write."""
        repo = getattr(self, "repo", None)
        if repo:
            raw = self._api(f"repos/{self.repo}/pulls/{number}")
            if not isinstance(raw, dict):
                raise classify_github_failure(
                    args=["api", f"repos/{self.repo}/pulls/{number}"],
                    malformed=True,
                )
            return normalize_rest_pull(raw)
        return self._pull_request_graphql_cli(number)

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
            proc = self.exec_command(args)
            data = parse_json_body(proc, args)
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
        """True when branch protection exists. Only HTTP 404 means unprotected."""
        if not getattr(self, "repo", None):
            return False
        try:
            data = self._api(f"repos/{self.repo}/branches/{base_ref}/protection")
        except GitHubTransportError as exc:
            if exc.is_not_found:
                return False
            raise
        return bool(data)

    def required_status_contexts(self, base_ref: str) -> list[str]:
        """Branch-protection required contexts. Empty when unprotected (404)."""
        if not getattr(self, "repo", None) or not base_ref:
            return []
        try:
            data = self._api(
                f"repos/{self.repo}/branches/{base_ref}/protection/required_status_checks"
            )
        except GitHubTransportError as exc:
            if exc.is_not_found:
                return []
            raise
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


def _mergeable_from_rest(raw: dict[str, Any]) -> str:
    if raw.get("mergeable") is False or str(raw.get("mergeable_state") or "").lower() == "dirty":
        return "CONFLICTING"
    existing = str(raw.get("mergeable") or "").upper()
    if existing in {"MERGEABLE", "CONFLICTING", "UNKNOWN"}:
        return existing
    state = str(raw.get("mergeable_state") or "").lower()
    if state == "clean" or raw.get("mergeable") is True:
        return "MERGEABLE"
    return "UNKNOWN"


def _normalize_rest_review(review: dict[str, Any]) -> dict[str, Any]:
    user = review.get("user") or review.get("author") or {}
    login = user.get("login") if isinstance(user, dict) else user
    is_bot = False
    if isinstance(user, dict):
        is_bot = user.get("type") == "Bot" or user.get("is_bot") is True
    oid = _review_commit_oid(review)
    mapped = {
        "author": {"login": login or "", "is_bot": is_bot},
        "state": review.get("state") or review.get("decision") or "",
        "authorAssociation": (
            review.get("author_association") or review.get("authorAssociation") or ""
        ),
    }
    if oid:
        mapped["commit_id"] = oid
        mapped["commit"] = {"oid": oid}
    return mapped


def normalize_rest_pull(
    raw: dict[str, Any],
    *,
    reviews: list[Any] | None = None,
    commits: list[Any] | None = None,
) -> dict[str, Any]:
    """Map a GitHub REST PR (plus optional reviews/commits) to gate fields."""
    if "headRefOid" in raw and "headRefName" in raw and reviews is None and commits is None:
        return dict(raw)

    gate_fields_incomplete = reviews is None and commits is None and not (
        raw.get("reviewDecision")
        or raw.get("latestReviews")
        or raw.get("reviews")
        or raw.get("statusCheckRollup")
    )

    user = raw.get("user") or raw.get("author") or {}
    head_raw = raw.get("head")
    base_raw = raw.get("base")
    head = head_raw if isinstance(head_raw, dict) else {}
    base = base_raw if isinstance(base_raw, dict) else {}
    mapped_reviews = raw.get("latestReviews") or raw.get("reviews") or []
    if reviews is not None:
        mapped_reviews = [
            _normalize_rest_review(row) if isinstance(row, dict) else row for row in reviews
        ]
    mapped_commits: list[dict[str, Any]] = []
    if commits:
        for row in commits:
            if not isinstance(row, dict):
                continue
            author = row.get("author")
            authors = []
            if isinstance(author, dict) and author.get("login"):
                authors.append({"login": str(author["login"])})
            mapped_commits.append({"oid": str(row.get("sha") or ""), "authors": authors})
    elif isinstance(raw.get("commits"), list):
        mapped_commits = [c for c in raw["commits"] if isinstance(c, dict)]

    author = {"login": str(user.get("login") or "")} if isinstance(user, dict) else user
    return {
        "number": raw.get("number"),
        "title": raw.get("title"),
        "url": raw.get("html_url") or raw.get("url") or "",
        "headRefName": head.get("ref") or raw.get("headRefName") or "",
        "baseRefName": base.get("ref") or raw.get("baseRefName") or "",
        "state": (
            "MERGED" if raw.get("merged") is True else str(raw.get("state") or "OPEN").upper()
        ),
        "merged": bool(raw.get("merged")),
        "isDraft": bool(raw.get("draft") if raw.get("draft") is not None else raw.get("isDraft")),
        "mergeable": _mergeable_from_rest(raw),
        "reviewDecision": raw.get("reviewDecision") or "",
        "statusCheckRollup": raw.get("statusCheckRollup") or [],
        "commits": mapped_commits,
        "headRefOid": head.get("sha") or raw.get("headRefOid") or "",
        "baseRefOid": base.get("sha") or raw.get("baseRefOid") or "",
        "reviews": mapped_reviews,
        "latestReviews": mapped_reviews,
        "author": author,
        "labels": raw.get("labels") or [],
        "gateFieldsIncomplete": gate_fields_incomplete,
    }


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


def _review_list(pr: dict[str, Any], *, prefer_full: bool = False) -> list[dict[str, Any]]:
    """Return review objects. Prefer full ``reviews`` (commit OIDs) when nonempty."""
    del prefer_full  # pin vs unpinned uses the same source list; OID filter is separate
    full = pr.get("reviews")
    latest = pr.get("latestReviews")
    if isinstance(full, list) and full:
        reviews: Any = full
    elif isinstance(latest, list) and latest:
        reviews = latest
    elif isinstance(full, list):
        reviews = full
    elif isinstance(latest, list):
        reviews = latest
    else:
        reviews = full or latest or []
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


def _pr_state(pr: dict[str, Any]) -> str:
    """Normalize GitHub PR lifecycle state for gate evaluation."""
    if pr.get("merged") is True:
        return "MERGED"
    state = str(pr.get("state") or "OPEN").strip().upper()
    if state in ("MERGED", "CLOSED"):
        return state
    return "OPEN"


def _summarize_pr(
    pr: dict[str, Any],
    *,
    policy: GatePolicy | None = None,
    expected_head_sha: str = "",
    trusted_reviewer_apps: set[str] | None = None,
) -> dict[str, Any]:
    policy = policy or GatePolicy()
    pin = (expected_head_sha or "").strip()
    threads = pr.get("reviewThreads") or []
    open_threads = sum(1 for t in threads if not t.get("isResolved"))
    checks = [c for c in (pr.get("statusCheckRollup") or []) if isinstance(c, dict)]
    check_summary = summarize_checks(checks, required_names=policy.required_check_names)
    pending_checks = check_summary["pending"]
    failed_checks = check_summary["failed"]
    decision = (pr.get("reviewDecision") or "").upper()
    approving = 1 if decision == "APPROVED" else 0
    reviews = _review_list(pr, prefer_full=bool(pin))
    author_login = _author_login(pr)
    commit_authors = _commit_author_logins(pr)
    independent = count_independent_approvals(
        reviews,
        author_login=author_login,
        policy=policy,
        expected_head_sha=pin,
        trusted_reviewer_apps=trusted_reviewer_apps,
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
        "commit_author_logins": list(commit_authors),
        "p1_latch_open": p1_latch_open(_label_list(pr), policy),
        "repo": repo,
        "required_failed": check_summary["required_failed"],
        "required_pending": check_summary["required_pending"],
        "required_missing": check_summary["required_missing"],
        "required_success": check_summary["required_success"],
        "required_names": check_summary["required_names"],
        "pr_state": _pr_state(pr),
    }


def gate_for_pr(
    client: GitHubPRClient,
    pr: dict[str, Any],
    *,
    overlapping_open: int = 0,
    policy: GatePolicy | None = None,
    expected_head_sha: str = "",
) -> GateResult:
    policy = policy or load_gate_policy()
    pin = (expected_head_sha or "").strip()
    # Human-only allowlists do not require installation/API evidence.
    needs_app_lookup = any(
        str(entry).strip().count(":") >= 2
        for entry in policy.independent_reviewer_allowlist
    )
    reviewer_lookup = (
        client.trusted_reviewer_app_identities()
        if needs_app_lookup
        else ReviewerAppLookup(frozenset())
    )
    summary = _summarize_pr(
        pr,
        policy=policy,
        expected_head_sha=pin,
        trusted_reviewer_apps=set(reviewer_lookup.identities),
    )
    protection_lookup_failed = False
    try:
        base_protected = client.is_base_protected(summary["base_ref"] or "")
    except GitHubTransportError:
        base_protected = False
        protection_lookup_failed = True
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
        pr_state=summary["pr_state"],
    )
    if reviewer_lookup.failed:
        result.reasons.append(REASON_REVIEWER_APP_LOOKUP)
        result.verdict = VERDICT_BLOCK
    if required_lookup_failed or check_runs_failed or protection_lookup_failed:
        if REASON_REQUIRED_CHECK_LOOKUP not in result.reasons:
            result.reasons.append(REASON_REQUIRED_CHECK_LOOKUP)
        result.verdict = _collapse(
            result.verdict,
            result.reasons,
            policy,
            required_incomplete=check_summary["required_pending"] > 0,
        )
    if pin:
        result.details["expected_head_sha"] = pin
        matches = head_sha == pin if head_sha else None
        result.details["head_sha_matches"] = matches
        if matches is not True:
            if REASON_HEAD_STALE not in result.reasons:
                result.reasons.append(REASON_HEAD_STALE)
            result.verdict = _collapse(
                result.verdict,
                result.reasons,
                policy,
                required_incomplete=check_summary["required_pending"] > 0,
            )
    return result


def _list_gate_for_pr(pr: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Advisory list-view gate: never BLOCK/PASS on unfetched review/check fields."""
    policy = load_gate_policy()
    if not pr.get("gateFieldsIncomplete"):
        return evaluate_gate(
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
            policy=policy,
            failed_checks=summary.get("failed_checks") or 0,
            p1_latch_open=bool(summary.get("p1_latch_open")),
            independent_approvals=summary.get("independent_approvals"),
            repo=summary.get("repo") or "",
            required_failed=summary.get("required_failed") or 0,
            required_pending=summary.get("required_pending") or 0,
            required_missing=summary.get("required_missing") or 0,
            pr_state=summary.get("pr_state") or "OPEN",
        ).as_dict()

    # REST list rows omit reviews/commits/check-runs. Still surface draft/conflict/
    # repo/lifecycle signals from fields we did fetch; never infer review/check state.
    list_policy = replace(
        policy,
        require_approvals=0,
        block_failed_checks=False,
        require_required_checks=False,
    )
    result = evaluate_gate(
        pr_number=summary["number"],
        head_sha=summary["head_sha"],
        base_sha=summary["base_sha"],
        mergeable=summary["mergeable"],
        draft=summary["draft"],
        open_threads=summary["open_threads"],
        pending_checks=0,
        approving_reviews=0,
        base_protected=False,
        overlapping_open=0,
        policy=list_policy,
        failed_checks=0,
        p1_latch_open=bool(summary.get("p1_latch_open")),
        independent_approvals=None,
        repo=summary.get("repo") or "",
        required_failed=0,
        required_pending=0,
        required_missing=0,
        pr_state=summary.get("pr_state") or "OPEN",
    )
    if REASON_GATE_INCOMPLETE not in result.reasons:
        result.reasons.append(REASON_GATE_INCOMPLETE)
    if result.verdict == VERDICT_PASS:
        result.verdict = VERDICT_UNKNOWN
    result.details["advisory"] = True
    return result.as_dict()


# ── MCP tool handlers (read-only) ─────────────────────────────────────────


def pr_list_tool(state: str = "open", limit: int = 30, repo: str = "") -> dict[str, Any]:
    client = _pr_client(repo)
    rows = client.list_pull_requests(state=state, limit=limit)
    pulls = []
    for r in rows:
        summary = _summarize_pr(r)
        # List view skips the per-PR base-protection lookup (one extra API call
        # each) to stay cheap; the single-PR gate/status paths still check it.
        summary["gate"] = _list_gate_for_pr(r, summary)
        pulls.append(summary)
    return {
        "state": state,
        "count": len(pulls),
        "pulls": pulls,
    }


def pr_status_tool(number: int, repo: str = "") -> dict[str, Any]:
    client = _pr_client(repo)
    pr = client.pull_request(number)
    summary = _summarize_pr(pr)
    gate = gate_for_pr(client, pr)
    result = summary
    result["gate"] = gate.as_dict()
    return result


def pr_gate_tool(number: int, expected_head_sha: str = "", repo: str = "") -> dict[str, Any]:
    """Evaluate the merge-readiness gate for a PR.

    ``expected_head_sha`` lets a caller assert they are gating against a known
    head before acting. Write-tools must require a nonempty SHA. A nonempty
    pin that does not match the live head BLOCKs the read gate with
    ``HEAD_STALE``. Independent APPROVE must cover that same commit OID.
    """
    client = _pr_client(repo)
    pr = client.pull_request(number)
    return gate_for_pr(client, pr, expected_head_sha=expected_head_sha).as_dict()


def pr_policy_tool(policy_path: str = "") -> dict[str, Any]:
    """Show the resolved merge-gate policy (§4 config)."""
    policy = load_gate_policy(path=policy_path or None)
    return {"policy": policy.__dict__}


def pr_audit_tool(pr_number: int = 0, limit: int = 100) -> dict[str, Any]:
    """Show the local gate audit trail (§7), optionally for one PR."""
    from kater.storage import query_gate_audit

    rows = query_gate_audit(pr_number=pr_number or None, limit=limit)
    return {"count": len(rows), "entries": rows}


def pr_merge_tool(
    number: int, expected_head_sha: str = "", actor: str = "", repo: str = ""
) -> dict[str, Any]:
    """Gate-then-merge a PR (§6 write-path). Requires a PASS gate and a nonempty
    pinned expected head SHA; refuses the merge otherwise and records it in
    the audit trail. Empty ``expected_head_sha`` is always a hard reject.
    """
    return merge_pr(number, expected_head_sha=expected_head_sha, actor=actor, repo=repo)


class MergeRejected(RuntimeError):
    """Raised when a merge is attempted against an ungateable PR."""


def merge_pr(
    number: int,
    *,
    expected_head_sha: str = "",
    actor: str = "",
    repo: str = "",
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
    client = _pr_client(repo)
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

    gate = gate_for_pr(client, pr, policy=policy, expected_head_sha=pinned)
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
    try:
        result = client.exec_command(args, mutate=True)
    except GitHubTransportError as exc:
        if exc.retryable:
            return _reconcile_timed_out_merge(
                client,
                number=number,
                pinned=pinned,
                actor=actor,
                verdict=verdict,
                reasons=reasons,
                gate=gate,
                write_error=exc,
            )
        record_gate_audit(
            action="merge_failed",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
            applied_head_sha=head,
            actor=actor or None,
            detail=redact_secrets(str(exc))[:500],
        )
        raise RuntimeError(f"gh pr merge failed: {exc}") from exc
    if result.returncode != 0:
        detail = redact_secrets(result.stderr.strip())[:500]
        record_gate_audit(
            action="merge_failed",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
            applied_head_sha=head,
            actor=actor or None,
            detail=detail,
        )
        raise RuntimeError(f"gh pr merge failed: {detail}")

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


def _reconcile_timed_out_merge(
    client: GitHubPRClient,
    *,
    number: int,
    pinned: str,
    actor: str,
    verdict: str,
    reasons: list[str],
    gate: GateResult,
    write_error: GitHubTransportError,
) -> dict[str, Any]:
    """After a merge timeout, prove merged + exact pin via a bounded read."""
    from kater.storage import record_gate_audit

    try:
        evidence = client.pull_merge_evidence(number)
    except GitHubTransportError as exc:
        record_gate_audit(
            action="merge_failed",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
            applied_head_sha=None,
            actor=actor or None,
            detail=redact_secrets(f"merge write timed out; reconcile failed: {exc}")[:500],
        )
        raise RuntimeError(f"gh pr merge timed out and reconcile failed: {exc}") from exc

    head = str(evidence.get("headRefOid") or "")
    merged = evidence.get("merged") is True or _pr_state(evidence) == "MERGED"
    if merged and head and head == pinned:
        record_gate_audit(
            action="merge_applied",
            pr_number=number,
            verdict=verdict,
            reasons=reasons,
            expected_head_sha=pinned,
            applied_head_sha=head,
            actor=actor or None,
            detail="squash merge (reconciled after write timeout)",
        )
        return {
            "merged": True,
            "reconciled": True,
            "pr_number": number,
            "head_sha": head,
            "gate": gate.as_dict(),
        }

    record_gate_audit(
        action="merge_failed",
        pr_number=number,
        verdict=verdict,
        reasons=reasons,
        expected_head_sha=pinned,
        applied_head_sha=head or None,
        actor=actor or None,
        detail=redact_secrets(f"merge write timed out; not proven merged at pin {pinned}")[:500],
    )
    raise RuntimeError(
        f"gh pr merge timed out; PR not proven merged at pinned head {pinned} ({write_error})"
    )
