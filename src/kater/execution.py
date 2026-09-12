"""Canonical execution models: identity, policy context, and structured results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError

from kater.connectors.errors import ConnectorCapabilityError, ConnectorUnavailableError
from kater.settings import load_settings

_RETRYABLE = frozenset({"unavailable", "timeout"})
_DANGEROUS_TOKENS = frozenset({"merge", "delete", "destroy", "admin", "drop"})

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None

_IDEMPOTENCY_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class ActorIdentity:
    actor_id: str = "anonymous"
    kind: str = "agent"
    agent_id: str | None = None
    principal_id: str | None = None

    def __post_init__(self) -> None:
        actor = (self.actor_id or self.principal_id or "anonymous").strip() or "anonymous"
        kind = (self.kind or "agent").strip() or "agent"
        object.__setattr__(self, "actor_id", actor)
        object.__setattr__(self, "kind", kind)
        if not self.principal_id:
            object.__setattr__(self, "principal_id", actor)

    def as_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "kind": self.kind,
            "agent_id": self.agent_id,
            "principal_id": self.principal_id,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None, *, default_actor: str = "anonymous") -> ActorIdentity:
        if not data:
            return cls(actor_id=default_actor)
        return cls(
            actor_id=str(data.get("actor_id") or data.get("principal_id") or default_actor),
            kind=str(data.get("kind") or "agent"),
            agent_id=(str(data["agent_id"]) if data.get("agent_id") else None),
            principal_id=(str(data["principal_id"]) if data.get("principal_id") else None),
        )


@dataclass(frozen=True, slots=True)
class PolicyContext:
    profile: str = "core"
    run_id: str | None = None
    trace_id: str | None = None
    context_id: str | None = None
    timeout_seconds: float | None = None
    max_retries: int = 0
    idempotency_key: str | None = None
    allow_dangerous: bool = True
    expected_head_sha: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile", (self.profile or "core").strip() or "core")
        retries = max(0, min(int(self.max_retries), 5))
        object.__setattr__(self, "max_retries", retries)
        if self.timeout_seconds is not None and float(self.timeout_seconds) <= 0:
            raise ValueError("timeout_seconds must be positive")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(
        cls,
        data: dict[str, Any] | None,
        *,
        profile: str = "core",
        context_id: str | None = None,
    ) -> PolicyContext:
        payload = dict(data or {})
        timeout = payload.get("timeout_seconds")
        return cls(
            profile=str(payload.get("profile") or profile or "core"),
            run_id=(str(payload["run_id"]) if payload.get("run_id") else None),
            trace_id=(str(payload["trace_id"]) if payload.get("trace_id") else None),
            context_id=(str(payload["context_id"]) if payload.get("context_id") else context_id),
            timeout_seconds=(float(timeout) if timeout is not None and timeout != "" else None),
            max_retries=int(payload.get("max_retries") or 0),
            idempotency_key=(
                str(payload["idempotency_key"]) if payload.get("idempotency_key") else None
            ),
            allow_dangerous=bool(payload.get("allow_dangerous", True)),
            expected_head_sha=(
                str(payload["expected_head_sha"]) if payload.get("expected_head_sha") else None
            ),
        )


@dataclass
class ExecutionError:
    code: str
    message: str
    retryable: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass
class ExecutionResult:
    ok: bool
    connection_id: str
    action: str
    integration_id: str
    toolkit: str
    identity: ActorIdentity
    run_id: str
    trace_id: str
    result: Any = None
    error: ExecutionError | None = None
    audit_id: int | None = None
    audit_recorded: bool = False
    duration_ms: float = 0.0
    attempts: int = 1
    idempotency_replay: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "ok": self.ok,
            "connection_id": self.connection_id,
            "action": self.action,
            "capability_id": self.action,
            "connector_id": self.integration_id,
            "integration_id": self.integration_id,
            "toolkit": self.toolkit,
            "identity": self.identity.as_dict(),
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "result": self.result,
            "error": self.error.as_dict() if self.error else None,
            "audit_id": self.audit_id,
            "audit_recorded": self.audit_recorded,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "idempotency_replay": self.idempotency_replay,
        }
        payload.update(self.extra)
        return payload


def new_ids(policy: PolicyContext) -> tuple[str, str]:
    run_id = (policy.run_id or "").strip() or str(uuid.uuid4())
    trace_id = (policy.trace_id or "").strip() or run_id
    return run_id, trace_id


def action_is_dangerous(action: str, *, mutation: bool = False) -> bool:  # noqa: ARG001
    tokens = {part.lower() for part in action.split(".") if part}
    return bool(tokens & _DANGEROUS_TOKENS)


def validate_action_input(schema: dict[str, Any] | None, payload: dict[str, Any]) -> None:
    if not schema:
        return
    try:
        Draft202012Validator(schema).validate(payload)
    except JsonSchemaError as exc:
        raise ConnectorCapabilityError(f"input failed schema validation: {exc.message}") from exc


def run_with_timeout(func: Any, timeout_seconds: float | None) -> Any:
    if timeout_seconds is None:
        return func()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func)
        try:
            return future.result(timeout=float(timeout_seconds))
        except FuturesTimeout as exc:
            future.cancel()
            raise ConnectorUnavailableError(
                f"action timed out after {timeout_seconds}s",
                code="timeout",
            ) from exc


def is_retryable(exc: BaseException) -> bool:
    code = getattr(exc, "code", "")
    return code in _RETRYABLE


def input_fingerprint(connection_id: str, action: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"connection": connection_id, "action": action, "input": payload},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _quiet_close(conn: sqlite3.Connection) -> None:
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _is_usable(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
        return True
    except sqlite3.Error:
        return False


def _get_db() -> sqlite3.Connection:
    global _db_cache, _db_path_cache
    db_path = str(load_settings().resolved_db_path)
    if _db_cache is not None:
        if _db_path_cache == db_path and Path(db_path).exists() and _is_usable(_db_cache):
            return _db_cache
        _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_IDEMPOTENCY_SCHEMA)
    conn.commit()
    _db_cache = conn
    _db_path_cache = db_path
    return conn


def reset_idempotency_cache() -> None:
    global _db_cache, _db_path_cache
    with _lock:
        if _db_cache is not None:
            _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None


def lookup_idempotency(key: str, fingerprint: str) -> dict[str, Any] | None:
    with _lock:
        row = (
            _get_db()
            .execute(
                "SELECT fingerprint, result_json FROM execution_idempotency WHERE idempotency_key = ?",
                (key,),
            )
            .fetchone()
        )
    if row is None:
        return None
    if str(row["fingerprint"]) != fingerprint:
        raise ConnectorCapabilityError(
            "idempotency key reused with different action input",
        )
    return json.loads(str(row["result_json"]))


def store_idempotency(key: str, fingerprint: str, result: dict[str, Any]) -> None:
    with _lock:
        db = _get_db()
        db.execute(
            """INSERT OR REPLACE INTO execution_idempotency
               (idempotency_key, fingerprint, result_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (key, fingerprint, json.dumps(result, default=str), time.time()),
        )
        db.commit()
