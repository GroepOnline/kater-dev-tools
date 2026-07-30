"""SQLite persistence for automations.

Uses the shared ``.kater/kater.db`` file (``settings.db_path``) with the same
WAL / busy-timeout / cached-connection pattern as ``kater.browser.store``.
The table is owned by migration v3; ``CREATE IF NOT EXISTS`` keeps tests and
early bootstraps safe when migrate has not run yet.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from kater.automations.models import Automation
from kater.settings import load_settings

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    kind TEXT NOT NULL,
    schedule_seconds INTEGER NOT NULL DEFAULT 0,
    config TEXT NOT NULL DEFAULT '{}',
    last_run_at REAL,
    last_status TEXT,
    last_error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automations_enabled ON automations(enabled);

CREATE TABLE IF NOT EXISTS automation_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""

#: Marker recording that the built-in automations were seeded once.
DEFAULTS_SEEDED_KEY = "defaults_seeded"

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None





def _get_db() -> sqlite3.Connection:
    """
    Return a usable SQLite connection for the configured database.
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
    """Close and clear the cached database connection and path."""
    global _db_cache, _db_path_cache
    with _lock:
        if _db_cache is not None:
            _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None


def count() -> int:
    """Count the persisted automation records.

    Returns:
        int: The number of automation records.
    """
    with _lock:
        row = _get_db().execute("SELECT COUNT(*) AS c FROM automations").fetchone()
    return int(row["c"]) if row else 0


def get_meta(key: str) -> str | None:
    """Read a persisted store marker.

    Parameters:
        key (str): Marker name.

    Returns:
        str | None: The stored value, or `None` when the marker was never set.
    """
    with _lock:
        row = _get_db().execute(
            "SELECT value FROM automation_meta WHERE key = ?", (key,)
        ).fetchone()
    return str(row["value"]) if row else None


def set_meta(key: str, value: str = "1") -> None:
    """Persist a store marker.

    Parameters:
        key (str): Marker name.
        value (str): Marker value.
    """
    with _lock:
        db = _get_db()
        db.execute(
            """INSERT INTO automation_meta (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                              updated_at = excluded.updated_at""",
            (key, value, time.time()),
        )
        db.commit()


def list_automations() -> list[Automation]:
    """
    List all automations in creation order.

    Returns:
        list[Automation]: The stored automations ordered by creation time and ID.
    """
    with _lock:
        rows = (
            _get_db()
            .execute("SELECT * FROM automations ORDER BY created_at ASC, id ASC")
            .fetchall()
        )
    return [_row_to_automation(row) for row in rows]


def get_automation(automation_id: str) -> Automation | None:
    """Retrieve an automation by its identifier.

    Parameters:
        automation_id (str): Identifier of the automation to retrieve.

    Returns:
        Automation | None: The matching automation, or `None` if no record exists.
    """
    with _lock:
        row = (
            _get_db()
            .execute("SELECT * FROM automations WHERE id = ?", (automation_id,))
            .fetchone()
        )
    return _row_to_automation(row) if row is not None else None


def upsert(automation: Automation) -> Automation:
    """
    Insert or update an automation and return the persisted record.

    Parameters:
        automation (Automation): The automation record to persist.

    Returns:
        Automation: The persisted automation record.
    """
    with _lock:
        db = _get_db()
        db.execute(
            """INSERT INTO automations
               (id, name, enabled, kind, schedule_seconds, config,
                last_run_at, last_status, last_error, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 name = excluded.name,
                 enabled = excluded.enabled,
                 kind = excluded.kind,
                 schedule_seconds = excluded.schedule_seconds,
                 config = excluded.config,
                 last_run_at = excluded.last_run_at,
                 last_status = excluded.last_status,
                 last_error = excluded.last_error,
                 updated_at = excluded.updated_at""",
            (
                automation.id,
                automation.name,
                1 if automation.enabled else 0,
                automation.kind,
                int(automation.schedule_seconds),
                json.dumps(automation.config, ensure_ascii=False, default=str),
                automation.last_run_at,
                automation.last_status,
                automation.last_error,
                automation.created_at,
                automation.updated_at,
            ),
        )
        db.commit()
    loaded = get_automation(automation.id)
    if loaded is None:
        raise RuntimeError(f"automation {automation.id} missing after upsert")
    return loaded


def set_enabled(automation_id: str, enabled: bool) -> Automation | None:
    """
    Update an automation's enabled state.

    Parameters:
        automation_id (str): Identifier of the automation to update.
        enabled (bool): Whether the automation should be enabled.

    Returns:
        Automation | None: The updated automation, or `None` if no matching automation exists.
    """
    now = time.time()
    with _lock:
        db = _get_db()
        cursor = db.execute(
            """UPDATE automations
               SET enabled = ?, updated_at = ?
               WHERE id = ?""",
            (1 if enabled else 0, now, automation_id),
        )
        db.commit()
        if cursor.rowcount <= 0:
            return None
    return get_automation(automation_id)


def record_run(
    automation_id: str,
    *,
    ran_at: float,
    status: str,
    error: str | None,
) -> Automation | None:
    """
    Record the outcome of an automation run.

    Parameters:
        automation_id (str): Identifier of the automation to update.
        ran_at (float): Timestamp when the run occurred.
        status (str): Status of the run.
        error (str | None): Error details, or None when the run completed without an error.

    Returns:
        Automation | None: The updated automation, or None if the identifier does not exist.
    """
    with _lock:
        db = _get_db()
        cursor = db.execute(
            """UPDATE automations
               SET last_run_at = ?, last_status = ?, last_error = ?, updated_at = ?
               WHERE id = ?""",
            (ran_at, status, error, ran_at, automation_id),
        )
        db.commit()
        if cursor.rowcount <= 0:
            return None
    return get_automation(automation_id)


def delete(automation_id: str) -> bool:
    """
    Delete an automation by its identifier.

    Parameters:
        automation_id (str): Identifier of the automation to delete.

    Returns:
        bool: `True` if an automation was deleted, `False` if no matching automation was found.
    """
    with _lock:
        db = _get_db()
        cursor = db.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        db.commit()
        return cursor.rowcount > 0


def _row_to_automation(row: sqlite3.Row) -> Automation:
    """Convert a database row into an Automation instance.

    Parameters:
        row (sqlite3.Row): Database row containing automation fields.

    Returns:
        Automation: The reconstructed automation record.
    """
    raw_config = row["config"] or "{}"
    try:
        parsed = json.loads(raw_config)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = {}
    config = parsed if isinstance(parsed, dict) else {}
    return Automation(
        id=row["id"],
        name=row["name"],
        enabled=bool(row["enabled"]),
        kind=row["kind"],
        schedule_seconds=int(row["schedule_seconds"] or 0),
        config=config,
        last_run_at=float(row["last_run_at"]) if row["last_run_at"] is not None else None,
        last_status=row["last_status"],
        last_error=row["last_error"],
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def _is_usable(conn: sqlite3.Connection) -> bool:
    """Determine whether a SQLite connection can execute queries.

    Parameters:
        conn (sqlite3.Connection): The connection to check.

    Returns:
        bool: `True` if the connection executes a test query successfully, `False` otherwise.
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


# Keep a typed alias for callers that prefer a store object.
class AutomationStore:
    """Thin object facade over the module-level helpers (test seam)."""

    def count(self) -> int:
        """Count the stored automation records.

        Returns:
            int: The number of stored automations.
        """
        return count()

    def list(self) -> list[Automation]:
        """List all persisted automations in creation order."""
        return list_automations()

    def defaults_seeded(self) -> bool:
        """Report whether the built-in automations were already seeded once."""
        return get_meta(DEFAULTS_SEEDED_KEY) is not None

    def mark_defaults_seeded(self) -> None:
        """Persist the marker that stops the built-ins from being re-seeded."""
        set_meta(DEFAULTS_SEEDED_KEY)

    def get(self, automation_id: str) -> Automation | None:
        """Retrieve an automation by its identifier.

        Parameters:
            automation_id (str): Identifier of the automation to retrieve.

        Returns:
            Automation | None: The matching automation, or `None` if it does not exist.
        """
        return get_automation(automation_id)

    def upsert(self, automation: Automation) -> Automation:
        """Persist an automation record and return its stored representation.

        Parameters:
            automation (Automation): The automation record to create or update.

        Returns:
            Automation: The persisted automation record.
        """
        return upsert(automation)

    def set_enabled(self, automation_id: str, enabled: bool) -> Automation | None:
        """Set whether an automation is enabled.

        Parameters:
            automation_id (str): Identifier of the automation to update.
            enabled (bool): Whether the automation should be enabled.

        Returns:
            Automation | None: The updated automation, or `None` if no matching automation exists.
        """
        return set_enabled(automation_id, enabled)

    def record_run(
        self,
        automation_id: str,
        *,
        ran_at: float,
        status: str,
        error: str | None,
    ) -> Automation | None:
        """Record the outcome of an automation run.

        Parameters:
            automation_id (str): Identifier of the automation.
            ran_at (float): Timestamp when the run occurred.
            status (str): Result status of the run.
            error (str | None): Error message, if the run failed.

        Returns:
            Automation | None: The updated automation, or `None` if it does not exist.
        """
        return record_run(automation_id, ran_at=ran_at, status=status, error=error)

    def delete(self, automation_id: str) -> bool:
        """Delete an automation record by its identifier.

        Parameters:
            automation_id (str): Identifier of the automation to delete.

        Returns:
            bool: `True` if a record was deleted, `False` if no matching record was found.
        """
        return delete(automation_id)

    def reset_cache(self) -> None:
        """Close the cached database connection and clear its cached path."""
        reset_cache()
