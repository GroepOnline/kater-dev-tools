from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from kater.settings import load_settings

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

_db_lock = threading.Lock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None


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
    if _db_cache is not None:
        _db_cache.close()
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
    with _db_lock:
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
        db.commit()


def _sqlite_query(
    limit: int = 0,
    event_type: str | None = None,
    name: str | None = None,
    since: float | None = None,
) -> list[dict[str, Any]]:
    with _db_lock:
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
        query += " ORDER BY timestamp ASC"
        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = db.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "type": row["type"],
        "name": row["name"],
        "timestamp": row["timestamp"],
        "duration_ms": row["duration_ms"],
        "success": bool(row["success"]),
        "profile": row["profile"],
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
    }


def _sqlite_count(event_type: str | None = None) -> int:
    with _db_lock:
        db = _get_db()
        if event_type:
            row = db.execute(
                "SELECT COUNT(*) as c FROM events WHERE type = ?", (event_type,)
            ).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) as c FROM events").fetchone()
    return row["c"]


def _sqlite_clear() -> int:
    with _db_lock:
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
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _jsonl_query(
    limit: int = 0,
    event_type: str | None = None,
    name: str | None = None,
    since: float | None = None,
) -> list[dict[str, Any]]:
    path = _jsonl_path()
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event_type and event["type"] != event_type:
                continue
            if name and event["name"] != name:
                continue
            if since and event["timestamp"] < since:
                continue
            events.append(event)
    if limit > 0:
        events = events[-limit:]
    return events


def _jsonl_count(event_type: str | None = None) -> int:
    return len(_jsonl_query(event_type=event_type))


def _jsonl_clear() -> int:
    path = _jsonl_path()
    if not path.exists():
        return 0
    count = _jsonl_count()
    path.unlink()
    return count


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


def reset_db_cache() -> None:
    global _db_cache, _db_path_cache
    with _db_lock:
        if _db_cache is not None:
            _db_cache.close()
        _db_cache = None
        _db_path_cache = None
