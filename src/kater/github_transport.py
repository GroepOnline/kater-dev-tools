"""Bounded, classifiable GitHub CLI transport for PR-gate I/O.

Read-only ``gh`` calls retry transient network/timeouts under a strict
budget. Write/merge calls are one-shot. Secrets are redacted before any
error leaves this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TIMEOUT_SEC = 12.0
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_BUDGET_SEC = 40.0
DEFAULT_BACKOFF_SEC = 0.2
DEFAULT_BACKOFF_CAP_SEC = 1.6
DEFAULT_JITTER_RATIO = 0.25

ERROR_TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
ERROR_TIMEOUT = "TIMEOUT"
ERROR_AUTH_PERMANENT = "AUTH_PERMANENT"
ERROR_PERMANENT = "PERMANENT"
ERROR_MALFORMED = "MALFORMED_RESPONSE"
ERROR_NOT_FOUND = "NOT_FOUND"

_SECRET_RE = re.compile(
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]+"
    r"|github_pat_[A-Za-z0-9_]+"
    r"|Bearer\s+[A-Za-z0-9._\-=]+"
    r"|authorization:\s*\S+",
    re.IGNORECASE,
)
_HTTP_RE = re.compile(r"\bHTTP\s+(\d{3})\b", re.IGNORECASE)
_TRANSIENT_MARKERS = (
    "dial tcp",
    "i/o timeout",
    "io timeout",
    "tls handshake timeout",
    "connection reset",
    "connection refused",
    "connection aborted",
    "network is unreachable",
    "no route to host",
    "temporary failure",
    "context deadline exceeded",
    "eof",
    "broken pipe",
    "error connecting to api.github.com",
)
_AUTH_MARKERS = (
    "bad credentials",
    "authentication required",
    "auth required",
    "must be authenticated",
    "requires authentication",
    "resource not accessible by integration",
)
_PERMANENT_MARKERS = (
    "unknown json field",
    "merge conflict",
    "required status checks",
    "pull request is not mergeable",
)


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]
Rng = Callable[[], float]
Clock = Callable[[], float]


def redact_secrets(text: str) -> str:
    """Strip token-like material from operator-visible strings."""
    if not text:
        return ""
    return _SECRET_RE.sub("[redacted]", text)


def _clamp_float(raw: str, default: float, *, min_v: float, max_v: float) -> float:
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(min_v, min(max_v, value))


def _clamp_int(raw: str, default: int, *, min_v: int, max_v: int) -> int:
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_v, min(max_v, value))


def load_transport_config() -> TransportConfig:
    """Read bounded transport knobs from the environment."""
    return TransportConfig(
        timeout_sec=_clamp_float(
            os.environ.get("KATER_GH_TIMEOUT_SEC", ""),
            DEFAULT_TIMEOUT_SEC,
            min_v=1.0,
            max_v=60.0,
        ),
        extra_retries=_clamp_int(
            os.environ.get("KATER_GH_RETRY_ATTEMPTS", ""),
            DEFAULT_RETRY_ATTEMPTS,
            min_v=0,
            max_v=4,
        ),
        retry_budget_sec=_clamp_float(
            os.environ.get("KATER_GH_RETRY_BUDGET_SEC", ""),
            DEFAULT_RETRY_BUDGET_SEC,
            min_v=1.0,
            max_v=120.0,
        ),
        backoff_base_sec=_clamp_float(
            os.environ.get("KATER_GH_BACKOFF_SEC", ""),
            DEFAULT_BACKOFF_SEC,
            min_v=0.0,
            max_v=5.0,
        ),
    )


@dataclass
class TransportConfig:
    timeout_sec: float = DEFAULT_TIMEOUT_SEC
    extra_retries: int = DEFAULT_RETRY_ATTEMPTS
    retry_budget_sec: float = DEFAULT_RETRY_BUDGET_SEC
    backoff_base_sec: float = DEFAULT_BACKOFF_SEC
    backoff_cap_sec: float = DEFAULT_BACKOFF_CAP_SEC
    jitter_ratio: float = DEFAULT_JITTER_RATIO
    sleeper: Sleeper = time.sleep
    rng: Rng = random.random
    clock: Clock = time.monotonic

    @property
    def max_attempts(self) -> int:
        return 1 + max(0, self.extra_retries)


def github_token_identity() -> dict[str, Any]:
    """Env precedence + SHA-256 fingerprint. Never the token value."""
    gh_token = (os.environ.get("GH_TOKEN") or "").strip()
    github_token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    pat = (os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or "").strip()
    if gh_token:
        source = "GH_TOKEN"
        token = gh_token
        unused = []
        if github_token:
            unused.append("GITHUB_TOKEN")
        if pat:
            unused.append("GITHUB_PERSONAL_ACCESS_TOKEN")
        precedence = "GH_TOKEN wins"
        if unused:
            precedence = f"GH_TOKEN wins over {', '.join(unused)}"
    elif github_token:
        source = "GITHUB_TOKEN"
        token = github_token
        precedence = (
            "GITHUB_TOKEN wins over GITHUB_PERSONAL_ACCESS_TOKEN" if pat else "GITHUB_TOKEN"
        )
    elif pat:
        source = "GITHUB_PERSONAL_ACCESS_TOKEN"
        token = pat
        precedence = "GITHUB_PERSONAL_ACCESS_TOKEN mapped to GH_TOKEN"
    else:
        return {
            "token_env": None,
            "fingerprint": None,
            "precedence": "none",
        }
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return {
        "token_env": source,
        "fingerprint": digest,
        "precedence": precedence,
    }


def extract_http_status(text: str) -> int | None:
    match = _HTTP_RE.search(text or "")
    if match:
        return int(match.group(1))
    lowered = (text or "").lower()
    if '"not found"' in lowered or "not found" in lowered:
        if "404" in lowered:
            return 404
    return None


def command_summary(args: list[str]) -> str:
    if not args:
        return "gh"
    if args[0] == "api" and len(args) > 1:
        if args[1] == "graphql":
            return "api graphql"
        return f"api {args[1]}"
    return " ".join(args[:4])


def infer_transport(args: list[str]) -> str:
    if not args:
        return "cli"
    if args[0] == "api":
        if len(args) > 1 and args[1] == "graphql":
            return "graphql"
        return "rest"
    if args[:2] == ["pr", "view"] or args[:2] == ["pr", "list"]:
        return "graphql"
    return "cli"


def classify_github_failure(
    *,
    args: list[str],
    returncode: int | None = None,
    stderr: str = "",
    stdout: str = "",
    timeout: bool = False,
    malformed: bool = False,
    attempts: int = 1,
) -> GitHubTransportError:
    """Build a redacted, typed error from a ``gh`` outcome."""
    blob = redact_secrets(" ".join(part for part in (stderr, stdout) if part))
    lowered = blob.lower()
    status = extract_http_status(blob)
    transport = infer_transport(args)
    command = command_summary(args)
    identity = github_token_identity()

    if timeout:
        return GitHubTransportError(
            error_class=ERROR_TIMEOUT,
            retryable=True,
            attempts=attempts,
            transport=transport,
            command=command,
            message=redact_secrets(f"gh {command} timed out"),
            http_status=status,
            identity=identity,
        )
    if malformed:
        return GitHubTransportError(
            error_class=ERROR_MALFORMED,
            retryable=False,
            attempts=attempts,
            transport=transport,
            command=command,
            message=redact_secrets(f"gh {command} returned a malformed response"),
            http_status=status,
            identity=identity,
        )
    if status in {401, 403} or any(marker in lowered for marker in _AUTH_MARKERS):
        return GitHubTransportError(
            error_class=ERROR_AUTH_PERMANENT,
            retryable=False,
            attempts=attempts,
            transport=transport,
            command=command,
            message=redact_secrets(f"gh {command} failed: permanent auth error"),
            http_status=status or 401,
            identity=identity,
        )
    if status == 404:
        return GitHubTransportError(
            error_class=ERROR_NOT_FOUND,
            retryable=False,
            attempts=attempts,
            transport=transport,
            command=command,
            message=redact_secrets(f"gh {command} failed: not found"),
            http_status=404,
            identity=identity,
        )
    if status in {429, 500, 502, 503, 504} or any(
        marker in lowered for marker in _TRANSIENT_MARKERS
    ):
        detail = blob[:240] or "transient network error"
        return GitHubTransportError(
            error_class=ERROR_TRANSIENT_NETWORK,
            retryable=True,
            attempts=attempts,
            transport=transport,
            command=command,
            message=redact_secrets(f"gh {command} failed: {detail}"),
            http_status=status,
            identity=identity,
        )
    if any(marker in lowered for marker in _PERMANENT_MARKERS) or (
        status is not None and status >= 400
    ):
        detail = blob[:240] or "permanent GitHub error"
        return GitHubTransportError(
            error_class=ERROR_PERMANENT,
            retryable=False,
            attempts=attempts,
            transport=transport,
            command=command,
            message=redact_secrets(f"gh {command} failed: {detail}"),
            http_status=status,
            identity=identity,
        )
    detail = blob[:240] or f"exit {returncode}"
    return GitHubTransportError(
        error_class=ERROR_PERMANENT,
        retryable=False,
        attempts=attempts,
        transport=transport,
        command=command,
        message=redact_secrets(f"gh {command} failed: {detail}"),
        http_status=status,
        identity=identity,
    )


@dataclass
class GitHubTransportError(RuntimeError):
    """Typed GitHub transport failure. ``str()`` is always redacted."""

    error_class: str
    retryable: bool
    attempts: int
    transport: str
    command: str
    message: str
    http_status: int | None = None
    identity: dict[str, Any] = field(default_factory=github_token_identity)

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def __str__(self) -> str:
        return self.message

    @property
    def is_not_found(self) -> bool:
        return self.error_class == ERROR_NOT_FOUND or self.http_status == 404

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": self.message,
            "error_class": self.error_class,
            "retryable": self.retryable,
            "attempts": self.attempts,
            "transport": self.transport,
            "command": self.command,
            "http_status": self.http_status,
            "identity": {
                "token_env": (self.identity or {}).get("token_env"),
                "fingerprint": (self.identity or {}).get("fingerprint"),
                "precedence": (self.identity or {}).get("precedence"),
            },
        }


def github_error_payload(exc: BaseException) -> dict[str, Any]:
    """HTTP/MCP/CLI body for any PR-tool failure. Never includes secrets."""
    if isinstance(exc, GitHubTransportError):
        return exc.as_dict()
    return {
        "ok": False,
        "error": redact_secrets(str(exc)),
        "error_class": ERROR_PERMANENT,
        "retryable": False,
        "attempts": 1,
        "transport": "cli",
        "command": "",
        "http_status": None,
        "identity": github_token_identity(),
    }


def _backoff_delay(attempt: int, config: TransportConfig) -> float:
    base = min(config.backoff_cap_sec, config.backoff_base_sec * (2**attempt))
    jitter = 1.0 + config.jitter_ratio * (2.0 * config.rng() - 1.0)
    return max(0.0, base * jitter)


def run_github_command(
    args: list[str],
    *,
    invoke: Runner,
    mutate: bool = False,
    config: TransportConfig | None = None,
    expect_json: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run ``gh`` with optional read-only retries. Writes never retry."""
    cfg = config or load_transport_config()
    max_attempts = 1 if mutate else cfg.max_attempts
    started = cfg.clock()
    last_error: GitHubTransportError | None = None

    for attempt in range(max_attempts):
        if attempt > 0:
            elapsed = cfg.clock() - started
            if elapsed >= cfg.retry_budget_sec:
                if last_error is not None:
                    last_error.attempts = attempt
                    raise last_error
                raise classify_github_failure(
                    args=args,
                    stderr="retry budget exhausted",
                    attempts=attempt,
                )
            cfg.sleeper(_backoff_delay(attempt - 1, cfg))
        try:
            proc = invoke(args)
        except subprocess.TimeoutExpired as exc:
            last_error = classify_github_failure(
                args=args,
                timeout=True,
                stderr=str(exc),
                attempts=attempt + 1,
            )
            if mutate or attempt + 1 >= max_attempts:
                raise last_error from exc
            continue
        if proc.returncode == 0:
            if expect_json:
                try:
                    json.loads(proc.stdout or "")
                except ValueError as exc:
                    last_error = classify_github_failure(
                        args=args,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                        malformed=True,
                        attempts=attempt + 1,
                    )
                    raise last_error from exc
            return proc
        last_error = classify_github_failure(
            args=args,
            returncode=proc.returncode,
            stderr=proc.stderr or "",
            stdout=proc.stdout or "",
            attempts=attempt + 1,
        )
        if mutate or not last_error.retryable or attempt + 1 >= max_attempts:
            raise last_error
    if last_error is not None:
        raise last_error
    raise classify_github_failure(args=args, stderr="no attempts executed")


def parse_json_body(proc: subprocess.CompletedProcess[str], args: list[str]) -> Any:
    try:
        return json.loads(proc.stdout or "")
    except ValueError as exc:
        raise classify_github_failure(
            args=args,
            stdout=proc.stdout,
            stderr=proc.stderr,
            malformed=True,
        ) from exc
