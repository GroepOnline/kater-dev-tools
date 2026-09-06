"""Authoritative agent-session work and event transport.

Sessions remain ``remote_contexts`` rows. This module stores NL work and
Kater-neutral events keyed by ``context_id`` — not a second session identity.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kater.authgate import RequestIdentity, capability_allowed
from kater.capabilities.audit import record_capability_audit
from kater.control_plane import contexts as remote_contexts
from kater.control_plane.models import AgentState
from kater.control_plane.state import AGENT_STATE_MACHINE, InvalidTransition
from kater.settings import load_settings

CAP_CONTINUE = "kater.session.continue"
CAP_SUBMIT = "kater.session.work.submit"
CAP_CANCEL = "kater.session.work.cancel"
CAP_TRANSITION = "kater.session.work.transition"
CAP_EVENTS_READ = "kater.session.events.read"
CAP_EVENTS_APPEND = "kater.session.events.append"

KNOWN_EVENT_TYPES = frozenset(
    {
        "session.continued",
        "work.submitted",
        "work.state",
        "work.progress",
        "work.cancelled",
        "event.unknown",
    }
)
UNKNOWN_EVENT_TYPE = "event.unknown"
PROMPT_MAX_CHARS = 32_768
WAIT_SLICE_SECONDS = 0.05

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS agent_session_work (
    work_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    state TEXT NOT NULL,
    correlation_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    cancelled_at REAL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_agent_session_work_context
    ON agent_session_work(context_id, created_at);

CREATE TABLE IF NOT EXISTS agent_session_events (
    event_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    work_id TEXT,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    provider TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_session_events_context_seq
    ON agent_session_events(context_id, seq);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_session_events_context_seq_unique
    ON agent_session_events(context_id, seq);
"""

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None


class SessionTransportError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True, slots=True)
class WorkRecord:
    work_id: str
    context_id: str
    principal_id: str
    prompt: str
    state: AgentState
    correlation: dict[str, Any]
    created_at: float
    updated_at: float
    cancelled_at: float | None
    completed_at: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "context_id": self.context_id,
            "principal_id": self.principal_id,
            "prompt": self.prompt,
            "state": self.state.value,
            "correlation": dict(self.correlation),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cancelled_at": self.cancelled_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_id: str
    context_id: str
    work_id: str | None
    seq: int
    type: str
    payload: dict[str, Any]
    provider: str | None
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "context_id": self.context_id,
            "work_id": self.work_id,
            "seq": self.seq,
            "type": self.type,
            "payload": dict(self.payload),
            "provider": self.provider,
            "created_at": self.created_at,
        }


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
    conn.executescript(_SCHEMA)
    conn.commit()
    _db_cache = conn
    _db_path_cache = db_path
    return conn


def reset_cache() -> None:
    """Drop the cached connection (tests swap the working directory)."""
    global _db_cache, _db_path_cache
    with _lock:
        if _db_cache is not None:
            _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None


def _new_id(prefix: str) -> str:
    return prefix + secrets.token_hex(16)


def _json_obj(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _work_from_row(row: sqlite3.Row) -> WorkRecord:
    return WorkRecord(
        work_id=str(row["work_id"]),
        context_id=str(row["context_id"]),
        principal_id=str(row["principal_id"]),
        prompt=str(row["prompt"]),
        state=AgentState(str(row["state"])),
        correlation=_json_obj(row["correlation_json"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        cancelled_at=None if row["cancelled_at"] is None else float(row["cancelled_at"]),
        completed_at=None if row["completed_at"] is None else float(row["completed_at"]),
    )


def _event_from_row(row: sqlite3.Row) -> EventRecord:
    provider = row["provider"]
    return EventRecord(
        event_id=str(row["event_id"]),
        context_id=str(row["context_id"]),
        work_id=None if row["work_id"] is None else str(row["work_id"]),
        seq=int(row["seq"]),
        type=str(row["type"]),
        payload=_json_obj(row["payload_json"]),
        provider=None if provider is None or provider == "" else str(provider),
        created_at=float(row["created_at"]),
    )


def _owns(identity: RequestIdentity, record: remote_contexts.ContextRecord) -> bool:
    if identity.principal_id is None:
        return True
    return record.principal_id == identity.principal_id


def _normalize_event_type(raw: str) -> tuple[str, dict[str, Any]]:
    name = str(raw or "").strip()
    extra: dict[str, Any] = {}
    if not name:
        raise SessionTransportError(400, "event type is required")
    if name in KNOWN_EVENT_TYPES:
        return name, extra
    extra["original_type"] = name
    return UNKNOWN_EVENT_TYPE, extra


def _explicit_provider(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SessionTransportError(400, "provider must be a string")
    cleaned = value.strip()
    return cleaned or None


def _correlation(context_id: str, incoming: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(incoming or {})
    claimed = payload.get("katerContextId")
    if claimed is not None and str(claimed) != context_id:
        raise SessionTransportError(400, "katerContextId must match context_id")
    payload["katerContextId"] = context_id
    return payload


def _gate_context(
    identity: RequestIdentity,
    context_id: str,
    *,
    capability: str,
    write: bool,
    audit: bool,
) -> remote_contexts.ContextRecord:
    if not capability_allowed(capability, identity.allowed_capabilities):
        if audit:
            record_capability_audit(
                capability_id=capability,
                outcome="denied",
                principal_id=identity.principal_id,
                context_id=context_id,
                reason="capability_denied",
            )
        raise SessionTransportError(403, f"Capability not allowed: {capability}")
    record = remote_contexts.get_context(context_id)
    if record is None or not _owns(identity, record):
        raise SessionTransportError(404, "context not found")
    if write and not record.is_active():
        raise SessionTransportError(409, "context is not active")
    if audit:
        record_capability_audit(
            capability_id=capability,
            outcome="allowed",
            principal_id=identity.principal_id,
            context_id=context_id,
            profile=record.profile,
        )
    return record


def _next_seq(db: sqlite3.Connection, context_id: str) -> int:
    row = db.execute(
        "SELECT COALESCE(MAX(seq), 0) AS seq FROM agent_session_events WHERE context_id = ?",
        (context_id,),
    ).fetchone()
    return int(row["seq"]) + 1


def _insert_event(
    db: sqlite3.Connection,
    *,
    context_id: str,
    work_id: str | None,
    event_type: str,
    payload: dict[str, Any],
    provider: str | None,
) -> EventRecord:
    now = time.time()
    record = EventRecord(
        event_id=_new_id("aevt_"),
        context_id=context_id,
        work_id=work_id,
        seq=_next_seq(db, context_id),
        type=event_type,
        payload=dict(payload),
        provider=provider,
        created_at=now,
    )
    db.execute(
        """INSERT INTO agent_session_events (
               event_id, context_id, work_id, seq, type, payload_json, provider, created_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.event_id,
            record.context_id,
            record.work_id,
            record.seq,
            record.type,
            json.dumps(record.payload, ensure_ascii=False),
            record.provider,
            record.created_at,
        ),
    )
    return record


def _get_work_unlocked(db: sqlite3.Connection, work_id: str) -> WorkRecord | None:
    row = db.execute(
        "SELECT * FROM agent_session_work WHERE work_id = ?",
        (work_id,),
    ).fetchone()
    return None if row is None else _work_from_row(row)


def _apply_state(
    db: sqlite3.Connection,
    work: WorkRecord,
    target: AgentState,
    *,
    reason: str | None,
) -> tuple[WorkRecord, EventRecord]:
    try:
        AGENT_STATE_MACHINE.transition(work.state, target, reason=reason)
    except InvalidTransition as exc:
        raise SessionTransportError(409, str(exc)) from exc
    now = time.time()
    cancelled_at = work.cancelled_at
    completed_at = work.completed_at
    if target is AgentState.CANCELLED:
        cancelled_at = now
    if target in {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}:
        completed_at = now
    db.execute(
        """UPDATE agent_session_work
           SET state = ?, updated_at = ?, cancelled_at = ?, completed_at = ?
           WHERE work_id = ?""",
        (target.value, now, cancelled_at, completed_at, work.work_id),
    )
    updated = WorkRecord(
        work_id=work.work_id,
        context_id=work.context_id,
        principal_id=work.principal_id,
        prompt=work.prompt,
        state=target,
        correlation=work.correlation,
        created_at=work.created_at,
        updated_at=now,
        cancelled_at=cancelled_at,
        completed_at=completed_at,
    )
    event_type = "work.cancelled" if target is AgentState.CANCELLED else "work.state"
    event = _insert_event(
        db,
        context_id=work.context_id,
        work_id=work.work_id,
        event_type=event_type,
        payload={"state": target.value, "reason": reason},
        provider=None,
    )
    return updated, event


def _latest_work(db: sqlite3.Connection, context_id: str) -> WorkRecord | None:
    row = db.execute(
        """SELECT * FROM agent_session_work
           WHERE context_id = ? ORDER BY created_at DESC, work_id DESC LIMIT 1""",
        (context_id,),
    ).fetchone()
    return None if row is None else _work_from_row(row)


def session_projection(
    identity: RequestIdentity,
    context_id: str,
) -> dict[str, Any]:
    record = _gate_context(
        identity, context_id, capability=CAP_EVENTS_READ, write=False, audit=False
    )
    with _lock:
        db = _get_db()
        latest = _latest_work(db, context_id)
        total_row = db.execute(
            "SELECT COUNT(*) AS n FROM agent_session_work WHERE context_id = ?",
            (context_id,),
        ).fetchone()
        total = int(total_row["n"])
    agent_state = latest.state.value if latest is not None else AgentState.IDLE.value
    return {
        "context": record.to_dict(),
        "agent_state": agent_state,
        "correlation": {"katerContextId": context_id},
        "active_work": None if latest is None else latest.to_dict(),
        "work_total": total,
    }


def continue_session(
    identity: RequestIdentity,
    context_id: str,
) -> dict[str, Any]:
    record = _gate_context(
        identity, context_id, capability=CAP_CONTINUE, write=True, audit=True
    )
    with _lock:
        db = _get_db()
        event = _insert_event(
            db,
            context_id=record.context_id,
            work_id=None,
            event_type="session.continued",
            payload={"katerContextId": record.context_id},
            provider=None,
        )
        db.commit()
    projection = session_projection(identity, context_id)
    projection["event"] = event.to_dict()
    return projection


def submit_work(
    identity: RequestIdentity,
    context_id: str,
    prompt: str,
    *,
    correlation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = str(prompt or "")
    if not text.strip():
        raise SessionTransportError(400, "prompt is required")
    if len(text) > PROMPT_MAX_CHARS:
        raise SessionTransportError(400, f"prompt exceeds {PROMPT_MAX_CHARS} characters")
    record = _gate_context(
        identity, context_id, capability=CAP_SUBMIT, write=True, audit=True
    )
    corr = _correlation(record.context_id, correlation)
    now = time.time()
    work = WorkRecord(
        work_id=_new_id("awrk_"),
        context_id=record.context_id,
        principal_id=record.principal_id,
        prompt=text,
        state=AgentState.IDLE,
        correlation=corr,
        created_at=now,
        updated_at=now,
        cancelled_at=None,
        completed_at=None,
    )
    with _lock:
        db = _get_db()
        db.execute(
            """INSERT INTO agent_session_work (
                   work_id, context_id, principal_id, prompt, state, correlation_json,
                   created_at, updated_at, cancelled_at, completed_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                work.work_id,
                work.context_id,
                work.principal_id,
                work.prompt,
                work.state.value,
                json.dumps(work.correlation, ensure_ascii=False),
                work.created_at,
                work.updated_at,
                None,
                None,
            ),
        )
        submitted = _insert_event(
            db,
            context_id=work.context_id,
            work_id=work.work_id,
            event_type="work.submitted",
            payload={"katerContextId": work.context_id},
            provider=None,
        )
        waiting, state_event = _apply_state(
            db, work, AgentState.WAITING, reason="handoff"
        )
        db.commit()
    return {
        "work": waiting.to_dict(),
        "events": [submitted.to_dict(), state_event.to_dict()],
        "correlation": dict(waiting.correlation),
        "agent_state": waiting.state.value,
    }


def list_work(identity: RequestIdentity, context_id: str) -> dict[str, Any]:
    _gate_context(identity, context_id, capability=CAP_EVENTS_READ, write=False, audit=False)
    with _lock:
        rows = (
            _get_db()
            .execute(
                """SELECT * FROM agent_session_work
                   WHERE context_id = ? ORDER BY created_at DESC, work_id DESC""",
                (context_id,),
            )
            .fetchall()
        )
    items = [_work_from_row(row).to_dict() for row in rows]
    return {"total": len(items), "work": items}


def get_work(identity: RequestIdentity, context_id: str, work_id: str) -> dict[str, Any]:
    _gate_context(identity, context_id, capability=CAP_EVENTS_READ, write=False, audit=False)
    with _lock:
        work = _get_work_unlocked(_get_db(), work_id)
    if work is None or work.context_id != context_id:
        raise SessionTransportError(404, "work not found")
    return work.to_dict()


def cancel_work(
    identity: RequestIdentity,
    context_id: str,
    work_id: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    _gate_context(identity, context_id, capability=CAP_CANCEL, write=True, audit=True)
    with _lock:
        db = _get_db()
        work = _get_work_unlocked(db, work_id)
        if work is None or work.context_id != context_id:
            raise SessionTransportError(404, "work not found")
        updated, event = _apply_state(
            db, work, AgentState.CANCELLED, reason=reason or "cancelled"
        )
        db.commit()
    return {"work": updated.to_dict(), "event": event.to_dict()}


def transition_work(
    identity: RequestIdentity,
    context_id: str,
    work_id: str,
    state: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    try:
        target = AgentState(state)
    except ValueError as exc:
        raise SessionTransportError(400, f"unknown agent state: {state}") from exc
    _gate_context(identity, context_id, capability=CAP_TRANSITION, write=True, audit=True)
    with _lock:
        db = _get_db()
        work = _get_work_unlocked(db, work_id)
        if work is None or work.context_id != context_id:
            raise SessionTransportError(404, "work not found")
        updated, event = _apply_state(db, work, target, reason=reason)
        db.commit()
    return {"work": updated.to_dict(), "event": event.to_dict()}


def append_event(
    identity: RequestIdentity,
    context_id: str,
    event_type: str,
    *,
    work_id: str | None = None,
    payload: dict[str, Any] | None = None,
    provider: Any = None,
) -> dict[str, Any]:
    _gate_context(identity, context_id, capability=CAP_EVENTS_APPEND, write=True, audit=True)
    stored_type, extra = _normalize_event_type(event_type)
    body = dict(payload or {})
    body.update(extra)
    explicit = _explicit_provider(provider)
    with _lock:
        db = _get_db()
        bound_work: str | None = None
        if work_id:
            work = _get_work_unlocked(db, work_id)
            if work is None or work.context_id != context_id:
                raise SessionTransportError(404, "work not found")
            bound_work = work.work_id
            if stored_type == "work.state" and "state" in body:
                try:
                    target = AgentState(str(body["state"]))
                except ValueError as exc:
                    raise SessionTransportError(
                        400, f"unknown agent state: {body['state']}"
                    ) from exc
                reason_raw = body.get("reason")
                reason = None if reason_raw is None else str(reason_raw)
                updated, event = _apply_state(db, work, target, reason=reason)
                db.commit()
                return {"event": event.to_dict(), "work": updated.to_dict()}
        event = _insert_event(
            db,
            context_id=context_id,
            work_id=bound_work,
            event_type=stored_type,
            payload=body,
            provider=explicit,
        )
        db.commit()
    return {"event": event.to_dict()}


def list_events(
    identity: RequestIdentity,
    context_id: str,
    *,
    after_seq: int = 0,
    limit: int = 100,
    wait_ms: int = 0,
) -> dict[str, Any]:
    _gate_context(identity, context_id, capability=CAP_EVENTS_READ, write=False, audit=False)
    after = max(0, int(after_seq))
    lim = max(1, min(int(limit), 1000))
    wait = max(0, int(wait_ms))
    deadline = time.monotonic() + (wait / 1000.0)
    events: list[EventRecord] = []
    while True:
        with _lock:
            rows = (
                _get_db()
                .execute(
                    """SELECT * FROM agent_session_events
                       WHERE context_id = ? AND seq > ?
                       ORDER BY seq ASC LIMIT ?""",
                    (context_id, after, lim),
                )
                .fetchall()
            )
        events = [_event_from_row(row) for row in rows]
        if events or wait == 0 or time.monotonic() >= deadline:
            break
        time.sleep(min(WAIT_SLICE_SECONDS, max(deadline - time.monotonic(), 0.0)))
        if time.monotonic() >= deadline:
            break
    next_seq = events[-1].seq if events else after
    return {
        "context_id": context_id,
        "katerContextId": context_id,
        "after_seq": after,
        "next_seq": next_seq,
        "total": len(events),
        "events": [item.to_dict() for item in events],
    }


def events_as_sse(payload: dict[str, Any]) -> bytes:
    chunks: list[str] = []
    for event in payload.get("events") or []:
        chunks.append(f"id: {event['seq']}\n")
        chunks.append(f"event: {event['type']}\n")
        chunks.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
    if not chunks:
        chunks.append("event: session.idle\n")
        chunks.append(
            "data: "
            + json.dumps(
                {
                    "context_id": payload.get("context_id"),
                    "katerContextId": payload.get("katerContextId"),
                    "next_seq": payload.get("next_seq", 0),
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )
    return "".join(chunks).encode("utf-8")
