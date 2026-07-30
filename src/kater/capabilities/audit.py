"""Append-only audit log for capability invocations.

Table ownership lives in migration v6 (``capability_audit``). The
``CREATE IF NOT EXISTS`` bootstrap below keeps unit tests and early
startup safe when migrate has not run yet.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from kater.settings import load_settings

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS capability_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    capability_id TEXT NOT NULL,
    principal_id TEXT,
    context_id TEXT,
    outcome TEXT NOT NULL,
    reason TEXT,
    duration_ms REAL,
    profile TEXT
);

CREATE INDEX IF NOT EXISTS idx_capability_audit_ts ON capability_audit(timestamp);
CREATE INDEX IF NOT EXISTS idx_capability_audit_cap ON capability_audit(capability_id);
"""

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None

VALID_OUTCOMES = frozenset({"allowed", "denied", "error"})



def _quiet_close(conn: sqlite3.Connection) -> None:
    """Close a SQLite connection while suppressing SQLite errors."""
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _is_usable(conn: sqlite3.Connection) -> bool:
    """Check whether a SQLite connection responds successfully to a simple query.

    Parameters:
        conn (sqlite3.Connection): The connection to check.

    Returns:
        bool: `True` if the connection responds successfully, `False` otherwise.
    """
    try:
        conn.execute("SELECT 1")
        return True
    except sqlite3.Error:
        return False


def _get_db() -> sqlite3.Connection:
    """
    Get the configured SQLite database connection, creating and initializing it when necessary.

    Returns:
        sqlite3.Connection: The cached or newly initialized database connection.
    """
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
    """Clear the cached database connection and its associated path."""
    global _db_cache, _db_path_cache
    with _lock:
        if _db_cache is not None:
            _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None


def record_capability_audit(
    *,
    capability_id: str,
    outcome: str,
    principal_id: str | None = None,
    context_id: str | None = None,
    reason: str | None = None,
    duration_ms: float | None = None,
    profile: str | None = None,
    timestamp: float | None = None,
) -> int:
    """
    Record an audit entry for a capability invocation.

    Parameters:
        capability_id (str): Identifier of the invoked capability.
        outcome (str): Invocation outcome: ``"allowed"``, ``"denied"``, or
            ``"error"``.
        timestamp (float | None): Event timestamp, or the current time when omitted.

    Returns:
        int: ID of the newly inserted audit entry.

    Raises:
        ValueError: If ``capability_id`` is empty or ``outcome`` is invalid.
    """
    cap = str(capability_id or "").strip()
    if not cap:
        raise ValueError("capability_id is required")
    result = str(outcome or "").strip().lower()
    if result not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    stamp = float(timestamp) if timestamp is not None else time.time()
    with _lock:
        db = _get_db()
        cur = db.execute(
            """INSERT INTO capability_audit
               (timestamp, capability_id, principal_id, context_id,
                outcome, reason, duration_ms, profile)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stamp,
                cap,
                principal_id,
                context_id,
                result,
                reason,
                duration_ms,
                profile,
            ),
        )
        db.commit()
        return int(cur.lastrowid) if cur.lastrowid is not None else 0


def query_capability_audit(
    *,
    capability_id: str | None = None,
    context_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Retrieve audit records in newest-first order, optionally filtered by capability or context.

    Parameters:
        capability_id (str | None): Restrict results to a capability identifier.
        context_id (str | None): Restrict results to a context identifier.
        limit (int): Maximum number of records to return, clamped to the range 1-1000.

    Returns:
        list[dict[str, Any]]: Matching audit records represented as dictionaries.
    """
    lim = max(1, min(int(limit), 1000))
    clauses: list[str] = []
    params: list[Any] = []
    if capability_id:
        clauses.append("capability_id = ?")
        params.append(capability_id)
    if context_id:
        clauses.append("context_id = ?")
        params.append(context_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        f"SELECT * FROM capability_audit {where} ORDER BY id DESC LIMIT ?"  # noqa: S608
    )
    params.append(lim)
    with _lock:
        rows = _get_db().execute(query, params).fetchall()
    return [dict(row) for row in rows]


def clear_capability_audit() -> None:
    """
    Delete all capability audit records.

    Intended for use in tests.
    """
    with _lock:
        db = _get_db()
        db.execute("DELETE FROM capability_audit")
        db.commit()
