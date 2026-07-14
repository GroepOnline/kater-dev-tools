from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kater.control_plane.models import (
    AccountState,
    ProviderAccount,
    QuotaWindow,
    RouteBinding,
    RoutingDecision,
    RoutingRequest,
)
from kater.settings import load_settings

_SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS control_route_candidates (
    capability TEXT NOT NULL,
    account_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    backend TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    scopes TEXT NOT NULL,
    priority INTEGER NOT NULL,
    max_concurrent INTEGER NOT NULL,
    cost_per_million_units REAL NOT NULL,
    latency_ms REAL NOT NULL,
    state TEXT NOT NULL,
    cooldown_until REAL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (capability, account_id)
);

CREATE INDEX IF NOT EXISTS idx_control_route_capability
    ON control_route_candidates(capability);
CREATE INDEX IF NOT EXISTS idx_control_route_backend
    ON control_route_candidates(backend, tool_name);

CREATE TABLE IF NOT EXISTS control_quota_windows (
    capability TEXT NOT NULL,
    account_id TEXT NOT NULL,
    name TEXT NOT NULL,
    limit_units INTEGER NOT NULL,
    used_units INTEGER NOT NULL,
    resets_at REAL,
    PRIMARY KEY (capability, account_id, name),
    FOREIGN KEY (capability, account_id)
        REFERENCES control_route_candidates(capability, account_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS control_routing_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    capability TEXT NOT NULL,
    context_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    backend TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    estimated_units INTEGER NOT NULL,
    score REAL NOT NULL,
    reasons TEXT NOT NULL,
    outcome TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_control_decision_capability
    ON control_routing_decisions(capability, id DESC);
CREATE INDEX IF NOT EXISTS idx_control_decision_context
    ON control_routing_decisions(context_id, id DESC);

CREATE TABLE IF NOT EXISTS control_route_affinity (
    capability TEXT NOT NULL,
    context_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (capability, context_id)
);
"""

_lock = threading.RLock()


def _db_path() -> Path:
    configured = Path(load_settings().db_path).expanduser()
    return configured if configured.is_absolute() else Path.cwd() / configured


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _ts(value: datetime | None) -> float | None:
    return value.timestamp() if value is not None else None


def _dt(value: float | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value is not None else None


def upsert_route_candidate(capability: str, account: ProviderAccount) -> None:
    if not capability:
        raise ValueError("capability is required")
    if "__" in capability:
        raise ValueError("logical capability cannot contain '__'")
    now = time.time()
    with _lock, _connect() as db:
        db.execute(
            """INSERT INTO control_route_candidates
               (capability, account_id, provider, backend, tool_name, scopes,
                priority, max_concurrent, cost_per_million_units, latency_ms,
                state, cooldown_until, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(capability, account_id) DO UPDATE SET
                 provider = excluded.provider,
                 backend = excluded.backend,
                 tool_name = excluded.tool_name,
                 scopes = excluded.scopes,
                 priority = excluded.priority,
                 max_concurrent = excluded.max_concurrent,
                 cost_per_million_units = excluded.cost_per_million_units,
                 latency_ms = excluded.latency_ms,
                 state = excluded.state,
                 cooldown_until = excluded.cooldown_until,
                 updated_at = excluded.updated_at""",
            (
                capability,
                account.account_id,
                account.provider,
                account.backend,
                account.tool_name,
                json.dumps(sorted(account.scopes)),
                account.priority,
                account.max_concurrent,
                account.cost_per_million_units,
                account.latency_ms,
                account.state.value,
                _ts(account.cooldown_until),
                now,
            ),
        )
        db.execute(
            "DELETE FROM control_quota_windows WHERE capability = ? AND account_id = ?",
            (capability, account.account_id),
        )
        db.executemany(
            """INSERT INTO control_quota_windows
               (capability, account_id, name, limit_units, used_units, resets_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    capability,
                    account.account_id,
                    window.name,
                    window.limit,
                    window.used,
                    _ts(window.resets_at),
                )
                for window in account.quota_windows
            ],
        )


def remove_route_candidate(capability: str, account_id: str) -> bool:
    with _lock, _connect() as db:
        db.execute(
            "DELETE FROM control_route_affinity WHERE capability = ? AND account_id = ?",
            (capability, account_id),
        )
        cursor = db.execute(
            "DELETE FROM control_route_candidates WHERE capability = ? AND account_id = ?",
            (capability, account_id),
        )
        return cursor.rowcount > 0


def list_route_candidates(capability: str | None = None) -> list[RouteBinding]:
    with _lock, _connect() as db:
        if capability is None:
            rows = db.execute(
                "SELECT * FROM control_route_candidates ORDER BY capability, priority, account_id"
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT * FROM control_route_candidates
                   WHERE capability = ? ORDER BY priority, account_id""",
                (capability,),
            ).fetchall()
        bindings: list[RouteBinding] = []
        for row in rows:
            windows = db.execute(
                """SELECT * FROM control_quota_windows
                   WHERE capability = ? AND account_id = ? ORDER BY name""",
                (row["capability"], row["account_id"]),
            ).fetchall()
            try:
                scopes = frozenset(json.loads(row["scopes"] or "[]"))
            except (json.JSONDecodeError, TypeError, ValueError):
                scopes = frozenset()
            try:
                state = AccountState(row["state"])
            except ValueError:
                state = AccountState.DISABLED
            account = ProviderAccount(
                account_id=row["account_id"],
                provider=row["provider"],
                backend=row["backend"],
                tool_name=row["tool_name"],
                scopes=scopes,
                priority=int(row["priority"]),
                max_concurrent=int(row["max_concurrent"]),
                cost_per_million_units=float(row["cost_per_million_units"]),
                latency_ms=float(row["latency_ms"]),
                state=state,
                cooldown_until=_dt(row["cooldown_until"]),
                quota_windows=tuple(
                    QuotaWindow(
                        name=window["name"],
                        limit=int(window["limit_units"]),
                        used=int(window["used_units"]),
                        resets_at=_dt(window["resets_at"]),
                    )
                    for window in windows
                ),
            )
            bindings.append(RouteBinding(capability=row["capability"], account=account))
        return bindings


def set_route_candidate_state(
    capability: str,
    account_id: str,
    state: AccountState,
    *,
    cooldown_until: datetime | None = None,
) -> bool:
    with _lock, _connect() as db:
        cursor = db.execute(
            """UPDATE control_route_candidates
               SET state = ?, cooldown_until = ?, updated_at = ?
               WHERE capability = ? AND account_id = ?""",
            (state.value, _ts(cooldown_until), time.time(), capability, account_id),
        )
        return cursor.rowcount > 0


def get_route_affinity(capability: str, context_id: str) -> str | None:
    with _lock, _connect() as db:
        row = db.execute(
            """SELECT account_id FROM control_route_affinity
               WHERE capability = ? AND context_id = ?""",
            (capability, context_id),
        ).fetchone()
    return str(row["account_id"]) if row else None


def set_route_affinity(capability: str, context_id: str, account_id: str) -> None:
    with _lock, _connect() as db:
        db.execute(
            """INSERT INTO control_route_affinity
               (capability, context_id, account_id, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(capability, context_id) DO UPDATE SET
                 account_id = excluded.account_id,
                 updated_at = excluded.updated_at""",
            (capability, context_id, account_id, time.time()),
        )


def clear_route_affinity(
    capability: str,
    context_id: str,
    *,
    account_id: str | None = None,
) -> None:
    with _lock, _connect() as db:
        if account_id is None:
            db.execute(
                "DELETE FROM control_route_affinity WHERE capability = ? AND context_id = ?",
                (capability, context_id),
            )
        else:
            db.execute(
                """DELETE FROM control_route_affinity
                   WHERE capability = ? AND context_id = ? AND account_id = ?""",
                (capability, context_id, account_id),
            )


def consume_quota(capability: str, account_id: str, units: int) -> None:
    if units < 1:
        raise ValueError("units must be at least one")
    now = time.time()
    with _lock, _connect() as db:
        db.execute(
            """UPDATE control_quota_windows
               SET used_units = CASE
                     WHEN resets_at IS NOT NULL AND resets_at <= ? THEN MIN(limit_units, ?)
                     ELSE MIN(limit_units, used_units + ?)
                   END,
                   resets_at = CASE
                     WHEN resets_at IS NOT NULL AND resets_at <= ? THEN NULL
                     ELSE resets_at
                   END
               WHERE capability = ? AND account_id = ?""",
            (now, units, units, now, capability, account_id),
        )


def record_routing_decision(
    request: RoutingRequest,
    decision: RoutingDecision,
    *,
    outcome: str,
    error: str | None = None,
) -> int:
    with _lock, _connect() as db:
        cursor = db.execute(
            """INSERT INTO control_routing_decisions
               (timestamp, capability, context_id, account_id, provider, backend,
                tool_name, estimated_units, score, reasons, outcome, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                request.capability,
                request.context_id,
                decision.account_id,
                decision.provider,
                decision.backend,
                decision.tool_name,
                request.estimated_units,
                decision.score,
                json.dumps(decision.reasons),
                outcome,
                error,
            ),
        )
        return int(cursor.lastrowid or 0)


def query_routing_decisions(
    *,
    capability: str | None = None,
    context_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    conditions: list[str] = []
    params: list[Any] = []
    if capability:
        conditions.append("capability = ?")
        params.append(capability)
    if context_id:
        conditions.append("context_id = ?")
        params.append(context_id)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    query = (
        f"SELECT * FROM control_routing_decisions{where} "  # noqa: S608
        "ORDER BY id DESC LIMIT ?"
    )
    with _lock, _connect() as db:
        rows = db.execute(query, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["reasons"] = json.loads(item["reasons"])
        except (json.JSONDecodeError, TypeError, ValueError):
            item["reasons"] = []
        result.append(item)
    return result


def route_overview() -> dict[str, Any]:
    bindings = list_route_candidates()
    capabilities = {binding.capability for binding in bindings}
    current = datetime.now(UTC)
    active = sum(
        1
        for binding in bindings
        if binding.account.effective_state(current) == AccountState.ACTIVE
        and all(
            window.remaining_at(current) > 0
            for window in binding.account.quota_windows
        )
    )
    with _lock, _connect() as db:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM control_routing_decisions"
        ).fetchone()
        decision_count = int(row["c"] if row else 0)
        affinity_row = db.execute(
            "SELECT COUNT(*) AS c FROM control_route_affinity"
        ).fetchone()
        affinity_count = int(affinity_row["c"] if affinity_row else 0)
    return {
        "capabilities": len(capabilities),
        "candidates": len(bindings),
        "active_candidates": active,
        "decisions": decision_count,
        "affinities": affinity_count,
    }


def clear_control_plane_state() -> None:
    """Test/repair helper: remove route state without touching normal telemetry."""
    with _lock, _connect() as db:
        db.execute("DELETE FROM control_routing_decisions")
        db.execute("DELETE FROM control_route_affinity")
        db.execute("DELETE FROM control_quota_windows")
        db.execute("DELETE FROM control_route_candidates")