"""SQLite persistence for automations.

Uses the shared ``.kater/kater.db`` file (``settings.db_path``) with the same
WAL / busy-timeout / cached-connection pattern as ``kater.browser.store``.
The tables are owned by migrations v3 / v7 / v12; ``CREATE IF NOT EXISTS`` keeps tests and
early bootstraps safe when migrate has not run yet.
"""

from __future__ import annotations

import builtins
import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from kater.automations.models import RUN_STATUSES, RUN_TRIGGERS, Automation, AutomationRun
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

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('ok', 'error', 'skipped', 'unknown')),
    error TEXT,
    "trigger" TEXT NOT NULL CHECK ("trigger" IN ('schedule', 'manual'))
);

CREATE INDEX IF NOT EXISTS idx_automation_runs_automation
    ON automation_runs(automation_id, started_at DESC, id DESC);
"""

#: Marker recording that the built-in automations were seeded once.
DEFAULTS_SEEDED_KEY = "defaults_seeded"

#: Run-history rows kept per automation; older rows are pruned by the janitor.
RUN_HISTORY_KEEP = 200

# History writes sit on the run path, so they give up on a locked database
# quickly instead of waiting out the connection's 10s busy timeout.
_HISTORY_BUSY_TIMEOUT_MS = 500
_DEFAULT_BUSY_TIMEOUT_MS = 10000

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None





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


def count() -> int:
    with _lock:
        row = _get_db().execute("SELECT COUNT(*) AS c FROM automations").fetchone()
    return int(row["c"]) if row else 0


def get_meta(key: str) -> str | None:
    """Read a persisted store marker, or ``None`` when it was never set."""
    with _lock:
        row = (
            _get_db()
            .execute("SELECT value FROM automation_meta WHERE key = ?", (key,))
            .fetchone()
        )
    return str(row["value"]) if row else None


def set_meta(key: str, value: str = "1") -> None:
    """Persist a store marker."""
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
    with _lock:
        rows = (
            _get_db()
            .execute("SELECT * FROM automations ORDER BY created_at ASC, id ASC")
            .fetchall()
        )
    return [_row_to_automation(row) for row in rows]


def get_automation(automation_id: str) -> Automation | None:
    with _lock:
        row = (
            _get_db()
            .execute("SELECT * FROM automations WHERE id = ?", (automation_id,))
            .fetchone()
        )
    return _row_to_automation(row) if row is not None else None


def upsert(automation: Automation) -> Automation:
    """Insert or update one automation row; returns the persisted record."""
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
    with _lock:
        db = _get_db()
        cursor = db.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        db.execute("DELETE FROM automation_runs WHERE automation_id = ?", (automation_id,))
        db.commit()
        return cursor.rowcount > 0


def start_run(automation_id: str, *, started_at: float, trigger: str) -> int:
    """Open a run row as ``unknown``; it stays that way unless finish_run lands."""
    if trigger not in RUN_TRIGGERS:
        raise ValueError(f"unknown run trigger: {trigger}")
    with _lock:
        db = _get_db()
        with _history_write(db):
            cursor = db.execute(
                """INSERT INTO automation_runs (automation_id, started_at, status, "trigger")
                   VALUES (?, ?, 'unknown', ?)""",
                (automation_id, started_at, trigger),
            )
        if cursor.lastrowid is None:
            raise RuntimeError(f"automation run for {automation_id} not recorded")
        return int(cursor.lastrowid)


def finish_run(run_id: int, *, finished_at: float, status: str, error: str | None) -> None:
    if status not in RUN_STATUSES:
        raise ValueError(f"unknown run status: {status}")
    with _lock:
        db = _get_db()
        with _history_write(db):
            db.execute(
                """UPDATE automation_runs SET finished_at = ?, status = ?, error = ?
                   WHERE id = ?""",
                (finished_at, status, error, run_id),
            )


@contextmanager
def _history_write(db: sqlite3.Connection) -> Iterator[None]:
    """Commit one history write under a short busy timeout; roll back on failure."""
    row = db.execute("PRAGMA busy_timeout").fetchone()
    previous = int(row[0]) if row else _DEFAULT_BUSY_TIMEOUT_MS
    db.execute(f"PRAGMA busy_timeout = {_HISTORY_BUSY_TIMEOUT_MS}")
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.execute(f"PRAGMA busy_timeout = {previous}")


def list_runs(automation_id: str, *, limit: int = 50) -> list[AutomationRun]:
    """Most recent runs first."""
    with _lock:
        rows = (
            _get_db()
            .execute(
                """SELECT id, automation_id, started_at, finished_at, status, error, "trigger"
                   FROM automation_runs WHERE automation_id = ?
                   ORDER BY started_at DESC, id DESC LIMIT ?""",
                (automation_id, max(1, int(limit))),
            )
            .fetchall()
        )
    return [
        AutomationRun(
            id=int(row["id"]),
            automation_id=row["automation_id"],
            started_at=float(row["started_at"]),
            finished_at=float(row["finished_at"]) if row["finished_at"] is not None else None,
            status=row["status"],
            error=row["error"],
            trigger=row["trigger"],
        )
        for row in rows
    ]


def prune_runs(keep: int = RUN_HISTORY_KEEP) -> int:
    """Keep the newest ``keep`` runs per automation and drop runs of deleted ones."""
    with _lock:
        db = _get_db()
        orphans = db.execute(
            "DELETE FROM automation_runs WHERE automation_id NOT IN (SELECT id FROM automations)"
        ).rowcount
        overflow = db.execute(
            """DELETE FROM automation_runs WHERE id IN (
                   SELECT id FROM (
                       SELECT id, ROW_NUMBER() OVER (
                           PARTITION BY automation_id ORDER BY started_at DESC, id DESC
                       ) AS rn
                       FROM automation_runs
                   ) WHERE rn > ?
               )""",
            (max(0, int(keep)),),
        ).rowcount
        db.commit()
    return max(0, orphans) + max(0, overflow)


def _row_to_automation(row: sqlite3.Row) -> Automation:
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
    try:
        conn.execute("SELECT 1")
    except sqlite3.Error:
        return False
    return True


def _quiet_close(conn: sqlite3.Connection) -> None:
    try:
        conn.close()
    except sqlite3.Error:
        pass


# Keep a typed alias for callers that prefer a store object.
class AutomationStore:
    """Thin object facade over the module-level helpers (test seam)."""

    def count(self) -> int:
        return count()

    def list(self) -> list[Automation]:
        return list_automations()

    def defaults_seeded(self) -> bool:
        return get_meta(DEFAULTS_SEEDED_KEY) is not None

    def mark_defaults_seeded(self) -> None:
        set_meta(DEFAULTS_SEEDED_KEY)

    def get(self, automation_id: str) -> Automation | None:
        return get_automation(automation_id)

    def upsert(self, automation: Automation) -> Automation:
        return upsert(automation)

    def set_enabled(self, automation_id: str, enabled: bool) -> Automation | None:
        return set_enabled(automation_id, enabled)

    def record_run(
        self,
        automation_id: str,
        *,
        ran_at: float,
        status: str,
        error: str | None,
    ) -> Automation | None:
        return record_run(automation_id, ran_at=ran_at, status=status, error=error)

    def delete(self, automation_id: str) -> bool:
        return delete(automation_id)

    def start_run(self, automation_id: str, *, started_at: float, trigger: str) -> int:
        return start_run(automation_id, started_at=started_at, trigger=trigger)

    def finish_run(
        self, run_id: int, *, finished_at: float, status: str, error: str | None
    ) -> None:
        finish_run(run_id, finished_at=finished_at, status=status, error=error)

    def list_runs(
        self, automation_id: str, *, limit: int = 50
    ) -> builtins.list[AutomationRun]:
        return list_runs(automation_id, limit=limit)

    def prune_runs(self, keep: int = RUN_HISTORY_KEEP) -> int:
        return prune_runs(keep)

    def reset_cache(self) -> None:
        reset_cache()
