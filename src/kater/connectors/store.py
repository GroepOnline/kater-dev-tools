"""SQLite persistence for the connector catalog."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from kater.connectors.errors import (
    ConnectorExistsError,
    ConnectorNotFoundError,
    ConnectorValidationError,
)
from kater.connectors.models import (
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    PermissionLevel,
)
from kater.settings import load_settings

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS connectors (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    type TEXT NOT NULL,
    version TEXT NOT NULL,
    transport_json TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    auth_binding_json TEXT NOT NULL,
    profiles_json TEXT NOT NULL,
    permissions_json TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    origin TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""

_lock = threading.RLock()
_cache: dict[str, ConnectorRecord] | None = None


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


@contextmanager
def _transaction() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, always close."""
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _invalidate_cache() -> None:
    global _cache
    _cache = None


def reload_store() -> None:
    """Drop any in-memory cache; next read hits SQLite."""
    with _lock:
        _invalidate_cache()


def clear_connector_state() -> None:
    """Test helper: remove all persisted connector rows and cache."""
    with _lock:
        _invalidate_cache()
        with _transaction() as db:
            db.execute("DELETE FROM connectors")


def _record_to_row(record: ConnectorRecord, updated_at: float) -> tuple[Any, ...]:
    return (
        record.id,
        record.display_name,
        record.type.value,
        record.version,
        json.dumps(record.transport.as_dict()),
        json.dumps([cap.as_dict() for cap in record.capabilities]),
        json.dumps(record.auth_binding.as_dict()),
        json.dumps(sorted(record.profiles)),
        json.dumps({key: value.value for key, value in sorted(record.permissions.items())}),
        record.status.value,
        json.dumps(record.metadata),
        record.origin,
        updated_at,
    )


def _row_to_mapping(row: sqlite3.Row) -> dict[str, Any]:
    try:
        transport = json.loads(row["transport_json"] or "{}")
        capabilities = json.loads(row["capabilities_json"] or "[]")
        auth_binding = json.loads(row["auth_binding_json"] or "{}")
        profiles = json.loads(row["profiles_json"] or "[]")
        permissions = json.loads(row["permissions_json"] or "{}")
        metadata = json.loads(row["metadata_json"] or "{}")
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConnectorValidationError(
            f"connector {row['id']!r} has malformed JSON",
            connector_id=row["id"],
        ) from exc
    if not isinstance(transport, dict):
        raise ConnectorValidationError(
            f"connector {row['id']!r} transport must be an object",
            connector_id=row["id"],
        )
    if not isinstance(capabilities, list):
        raise ConnectorValidationError(
            f"connector {row['id']!r} capabilities must be a list",
            connector_id=row["id"],
        )
    if not isinstance(auth_binding, dict):
        raise ConnectorValidationError(
            f"connector {row['id']!r} auth_binding must be an object",
            connector_id=row["id"],
        )
    if not isinstance(profiles, list):
        raise ConnectorValidationError(
            f"connector {row['id']!r} profiles must be a list",
            connector_id=row["id"],
        )
    if not isinstance(permissions, dict):
        raise ConnectorValidationError(
            f"connector {row['id']!r} permissions must be an object",
            connector_id=row["id"],
        )
    if not isinstance(metadata, dict):
        raise ConnectorValidationError(
            f"connector {row['id']!r} metadata must be an object",
            connector_id=row["id"],
        )
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "type": row["type"],
        "version": row["version"],
        "transport": transport,
        "capabilities": capabilities,
        "auth_binding": auth_binding,
        "profiles": profiles,
        "permissions": permissions,
        "status": row["status"],
        "metadata": metadata,
        "origin": row["origin"],
    }


def _row_to_record(row: sqlite3.Row) -> ConnectorRecord:
    try:
        return ConnectorRecord.from_mapping(_row_to_mapping(row))
    except ValueError as exc:
        raise ConnectorValidationError(str(exc), connector_id=row["id"]) from exc


def _persist(record: ConnectorRecord) -> ConnectorRecord:
    now = time.time()
    with _lock, _transaction() as db:
        db.execute(
            """INSERT INTO connectors
               (id, display_name, type, version, transport_json, capabilities_json,
                auth_binding_json, profiles_json, permissions_json, status,
                metadata_json, origin, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 display_name = excluded.display_name,
                 type = excluded.type,
                 version = excluded.version,
                 transport_json = excluded.transport_json,
                 capabilities_json = excluded.capabilities_json,
                 auth_binding_json = excluded.auth_binding_json,
                 profiles_json = excluded.profiles_json,
                 permissions_json = excluded.permissions_json,
                 status = excluded.status,
                 metadata_json = excluded.metadata_json,
                 origin = excluded.origin,
                 updated_at = excluded.updated_at""",
            _record_to_row(record, now),
        )
    _invalidate_cache()
    return record


def create_connector(record: ConnectorRecord) -> ConnectorRecord:
    """Insert-only registration; raises ConnectorExistsError on duplicate."""
    if record.origin == "seed" and record.status is ConnectorStatus.ENABLED:
        prepared = record
    else:
        prepared = replace(record, status=ConnectorStatus.DISABLED)
    with _lock, _transaction() as db:
        existing = db.execute(
            "SELECT id FROM connectors WHERE id = ?",
            (prepared.id,),
        ).fetchone()
        if existing is not None:
            raise ConnectorExistsError(prepared.id)
        db.execute(
            """INSERT INTO connectors
               (id, display_name, type, version, transport_json, capabilities_json,
                auth_binding_json, profiles_json, permissions_json, status,
                metadata_json, origin, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            _record_to_row(prepared, time.time()),
        )
    _invalidate_cache()
    return prepared


def upsert_connector(record: ConnectorRecord) -> ConnectorRecord:
    """Register or update connector metadata; never persists secret values."""
    return _persist(record)


def get_connector(connector_id: str) -> ConnectorRecord | None:
    with _lock, _transaction() as db:
        row = db.execute(
            "SELECT * FROM connectors WHERE id = ?",
            (connector_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def list_connectors() -> list[ConnectorRecord]:
    with _lock, _transaction() as db:
        rows = db.execute("SELECT * FROM connectors ORDER BY id").fetchall()
    return [_row_to_record(row) for row in rows]


def delete_connector(connector_id: str) -> None:
    with _lock, _transaction() as db:
        cursor = db.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
        if cursor.rowcount < 1:
            raise ConnectorNotFoundError(connector_id)
    _invalidate_cache()


def _require_connector(connector_id: str) -> ConnectorRecord:
    record = get_connector(connector_id)
    if record is None:
        raise ConnectorNotFoundError(connector_id)
    return record


def set_status(connector_id: str, status: ConnectorStatus) -> ConnectorRecord:
    if not isinstance(status, ConnectorStatus):
        raise ConnectorValidationError(
            "status must be a ConnectorStatus",
            connector_id=connector_id,
        )
    record = _require_connector(connector_id)
    updated = replace(record, status=status)
    return _persist(updated)


def set_profile_permission(
    connector_id: str,
    profile: str,
    level: PermissionLevel,
) -> ConnectorRecord:
    if not isinstance(level, PermissionLevel):
        raise ConnectorValidationError(
            "level must be a PermissionLevel",
            connector_id=connector_id,
        )
    record = _require_connector(connector_id)
    permissions = dict(record.permissions)
    permissions[profile] = level
    updated = replace(record, permissions=permissions)
    return _persist(updated)


def replace_capabilities(
    connector_id: str,
    capabilities: tuple[ConnectorCapability, ...] | list[ConnectorCapability],
) -> ConnectorRecord:
    record = _require_connector(connector_id)
    caps = tuple(capabilities)
    updated = replace(record, capabilities=caps)
    return _persist(updated)
