"""Usage / cost events ledger.

Table ownership lives in the ``usage_events`` migration. The
``CREATE IF NOT EXISTS`` bootstrap below keeps unit tests and early
startup safe when migrate has not run yet.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from kater.settings import load_settings

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    capability TEXT NOT NULL,
    backend TEXT,
    tool_name TEXT,
    account_id TEXT,
    context_id TEXT,
    principal_id TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    duration_ms REAL NOT NULL DEFAULT 0,
    cost_units REAL NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_usage_events_ts ON usage_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_events_cap ON usage_events(capability);
"""

_lock = threading.RLock()
_db_cache: sqlite3.Connection | None = None
_db_path_cache: str | None = None

# Keep usage ledger bounded so summary queries stay predictable on long-lived hosts.
MAX_USAGE_ROWS = 50_000



def _quiet_close(conn: sqlite3.Connection) -> None:
    """Close a SQLite connection while suppressing SQLite errors."""
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _is_usable(conn: sqlite3.Connection) -> bool:
    """
    Check whether a SQLite connection can execute a query.

    Parameters:
        conn (sqlite3.Connection): The connection to test.

    Returns:
        bool: `True` if the connection executes successfully, `False` otherwise.
    """
    try:
        conn.execute("SELECT 1")
        return True
    except sqlite3.Error:
        return False


def _get_db() -> sqlite3.Connection:
    """
    Get a usable SQLite connection for the configured usage database.

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
    """Drop the cached connection (tests swap the working directory)."""
    global _db_cache, _db_path_cache
    with _lock:
        if _db_cache is not None:
            _quiet_close(_db_cache)
        _db_cache = None
        _db_path_cache = None


def _trim_usage_rows(db: sqlite3.Connection) -> int:
    """
    Trim the usage-event ledger to the configured maximum row count.

    The oldest events are removed first, ordered by timestamp and then ID.
    Changes are not committed by this function.

    Returns:
        int: The number of deleted events.
    """
    row = db.execute("SELECT COUNT(*) FROM usage_events").fetchone()
    count = int(row[0]) if row is not None else 0
    if count <= MAX_USAGE_ROWS:
        return 0
    excess = count - MAX_USAGE_ROWS
    db.execute(
        """DELETE FROM usage_events WHERE id IN (
               SELECT id FROM usage_events
               ORDER BY timestamp ASC, id ASC
               LIMIT ?
           )""",
        (excess,),
    )
    return excess


def prune_usage_events(*, max_rows: int = MAX_USAGE_ROWS) -> int:
    """
    Reduce the usage-event ledger to the specified maximum number of rows by removing the oldest
        events.

    Parameters:
        max_rows (int): Maximum number of rows to retain; values below 1 retain one row.

    Returns:
        int: Number of usage events deleted.
    """
    keep = max(1, int(max_rows))
    with _lock:
        db = _get_db()
        row = db.execute("SELECT COUNT(*) FROM usage_events").fetchone()
        count = int(row[0]) if row is not None else 0
        if count <= keep:
            return 0
        excess = count - keep
        db.execute(
            """DELETE FROM usage_events WHERE id IN (
                   SELECT id FROM usage_events
                   ORDER BY timestamp ASC, id ASC
                   LIMIT ?
               )""",
            (excess,),
        )
        db.commit()
        return excess


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    """
    Parse JSON metadata into a dictionary.

    Parameters:
        raw (str | None): JSON-encoded metadata, if available.

    Returns:
        dict[str, Any]: The parsed metadata dictionary, or an empty dictionary when the input is
            missing, invalid, or not an object.
    """
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """
    Convert a usage event database row into a typed dictionary.

    Parameters:
        row (sqlite3.Row): The database row containing usage event fields.

    Returns:
        dict[str, Any]: The usage event with normalized numeric, boolean, and metadata values.
    """
    return {
        "id": int(row["id"]),
        "timestamp": float(row["timestamp"]),
        "capability": str(row["capability"]),
        "backend": row["backend"],
        "tool_name": row["tool_name"],
        "account_id": row["account_id"],
        "context_id": row["context_id"],
        "principal_id": row["principal_id"],
        "success": bool(row["success"]),
        "duration_ms": float(row["duration_ms"] or 0),
        "cost_units": float(row["cost_units"] or 0),
        "metadata": _parse_metadata(row["metadata"]),
    }


def record_usage_event(
    *,
    capability: str,
    backend: str | None = None,
    tool_name: str | None = None,
    account_id: str | None = None,
    context_id: str | None = None,
    principal_id: str | None = None,
    success: bool = True,
    duration_ms: float = 0.0,
    cost_units: float = 0.0,
    metadata: dict[str, Any] | None = None,
    timestamp: float | None = None,
) -> dict[str, Any]:
    """
    Record a usage event and return its stored representation.

    Parameters:
        capability (str): Capability associated with the event.
        metadata (dict[str, Any] | None): Optional metadata to store with the event.
        timestamp (float | None): Event timestamp; defaults to the current time when omitted.

    Returns:
        dict[str, Any]: The stored usage event.

    Raises:
        ValueError: If `capability` is empty after trimming.
        RuntimeError: If the inserted event cannot be identified or retrieved.
    """
    cap = str(capability or "").strip()
    if not cap:
        raise ValueError("capability is required")
    ts = float(timestamp if timestamp is not None else time.time())
    meta = dict(metadata or {})
    with _lock:
        db = _get_db()
        cur = db.execute(
            """INSERT INTO usage_events (
                   timestamp, capability, backend, tool_name, account_id,
                   context_id, principal_id, success, duration_ms, cost_units, metadata
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ts,
                cap,
                backend,
                tool_name,
                account_id,
                context_id,
                principal_id,
                1 if success else 0,
                float(duration_ms or 0),
                float(cost_units or 0),
                json.dumps(meta, default=str),
            ),
        )
        raw_id = cur.lastrowid
        if raw_id is None:
            raise RuntimeError("usage event insert returned no row id")
        row_id = int(raw_id)
        _trim_usage_rows(db)
        db.commit()
        row = db.execute("SELECT * FROM usage_events WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"usage event {row_id} missing after insert")
    return _row_to_dict(row)


def list_usage_events(
    *,
    limit: int = 100,
    capability: str | None = None,
) -> list[dict[str, Any]]:
    """Return newest-first usage events, optionally filtered by capability."""
    lim = max(1, min(int(limit), 1000))
    cap = (capability or "").strip() or None
    with _lock:
        db = _get_db()
        if cap is not None:
            rows = db.execute(
                """SELECT * FROM usage_events
                   WHERE capability = ?
                   ORDER BY timestamp DESC, id DESC
                   LIMIT ?""",
                (cap, lim),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT * FROM usage_events
                   ORDER BY timestamp DESC, id DESC
                   LIMIT ?""",
                (lim,),
            ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _percentile(sorted_values: list[float], pct: float) -> float:
    """
    Calculate a percentile using linear interpolation over ascending values.

    Parameters:
        sorted_values (list[float]): Values sorted in ascending order.
        pct (float): Percentile position expressed as a fraction between 0 and 1.

    Returns:
        float: The interpolated percentile rounded to two decimal places, or 0.0 when no values are
            provided.
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    rank = (len(sorted_values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    value = sorted_values[low] * (1 - weight) + sorted_values[high] * weight
    return round(value, 2)


def usage_summary(*, capability: str | None = None) -> dict[str, Any]:
    """
    Aggregate usage metrics by capability, optionally restricting results to one capability.

    Parameters:
        capability (str | None): Capability name to include, or all capabilities when omitted.

    Returns:
        dict[str, Any]: Summary containing total events, overall success rate, total cost
        units, and per-capability counts, success rates, failure counts, costs, and
        duration percentiles.
    """
    cap_filter = (capability or "").strip() or None
    with _lock:
        db = _get_db()
        if cap_filter is not None:
            agg_rows = db.execute(
                """SELECT capability,
                          COUNT(*) AS count,
                          SUM(success) AS success,
                          SUM(cost_units) AS total_cost
                   FROM usage_events
                   WHERE capability = ?
                   GROUP BY capability""",
                (cap_filter,),
            ).fetchall()
            duration_rows = db.execute(
                "SELECT duration_ms FROM usage_events WHERE capability = ?",
                (cap_filter,),
            ).fetchall()
        else:
            agg_rows = db.execute(
                """SELECT capability,
                          COUNT(*) AS count,
                          SUM(success) AS success,
                          SUM(cost_units) AS total_cost
                   FROM usage_events
                   GROUP BY capability"""
            ).fetchall()
            duration_rows = db.execute(
                "SELECT capability, duration_ms FROM usage_events"
            ).fetchall()

    durations_by_cap: dict[str, list[float]] = {}
    if cap_filter is not None:
        durations_by_cap[cap_filter] = [
            float(row["duration_ms"] or 0) for row in duration_rows
        ]
    else:
        for row in duration_rows:
            name = str(row["capability"])
            durations_by_cap.setdefault(name, []).append(float(row["duration_ms"] or 0))

    capabilities: list[dict[str, Any]] = []
    total_count = 0
    total_success = 0
    total_cost = 0.0
    for row in sorted(agg_rows, key=lambda item: str(item["capability"])):
        name = str(row["capability"])
        count = int(row["count"])
        success = int(row["success"] or 0)
        failed = count - success
        cost = float(row["total_cost"] or 0)
        durations = sorted(durations_by_cap.get(name, []))
        total_count += count
        total_success += success
        total_cost += cost
        capabilities.append(
            {
                "capability": name,
                "count": count,
                "success": success,
                "failed": failed,
                "success_rate": round((success / count) * 100, 1) if count else 0.0,
                "total_cost_units": round(cost, 4),
                "duration_p50_ms": _percentile(durations, 0.50),
                "duration_p95_ms": _percentile(durations, 0.95),
            }
        )

    return {
        "total_events": total_count,
        "overall_success_rate": round((total_success / total_count) * 100, 1)
        if total_count
        else 0.0,
        "total_cost_units": round(total_cost, 4),
        "capabilities": capabilities,
    }
