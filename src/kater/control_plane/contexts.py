"""Persistence and CRUD for remote execution contexts.

Table ownership lives in migration v4 (``remote_contexts``). The
``CREATE IF NOT EXISTS`` bootstrap below keeps unit tests and early
startup safe when migrate has not run yet.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kater.control_plane.models import RemoteContext
from kater.settings import load_settings

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS remote_contexts (
    context_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    label TEXT,
    profile TEXT NOT NULL DEFAULT 'core',
    scopes TEXT NOT NULL DEFAULT '[]',
    repository TEXT,
    environment TEXT,
    allowed_capabilities TEXT NOT NULL DEFAULT '[]',
    expires_at REAL,
    revoked_at REAL,
    created_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_remote_contexts_principal ON remote_contexts(principal_id);
"""

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None


@dataclass(frozen=True, slots=True)
class ContextRecord:
    """Stored remote context including fields beyond :class:`RemoteContext`."""

    context_id: str
    principal_id: str
    scopes: frozenset[str]
    created_at: datetime
    expires_at: datetime | None = None
    repository: str | None = None
    environment: str | None = None
    label: str | None = None
    profile: str = "core"
    allowed_capabilities: frozenset[str] = field(default_factory=frozenset)
    revoked_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_remote_context(self) -> RemoteContext:
        return RemoteContext(
            context_id=self.context_id,
            principal_id=self.principal_id,
            scopes=self.scopes,
            created_at=self.created_at,
            expires_at=self.expires_at,
            repository=self.repository,
            environment=self.environment,
        )

    def is_active(self, now: datetime | None = None) -> bool:
        if self.revoked_at is not None:
            return False
        return self.as_remote_context().is_active(now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "principal_id": self.principal_id,
            "label": self.label,
            "profile": self.profile,
            "scopes": sorted(self.scopes),
            "repository": self.repository,
            "environment": self.environment,
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "expires_at": self.expires_at.timestamp() if self.expires_at else None,
            "revoked_at": self.revoked_at.timestamp() if self.revoked_at else None,
            "created_at": self.created_at.timestamp(),
            "metadata": dict(self.metadata),
            "active": self.is_active(),
        }


def _resolve_db_path() -> Path:
    configured = load_settings().db_path
    if "/" in configured or configured.startswith("."):
        return Path(configured).expanduser()
    return Path.cwd() / configured


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
    db_path = str(_resolve_db_path())
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


def _new_context_id() -> str:
    return "rctx_" + secrets.token_hex(16)


def _ts(value: datetime | None) -> float | None:
    return value.timestamp() if value is not None else None


def _dt(value: float | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value is not None else None


def _json_list(values: frozenset[str] | list[str] | tuple[str, ...]) -> str:
    return json.dumps(sorted(values))


def _parse_str_set(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(data, list):
        return frozenset()
    return frozenset(str(item) for item in data)


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _row_to_record(row: sqlite3.Row) -> ContextRecord:
    return ContextRecord(
        context_id=str(row["context_id"]),
        principal_id=str(row["principal_id"]),
        label=row["label"],
        profile=str(row["profile"] or "core"),
        scopes=_parse_str_set(row["scopes"]),
        repository=row["repository"],
        environment=row["environment"],
        allowed_capabilities=_parse_str_set(row["allowed_capabilities"]),
        expires_at=_dt(row["expires_at"]),
        revoked_at=_dt(row["revoked_at"]),
        created_at=_dt(row["created_at"]) or datetime.fromtimestamp(0, tz=UTC),
        metadata=_parse_metadata(row["metadata"]),
    )


def _as_str_set(value: Any) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return frozenset(parts)
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(str(item) for item in value if str(item))
    raise ValueError("expected a list of strings")


def create_context(
    *,
    principal_id: str,
    label: str | None = None,
    profile: str = "core",
    scopes: frozenset[str] | list[str] | tuple[str, ...] | None = None,
    repository: str | None = None,
    environment: str | None = None,
    allowed_capabilities: frozenset[str] | list[str] | tuple[str, ...] | None = None,
    ttl_seconds: float | int | None = None,
    metadata: dict[str, Any] | None = None,
) -> ContextRecord:
    """Insert a new remote context and return the stored record."""
    principal = str(principal_id or "").strip()
    if not principal:
        raise ValueError("principal_id is required")
    profile_name = str(profile or "core").strip() or "core"
    scope_set = _as_str_set(scopes)
    capability_set = _as_str_set(allowed_capabilities)
    meta = dict(metadata or {})
    created = datetime.now(UTC)
    expires: datetime | None = None
    if ttl_seconds is not None:
        ttl = float(ttl_seconds)
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        expires = datetime.fromtimestamp(created.timestamp() + ttl, tz=UTC)

    context_id = _new_context_id()
    record = ContextRecord(
        context_id=context_id,
        principal_id=principal,
        label=str(label).strip() if label else None,
        profile=profile_name,
        scopes=scope_set,
        repository=str(repository).strip() if repository else None,
        environment=str(environment).strip() if environment else None,
        allowed_capabilities=capability_set,
        expires_at=expires,
        revoked_at=None,
        created_at=created,
        metadata=meta,
    )
    with _lock:
        db = _get_db()
        db.execute(
            """INSERT INTO remote_contexts (
                   context_id, principal_id, label, profile, scopes, repository,
                   environment, allowed_capabilities, expires_at, revoked_at,
                   created_at, metadata
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.context_id,
                record.principal_id,
                record.label,
                record.profile,
                _json_list(record.scopes),
                record.repository,
                record.environment,
                _json_list(record.allowed_capabilities),
                _ts(record.expires_at),
                None,
                record.created_at.timestamp(),
                json.dumps(record.metadata, ensure_ascii=False),
            ),
        )
        db.commit()
    return record


def get_context(context_id: str) -> ContextRecord | None:
    with _lock:
        row = (
            _get_db()
            .execute(
                "SELECT * FROM remote_contexts WHERE context_id = ?",
                (context_id,),
            )
            .fetchone()
        )
    return _row_to_record(row) if row else None


def list_contexts(
    *,
    principal_id: str | None = None,
    include_revoked: bool = False,
) -> list[ContextRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if principal_id:
        clauses.append("principal_id = ?")
        params.append(principal_id)
    if not include_revoked:
        clauses.append("revoked_at IS NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM remote_contexts {where} ORDER BY created_at DESC, context_id ASC"  # noqa: S608
    with _lock:
        rows = _get_db().execute(query, params).fetchall()
    return [_row_to_record(row) for row in rows]


def revoke_context(context_id: str, *, now: datetime | None = None) -> ContextRecord | None:
    """Soft-revoke a context. Returns the updated record, or None if missing."""
    stamp = (now or datetime.now(UTC)).timestamp()
    with _lock:
        db = _get_db()
        row = db.execute(
            "SELECT * FROM remote_contexts WHERE context_id = ?",
            (context_id,),
        ).fetchone()
        if row is None:
            return None
        if row["revoked_at"] is None:
            db.execute(
                "UPDATE remote_contexts SET revoked_at = ? WHERE context_id = ?",
                (stamp, context_id),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM remote_contexts WHERE context_id = ?",
                (context_id,),
            ).fetchone()
    return _row_to_record(row) if row else None


def purge_expired(*, now: datetime | None = None) -> int:
    """Hard-delete contexts past ``expires_at``. Returns the number removed."""
    stamp = (now or datetime.now(UTC)).timestamp()
    with _lock:
        db = _get_db()
        cursor = db.execute(
            """DELETE FROM remote_contexts
               WHERE expires_at IS NOT NULL AND expires_at < ?""",
            (stamp,),
        )
        db.commit()
        return int(cursor.rowcount)


def clear_contexts() -> None:
    """Delete all remote contexts (tests)."""
    with _lock:
        db = _get_db()
        db.execute("DELETE FROM remote_contexts")
        db.commit()
