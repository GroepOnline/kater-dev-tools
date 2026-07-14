from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from kater.capabilities.models import (
    CapabilityManifest,
    CapabilityTransport,
    LifecycleState,
    RiskClass,
)
from kater.settings import load_settings

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS control_capabilities (
    capability_id TEXT NOT NULL,
    version TEXT NOT NULL,
    package_id TEXT NOT NULL,
    publisher_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    transport TEXT NOT NULL,
    description TEXT NOT NULL,
    input_schema TEXT NOT NULL,
    output_schema TEXT NOT NULL,
    required_scopes TEXT NOT NULL,
    risk_class TEXT NOT NULL,
    data_classification TEXT NOT NULL,
    profiles TEXT NOT NULL,
    healthcheck_capability_id TEXT,
    lifecycle_state TEXT NOT NULL,
    rollback_version TEXT,
    network_targets TEXT NOT NULL,
    tags TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (capability_id, version)
);

CREATE INDEX IF NOT EXISTS idx_control_cap_lifecycle
    ON control_capabilities(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_control_cap_package
    ON control_capabilities(package_id);
"""

_ACTIVE_LIFECYCLES = frozenset({LifecycleState.ACTIVE, LifecycleState.CANARY})

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


def _json_list(values: frozenset[str] | tuple[str, ...] | list[str]) -> str:
    return json.dumps(sorted(values))


def _parse_str_set(raw: str | None) -> frozenset[str]:
    try:
        data = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        return frozenset()
    if not isinstance(data, list):
        return frozenset()
    return frozenset(str(item) for item in data)


def _parse_str_tuple(raw: str | None) -> tuple[str, ...]:
    try:
        data = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(str(item) for item in sorted(str(x) for x in data))


def _parse_schema(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _version_key(version: str) -> tuple[object, ...]:
    parts: list[object] = []
    for part in version.lstrip("vV").replace("+", ".").replace("-", ".").split("."):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part))
    return tuple(parts)


def _lifecycle_preference(state: LifecycleState) -> int:
    order = {
        LifecycleState.ACTIVE: 0,
        LifecycleState.CANARY: 1,
        LifecycleState.VERIFIED: 2,
        LifecycleState.CANDIDATE: 3,
        LifecycleState.DEPRECATED: 4,
        LifecycleState.REVOKED: 5,
    }
    return order.get(state, 99)


def _row_to_manifest(row: sqlite3.Row) -> CapabilityManifest:
    try:
        transport = CapabilityTransport(row["transport"])
    except ValueError as exc:
        raise ValueError(f"invalid transport in store: {row['transport']!r}") from exc
    try:
        risk_class = RiskClass(row["risk_class"])
    except ValueError as exc:
        raise ValueError(f"invalid risk_class in store: {row['risk_class']!r}") from exc
    try:
        lifecycle_state = LifecycleState(row["lifecycle_state"])
    except ValueError as exc:
        raise ValueError(
            f"invalid lifecycle_state in store: {row['lifecycle_state']!r}"
        ) from exc
    return CapabilityManifest(
        capability_id=row["capability_id"],
        package_id=row["package_id"],
        publisher_id=row["publisher_id"],
        version=row["version"],
        digest=row["digest"] or "",
        transport=transport,
        description=row["description"] or "",
        input_schema=_parse_schema(row["input_schema"]),
        output_schema=_parse_schema(row["output_schema"]),
        required_scopes=_parse_str_set(row["required_scopes"]),
        risk_class=risk_class,
        data_classification=row["data_classification"],
        profiles=_parse_str_set(row["profiles"]),
        healthcheck_capability_id=row["healthcheck_capability_id"],
        lifecycle_state=lifecycle_state,
        rollback_version=row["rollback_version"],
        network_targets=_parse_str_tuple(row["network_targets"]),
        tags=_parse_str_set(row["tags"]),
    )


def upsert_capability(manifest: CapabilityManifest) -> None:
    """Insert or replace one capability version in the control-plane database."""
    now = time.time()
    with _lock, _connect() as db:
        db.execute(
            """INSERT INTO control_capabilities
               (capability_id, version, package_id, publisher_id, digest, transport,
                description, input_schema, output_schema, required_scopes, risk_class,
                data_classification, profiles, healthcheck_capability_id,
                lifecycle_state, rollback_version, network_targets, tags, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(capability_id, version) DO UPDATE SET
                 package_id = excluded.package_id,
                 publisher_id = excluded.publisher_id,
                 digest = excluded.digest,
                 transport = excluded.transport,
                 description = excluded.description,
                 input_schema = excluded.input_schema,
                 output_schema = excluded.output_schema,
                 required_scopes = excluded.required_scopes,
                 risk_class = excluded.risk_class,
                 data_classification = excluded.data_classification,
                 profiles = excluded.profiles,
                 healthcheck_capability_id = excluded.healthcheck_capability_id,
                 lifecycle_state = excluded.lifecycle_state,
                 rollback_version = excluded.rollback_version,
                 network_targets = excluded.network_targets,
                 tags = excluded.tags,
                 updated_at = excluded.updated_at""",
            (
                manifest.capability_id,
                manifest.version,
                manifest.package_id,
                manifest.publisher_id,
                manifest.digest,
                manifest.transport.value,
                manifest.description,
                json.dumps(manifest.input_schema),
                json.dumps(manifest.output_schema),
                _json_list(manifest.required_scopes),
                manifest.risk_class.value,
                manifest.data_classification,
                _json_list(manifest.profiles),
                manifest.healthcheck_capability_id,
                manifest.lifecycle_state.value,
                manifest.rollback_version,
                _json_list(manifest.network_targets),
                _json_list(manifest.tags),
                now,
            ),
        )


def list_capabilities(*, include_non_active: bool = False) -> list[CapabilityManifest]:
    """List persisted capabilities; by default only active and canary."""
    with _lock, _connect() as db:
        rows = db.execute(
            """SELECT * FROM control_capabilities
               ORDER BY capability_id, version"""
        ).fetchall()
    manifests = [_row_to_manifest(row) for row in rows]
    if not include_non_active:
        manifests = [m for m in manifests if m.lifecycle_state in _ACTIVE_LIFECYCLES]
    manifests.sort(key=lambda m: (m.capability_id, _version_key(m.version)))
    return manifests


def get_capability(
    capability_id: str, version: str | None = None
) -> CapabilityManifest | None:
    """Fetch one capability; without version, prefer active then highest semver."""
    with _lock, _connect() as db:
        if version is not None:
            row = db.execute(
                """SELECT * FROM control_capabilities
                   WHERE capability_id = ? AND version = ?""",
                (capability_id, version),
            ).fetchone()
            return _row_to_manifest(row) if row else None
        rows = db.execute(
            "SELECT * FROM control_capabilities WHERE capability_id = ?",
            (capability_id,),
        ).fetchall()
    if not rows:
        return None
    candidates = [_row_to_manifest(row) for row in rows]
    best_pref = min(_lifecycle_preference(m.lifecycle_state) for m in candidates)
    band = [
        m for m in candidates if _lifecycle_preference(m.lifecycle_state) == best_pref
    ]
    band.sort(key=lambda m: _version_key(m.version), reverse=True)
    return band[0]


def set_capability_lifecycle(
    capability_id: str, version: str, state: LifecycleState
) -> CapabilityManifest:
    """Update lifecycle for one persisted capability version."""
    if not isinstance(state, LifecycleState):
        raise ValueError("state must be a LifecycleState")
    with _lock, _connect() as db:
        cursor = db.execute(
            """UPDATE control_capabilities
               SET lifecycle_state = ?, updated_at = ?
               WHERE capability_id = ? AND version = ?""",
            (state.value, time.time(), capability_id, version),
        )
        if cursor.rowcount < 1:
            raise KeyError(f"capability not found: {capability_id}@{version}")
        row = db.execute(
            """SELECT * FROM control_capabilities
               WHERE capability_id = ? AND version = ?""",
            (capability_id, version),
        ).fetchone()
    if row is None:
        raise KeyError(f"capability not found: {capability_id}@{version}")
    return _row_to_manifest(row)


def remove_capability(capability_id: str, version: str) -> bool:
    """Delete one capability version; returns True when a row was removed."""
    with _lock, _connect() as db:
        cursor = db.execute(
            """DELETE FROM control_capabilities
               WHERE capability_id = ? AND version = ?""",
            (capability_id, version),
        )
        return cursor.rowcount > 0


def clear_capability_state() -> None:
    """Test/repair helper: remove all persisted capability manifests."""
    with _lock, _connect() as db:
        db.execute("DELETE FROM control_capabilities")


def capability_overview() -> dict[str, Any]:
    """Return total and per-lifecycle counts for persisted capabilities."""
    with _lock, _connect() as db:
        rows = db.execute(
            """SELECT lifecycle_state, COUNT(*) AS c
               FROM control_capabilities
               GROUP BY lifecycle_state
               ORDER BY lifecycle_state"""
        ).fetchall()
        total_row = db.execute(
            "SELECT COUNT(*) AS c FROM control_capabilities"
        ).fetchone()
    by_lifecycle = {row["lifecycle_state"]: int(row["c"]) for row in rows}
    return {
        "total": int(total_row["c"] if total_row else 0),
        "by_lifecycle": by_lifecycle,
    }


def load_lifecycle_overlays() -> list[dict[str, str]]:
    """Lifecycle triples for optional registry bootstrap overlays."""
    with _lock, _connect() as db:
        rows = db.execute(
            """SELECT capability_id, version, lifecycle_state
               FROM control_capabilities
               ORDER BY capability_id, version"""
        ).fetchall()
    return [
        {
            "capability_id": row["capability_id"],
            "version": row["version"],
            "lifecycle_state": row["lifecycle_state"],
        }
        for row in rows
    ]
