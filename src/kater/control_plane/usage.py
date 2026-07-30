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
from collections.abc import Sequence
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


def _trim_usage_rows(db: sqlite3.Connection) -> int:
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
    """Drop oldest usage rows when the ledger exceeds ``max_rows``."""
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
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
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
    """Insert one usage event and return the stored row."""
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


def list_capabilities() -> list[str]:
    """Return the distinct capability ids present in the ledger."""
    with _lock:
        rows = (
            _get_db()
            .execute("SELECT DISTINCT capability FROM usage_events ORDER BY capability")
            .fetchall()
        )
    return [str(row["capability"]) for row in rows]


def _capability_where(
    capability: str | None,
    capabilities: Sequence[str] | None,
) -> tuple[str, list[Any]] | None:
    """Build the shared ``WHERE`` fragment for the capability filters.

    ``capabilities`` restricts the query to an explicit set (used to scope a
    caller to its allowlist *in SQL*, before any row limit applies). Returns
    ``None`` when the filters can never match, i.e. an empty set.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if capability is not None:
        clauses.append("capability = ?")
        params.append(capability)
    if capabilities is not None:
        allowed = [str(name) for name in capabilities]
        if not allowed:
            return None
        placeholders = ", ".join("?" * len(allowed))
        clauses.append(f"capability IN ({placeholders})")
        params.extend(allowed)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_usage_events(
    *,
    limit: int = 100,
    capability: str | None = None,
    capabilities: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return newest-first usage events, optionally filtered by capability."""
    lim = max(1, min(int(limit), 1000))
    cap = (capability or "").strip() or None
    built = _capability_where(cap, capabilities)
    if built is None:
        return []
    where, params = built
    with _lock:
        db = _get_db()
        rows = db.execute(
            f"""SELECT * FROM usage_events{where}
                ORDER BY timestamp DESC, id DESC
                LIMIT ?""",  # noqa: S608 - fragment is placeholders only
            (*params, lim),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _percentile(sorted_values: list[float], pct: float) -> float:
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


def usage_summary(
    *,
    capability: str | None = None,
    capabilities: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Aggregate usage by capability (count, success rate, cost, duration p50/p95).

    Aggregation happens in SQL over every matching row, so a caller scoped via
    ``capabilities`` gets a complete aggregate of what it may see rather than a
    truncated page.
    """
    cap_filter = (capability or "").strip() or None
    built = _capability_where(cap_filter, capabilities)
    if built is None:
        return {
            "total_events": 0,
            "overall_success_rate": 0.0,
            "total_cost_units": 0.0,
            "capabilities": [],
        }
    where, params = built
    with _lock:
        db = _get_db()
        agg_rows = db.execute(
            f"""SELECT capability,
                       COUNT(*) AS count,
                       SUM(success) AS success,
                       SUM(cost_units) AS total_cost
                FROM usage_events{where}
                GROUP BY capability""",  # noqa: S608 - fragment is placeholders only
            tuple(params),
        ).fetchall()
        duration_rows = db.execute(
            f"SELECT capability, duration_ms FROM usage_events{where}",  # noqa: S608
            tuple(params),
        ).fetchall()

    durations_by_cap: dict[str, list[float]] = {}
    for row in duration_rows:
        name = str(row["capability"])
        durations_by_cap.setdefault(name, []).append(float(row["duration_ms"] or 0))

    per_capability: list[dict[str, Any]] = []
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
        per_capability.append(
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
        "capabilities": per_capability,
    }
