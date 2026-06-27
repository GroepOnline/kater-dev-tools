from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections import deque
from pathlib import Path
from typing import Any

from kater.settings import load_settings

_log = logging.getLogger("kater.storage")

# Hard cap on how many events an unbounded query loads into memory, so a large
# or poisoned store cannot OOM the API process via /api/telemetry|/api/evals.
MAX_EVENTS = 100_000
# Hard cap on rows kept on disk. Inserts beyond this prune the oldest rows so a
# long-running public gateway cannot exhaust disk via telemetry growth.
MAX_ROWS_ON_DISK = 200_000
# Prune check frequency: only sweep once every N inserts to avoid write overhead.
_PRUNE_EVERY = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    timestamp REAL NOT NULL,
    duration_ms REAL DEFAULT 0,
    success INTEGER DEFAULT 1,
    profile TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_name ON events(name);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
"""

_storage_lock = threading.Lock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None
_insert_counter = 0


def _resolve_db_path() -> Path:
    settings = load_settings()
    p = settings.db_path
    if "/" in p:
        return Path(p).expanduser()
    return Path.cwd() / p


def _get_backend() -> str:
    return load_settings().storage_backend


# ── SQLite ─────────────────────────────────────────────────────────


def _get_db() -> sqlite3.Connection:
    global _db_cache, _db_path_cache
    db_path = str(_resolve_db_path())
    if _db_cache is not None and _db_path_cache == db_path:
        try:
            _db_cache.execute("SELECT 1")
        except sqlite3.DatabaseError:
            _db_cache.close()
            _db_cache = None
            _db_path_cache = None
    if _db_cache is not None:
        return _db_cache
    db_path_obj = Path(db_path)
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    _db_cache = conn
    _db_path_cache = db_path
    return conn


def _sqlite_insert(event: dict[str, Any]) -> None:
    global _insert_counter
    with _storage_lock:
        db = _get_db()
        db.execute(
            """INSERT INTO events (type, name, timestamp, duration_ms, success, profile, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event["type"],
                event["name"],
                event["timestamp"],
                event.get("duration_ms", 0),
                1 if event.get("success", True) else 0,
                event.get("profile"),
                json.dumps(event.get("metadata", {}), ensure_ascii=False),
            ),
        )
        _insert_counter += 1
        if _insert_counter % _PRUNE_EVERY == 0:
            _sqlite_prune_locked(db)
        db.commit()


def _sqlite_prune_locked(db: sqlite3.Connection) -> int:
    """Drop oldest rows beyond MAX_ROWS_ON_DISK. Caller holds _storage_lock."""
    row = db.execute("SELECT COUNT(*) AS c FROM events").fetchone()
    count = row["c"] if row else 0
    if count <= MAX_ROWS_ON_DISK:
        return 0
    excess = count - MAX_ROWS_ON_DISK
    db.execute(
        "DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY id ASC LIMIT ?)",
        (excess,),
    )
    _log.info("pruned %d telemetry rows (kept cap %d)", excess, MAX_ROWS_ON_DISK)
    return excess


def _sqlite_query(
    limit: int = 0,
    event_type: str | None = None,
    name: str | None = None,
    since: float | None = None,
) -> list[dict[str, Any]]:
    with _storage_lock:
        db = _get_db()
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        if event_type:
            query += " AND type = ?"
            params.append(event_type)
        if name:
            query += " AND name = ?"
            params.append(name)
        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        if limit > 0:
            query += " ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)
            rows = db.execute(query, params).fetchall()
        else:
            # Unbounded request: cap to the most recent MAX_EVENTS, but return
            # them in chronological order so callers see a normal ASC stream.
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(MAX_EVENTS)
            rows = list(reversed(db.execute(query, params).fetchall()))
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    raw_meta = row["metadata"]
    if raw_meta:
        try:
            metadata = json.loads(raw_meta)
        except (json.JSONDecodeError, ValueError, TypeError):
            metadata = {"_parse_error": True}
    else:
        metadata = {}
    return {
        "type": row["type"],
        "name": row["name"],
        "timestamp": row["timestamp"],
        "duration_ms": row["duration_ms"],
        "success": bool(row["success"]),
        "profile": row["profile"],
        "metadata": metadata,
    }


def _sqlite_count(event_type: str | None = None) -> int:
    with _storage_lock:
        db = _get_db()
        if event_type:
            row = db.execute(
                "SELECT COUNT(*) as c FROM events WHERE type = ?", (event_type,)
            ).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) as c FROM events").fetchone()
    return row["c"]


def _sqlite_clear() -> int:
    with _storage_lock:
        db = _get_db()
        row = db.execute("SELECT COUNT(*) as c FROM events").fetchone()
        count = row["c"]
        db.execute("DELETE FROM events")
        db.execute("DELETE FROM sqlite_sequence WHERE name='events'")
        db.commit()
    return count


# ── JSONL fallback ─────────────────────────────────────────────────


def _jsonl_path() -> Path:
    return Path.cwd() / ".kater" / "telemetry.jsonl"


def _jsonl_insert(event: dict[str, Any]) -> None:
    path = _jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with _storage_lock, path.open("a", encoding="utf-8") as f:
        f.write(line)


def _jsonl_query(
    limit: int = 0,
    event_type: str | None = None,
    name: str | None = None,
    since: float | None = None,
) -> list[dict[str, Any]]:
    path = _jsonl_path()
    if not path.exists():
        return []
    # Bound memory to the most recent `cap` matching events (deque drops the
    # oldest), and never let one corrupt line take down the whole query.
    cap = limit if limit > 0 else MAX_EVENTS
    events: deque[dict[str, Any]] = deque(maxlen=cap)
    with _storage_lock, path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if event_type and event.get("type") != event_type:
                continue
            if name and event.get("name") != name:
                continue
            if since and event.get("timestamp", 0) < since:
                continue
            events.append(event)
    return list(events)


def _jsonl_count(event_type: str | None = None) -> int:
    return len(_jsonl_query(event_type=event_type))


def _jsonl_clear() -> int:
    path = _jsonl_path()
    if not path.exists():
        return 0
    count = _jsonl_count()
    with _storage_lock:
        if path.exists():
            path.unlink()
    return count


def _jsonl_prune() -> int:
    """Keep only the most recent MAX_ROWS_ON_DISK lines in the JSONL file."""
    path = _jsonl_path()
    if not path.exists():
        return 0
    with _storage_lock:
        with path.open(encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= MAX_ROWS_ON_DISK:
            return 0
        keep = lines[-MAX_ROWS_ON_DISK:]
        dropped = len(lines) - len(keep)
        path.write_text("".join(keep), encoding="utf-8")
    _log.info("pruned %d telemetry lines (kept cap %d)", dropped, MAX_ROWS_ON_DISK)
    return dropped


# ── Unified API ────────────────────────────────────────────────────


def insert_event(event: dict[str, Any]) -> None:
    if _get_backend() == "sqlite":
        _sqlite_insert(event)
    else:
        _jsonl_insert(event)


def query_events(
    limit: int = 0,
    event_type: str | None = None,
    name: str | None = None,
    since: float | None = None,
) -> list[dict[str, Any]]:
    if _get_backend() == "sqlite":
        return _sqlite_query(limit=limit, event_type=event_type, name=name, since=since)
    return _jsonl_query(limit=limit, event_type=event_type, name=name, since=since)


def count_events(event_type: str | None = None) -> int:
    if _get_backend() == "sqlite":
        return _sqlite_count(event_type)
    return _jsonl_count(event_type)


def clear_all_events() -> int:
    if _get_backend() == "sqlite":
        return _sqlite_clear()
    return _jsonl_clear()


def prune_all() -> int:
    """Enforce the on-disk row cap across whichever backend is active."""
    if _get_backend() == "sqlite":
        with _storage_lock:
            return _sqlite_prune_locked(_get_db())
    return _jsonl_prune()


def reset_db_cache() -> None:
    global _db_cache, _db_path_cache
    with _storage_lock:
        if _db_cache is not None:
            _db_cache.close()
        _db_cache = None
        _db_path_cache = None
