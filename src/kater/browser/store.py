"""SQLite persistence for browser sessions and the action audit trail.

Uses the same ``.kater/kater.db`` file and the same cached-connection pattern
as ``kater.storage``: one process-wide connection guarded by a lock, WAL mode,
a busy timeout, and a hard row cap on the append-only action log.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from kater.browser.models import ActionResult, BrowserSession, ProviderKind, SessionState
from kater.settings import load_settings

_log = logging.getLogger("kater.browser.store")

MAX_ACTION_ROWS = 20_000
_PRUNE_EVERY = 200

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS browser_sessions (
    session_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    state TEXT NOT NULL,
    label TEXT,
    profile TEXT NOT NULL DEFAULT 'core',
    created_at REAL NOT NULL,
    last_used_at REAL NOT NULL,
    expires_at REAL NOT NULL DEFAULT 0,
    current_url TEXT,
    title TEXT,
    error TEXT,
    viewport_width INTEGER NOT NULL DEFAULT 1280,
    viewport_height INTEGER NOT NULL DEFAULT 800
);

CREATE INDEX IF NOT EXISTS idx_browser_sessions_state ON browser_sessions(state);

CREATE TABLE IF NOT EXISTS browser_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 1,
    started_at REAL NOT NULL,
    duration_ms REAL NOT NULL DEFAULT 0,
    url TEXT,
    error TEXT,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_browser_actions_session ON browser_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_browser_actions_started ON browser_actions(started_at);
"""

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None
_insert_counter = 0



def _get_db() -> sqlite3.Connection:
    """
    Get a usable SQLite connection for the configured database path.

    Returns:
        sqlite3.Connection: The cached or newly initialized database connection.
    """
    global _db_cache, _db_path_cache
    db_path = str(load_settings().resolved_db_path)
    if _db_cache is not None:
        # The file itself has to still be there: an unlinked database keeps
        # answering reads through the open handle while every write fails.
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
    """Clear the cached database connection and reset the action insert counter.

    This is intended for test scenarios that change the database location.
    """
    global _db_cache, _db_path_cache, _insert_counter
    with _lock:
        if _db_cache is not None:
            _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None
        _insert_counter = 0


def upsert_session(session: BrowserSession) -> None:
    """Insert a new browser session or update the existing record with the same session ID.

    Parameters:
        session (BrowserSession): Session data to persist.
    """
    with _lock:
        db = _get_db()
        db.execute(
            """INSERT INTO browser_sessions
               (session_id, provider, state, label, profile, created_at, last_used_at,
                expires_at, current_url, title, error, viewport_width, viewport_height)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 provider = excluded.provider,
                 state = excluded.state,
                 label = excluded.label,
                 profile = excluded.profile,
                 last_used_at = excluded.last_used_at,
                 expires_at = excluded.expires_at,
                 current_url = excluded.current_url,
                 title = excluded.title,
                 error = excluded.error,
                 viewport_width = excluded.viewport_width,
                 viewport_height = excluded.viewport_height""",
            (
                session.session_id,
                session.provider.value,
                session.state.value,
                session.label,
                session.profile,
                session.created_at,
                session.last_used_at,
                session.expires_at,
                session.current_url,
                session.title,
                session.error,
                session.viewport_width,
                session.viewport_height,
            ),
        )
        db.commit()


def get_session(session_id: str) -> BrowserSession | None:
    """
    Retrieve a stored browser session by its identifier.

    Parameters:
        session_id (str): Identifier of the session to retrieve.

    Returns:
        BrowserSession | None: The matching session, or `None` if no session exists.
    """
    with _lock:
        row = (
            _get_db()
            .execute("SELECT * FROM browser_sessions WHERE session_id = ?", (session_id,))
            .fetchone()
        )
    return _row_to_session(row) if row is not None else None


def list_sessions(limit: int = 100) -> list[BrowserSession]:
    """
    List stored browser sessions in newest-first order.

    Parameters:
        limit (int): Maximum number of sessions to return, capped between 1 and 1000.

    Returns:
        list[BrowserSession]: The matching sessions.
    """
    capped = max(1, min(int(limit), 1000))
    with _lock:
        rows = (
            _get_db()
            .execute(
                "SELECT * FROM browser_sessions ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (capped,),
            )
            .fetchall()
        )
    return [_row_to_session(row) for row in rows]


def delete_session(session_id: str) -> bool:
    """Delete a session and its action rows; True when the session existed."""
    with _lock:
        db = _get_db()
        cursor = db.execute("DELETE FROM browser_sessions WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM browser_actions WHERE session_id = ?", (session_id,))
        db.commit()
        return cursor.rowcount > 0


def record_action(result: ActionResult, *, detail: dict[str, Any] | None = None) -> int:
    """
    Append an action result to the browser action audit trail.

    Parameters:
        result (ActionResult): Action result to record.
        detail (dict[str, Any] | None): Optional additional action metadata.

    Returns:
        int: ID of the newly recorded audit row, or 0 if no row ID is available.
    """
    global _insert_counter
    with _lock:
        db = _get_db()
        cursor = db.execute(
            """INSERT INTO browser_actions
               (session_id, kind, ok, started_at, duration_ms, url, error, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.session_id,
                result.kind.value,
                1 if result.ok else 0,
                result.started_at,
                result.duration_ms,
                result.url,
                result.error,
                json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
            ),
        )
        _insert_counter += 1
        if _insert_counter % _PRUNE_EVERY == 0:
            _prune_locked(db, MAX_ACTION_ROWS)
        db.commit()
        return int(cursor.lastrowid) if cursor.lastrowid is not None else 0


def list_actions(session_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List browser action audit records in newest-first order.

    Parameters:
        session_id (str | None): Restrict results to a specific session when provided.
        limit (int): Maximum number of records to return, capped at 5,000.

    Returns:
        list[dict[str, Any]]: Audit records ordered from newest to oldest.
    """
    capped = max(1, min(int(limit), 5000))
    with _lock:
        db = _get_db()
        if session_id is not None:
            rows = db.execute(
                """SELECT * FROM browser_actions WHERE session_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (session_id, capped),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM browser_actions ORDER BY id DESC LIMIT ?", (capped,)
            ).fetchall()
    return [_row_to_action(row) for row in rows]


def count_actions(session_id: str | None = None) -> int:
    """Count recorded browser actions, optionally restricted to a session.

    Parameters:
        session_id (str | None): Session identifier used to filter the count.

    Returns:
        int: The number of matching browser actions.
    """
    with _lock:
        db = _get_db()
        if session_id is not None:
            row = db.execute(
                "SELECT COUNT(*) AS c FROM browser_actions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) AS c FROM browser_actions").fetchone()
    return int(row["c"]) if row else 0


def prune_actions(max_rows: int = MAX_ACTION_ROWS) -> int:
    """
    Remove the oldest browser action records until at most the specified number remain.

    Parameters:
        max_rows (int): Maximum number of action records to retain.

    Returns:
        int: Number of action records removed.
    """
    with _lock:
        db = _get_db()
        removed = _prune_locked(db, max_rows)
        db.commit()
    return removed


def _prune_locked(db: sqlite3.Connection, max_rows: int) -> int:
    """
    Remove the oldest browser action records until the table contains at most the specified number
        of rows.

    Parameters:
        db (sqlite3.Connection): Database connection containing the browser action records.
        max_rows (int): Maximum number of action records to retain.

    Returns:
        int: Number of records removed.
    """
    keep = max(0, int(max_rows))
    row = db.execute("SELECT COUNT(*) AS c FROM browser_actions").fetchone()
    count = int(row["c"]) if row else 0
    if count <= keep:
        return 0
    excess = count - keep
    db.execute(
        """DELETE FROM browser_actions WHERE id IN (
               SELECT id FROM browser_actions ORDER BY id ASC LIMIT ?)""",
        (excess,),
    )
    _log.info("pruned %d browser action rows (kept cap %d)", excess, keep)
    return excess


def _row_to_session(row: sqlite3.Row) -> BrowserSession:
    """
    Convert a database row into a browser session.
    """
    return BrowserSession(
        session_id=row["session_id"],
        provider=_enum(ProviderKind, row["provider"], ProviderKind.LOCAL),
        state=_enum(SessionState, row["state"], SessionState.FAILED),
        created_at=float(row["created_at"]),
        last_used_at=float(row["last_used_at"]),
        expires_at=float(row["expires_at"] or 0.0),
        current_url=row["current_url"],
        title=row["title"],
        label=row["label"],
        profile=row["profile"] or "core",
        viewport_width=int(row["viewport_width"]),
        viewport_height=int(row["viewport_height"]),
        error=row["error"],
    )


def _row_to_action(row: sqlite3.Row) -> dict[str, Any]:
    """
    Convert an action database row into a typed action dictionary.

    Parameters:
        row (sqlite3.Row): Database row containing an action record.

    Returns:
        dict[str, Any]: Action fields with numeric values normalized and JSON
        details parsed into a dictionary when valid.
    """
    detail_raw = row["detail"]
    detail: dict[str, Any] | None = None
    if detail_raw:
        try:
            parsed = json.loads(detail_raw)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        detail = parsed if isinstance(parsed, dict) else None
    return {
        "id": int(row["id"]),
        "session_id": row["session_id"],
        "kind": row["kind"],
        "ok": bool(row["ok"]),
        "started_at": float(row["started_at"]),
        "duration_ms": float(row["duration_ms"]),
        "url": row["url"],
        "error": row["error"],
        "detail": detail,
    }


def _enum(enum_cls: Any, raw: Any, fallback: Any) -> Any:
    """
    Convert a raw value to an enum member, using a fallback for invalid values.

    Parameters:
        enum_cls (Any): Enum class used for conversion.
        raw (Any): Value to convert.
        fallback (Any): Value returned when conversion fails.

    Returns:
        Any: The converted enum member or fallback value.
    """
    try:
        return enum_cls(raw)
    except ValueError:
        return fallback


def _is_usable(conn: sqlite3.Connection) -> bool:
    """Determine whether a SQLite connection can execute a query.

    Parameters:
        conn (sqlite3.Connection): The connection to check.

    Returns:
        bool: `true` if the connection is usable, `false` otherwise.
    """
    try:
        conn.execute("SELECT 1")
    except sqlite3.Error:
        return False
    return True


def _quiet_close(conn: sqlite3.Connection) -> None:
    """Close a SQLite connection while suppressing SQLite errors."""
    try:
        conn.close()
    except sqlite3.Error:
        pass
