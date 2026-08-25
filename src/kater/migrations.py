"""Forward-only schema migrations for the shared Kater SQLite database.

Every Kater subsystem (telemetry, gate audit, control-plane routing,
capability registry) stores its state in one SQLite file — `.kater/kater.db`
by default. Historically each module created its own tables on connect with
ad-hoc ``CREATE TABLE IF NOT EXISTS`` plus best-effort ``ALTER TABLE ADD
COLUMN`` whose duplicate-column errors were swallowed. That works until two
installs disagree about what "current" means, and there is no way to tell
whether a database is up to date, behind, or hand-edited.

This module is the single source of truth for schema evolution.

Contract
--------
* Migrations are **append-only**. Never edit a released migration; add a new
  one. An applied version whose recorded checksum no longer matches the code
  raises :class:`MigrationError` instead of silently diverging.
* Migrations are **forward-only**. There is no downgrade path; a rollback is
  a restore from a backup bundle (see :mod:`kater.backup`).
* Version 1 is the **baseline**: the DDL of every table that existed before
  this module, copied faithfully from the owning modules. Every statement is
  ``IF NOT EXISTS``, so applying the baseline to an already-populated legacy
  database is a no-op that simply records the version row. That is how
  existing installs adopt the migration system without a dump/reload.
* The runner tolerates tables it does not own. Anything not listed here is
  left untouched, so a subsystem may still bootstrap its own tables while it
  is being developed, then fold them into a new migration.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from kater.settings import load_settings

_log = logging.getLogger("kater.migrations")

SCHEMA_TABLE = "schema_migrations"

BUSY_TIMEOUT_MS = 10_000

MigrationStatus = Literal["applied", "skipped", "pending"]


class MigrationError(RuntimeError):
    """Raised when the schema cannot be brought to the expected version."""


@dataclass(frozen=True)
class Migration:
    """One ordered, atomically applied batch of DDL statements."""

    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        """sha256 over the whitespace-normalised statements."""
        normalised = ";\n".join(" ".join(s.split()) for s in self.statements)
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MigrationResult:
    version: int
    name: str
    status: MigrationStatus


_BASELINE = (
    # ── kater.storage: telemetry + gate audit ──────────────────────
    """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        name TEXT NOT NULL,
        timestamp REAL NOT NULL,
        duration_ms REAL DEFAULT 0,
        success INTEGER DEFAULT 1,
        profile TEXT,
        metadata TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_events_name ON events(name)",
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)",
    """CREATE TABLE IF NOT EXISTS gate_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        action TEXT NOT NULL,
        pr_number INTEGER NOT NULL,
        verdict TEXT NOT NULL,
        reasons TEXT NOT NULL,
        expected_head_sha TEXT,
        applied_head_sha TEXT,
        actor TEXT,
        detail TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_gate_audit_pr ON gate_audit(pr_number)",
    "CREATE INDEX IF NOT EXISTS idx_gate_audit_ts ON gate_audit(timestamp)",
    # ── kater.control_plane.store: routing state ───────────────────
    """CREATE TABLE IF NOT EXISTS control_route_candidates (
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
    )""",
    """CREATE INDEX IF NOT EXISTS idx_control_route_capability
        ON control_route_candidates(capability)""",
    """CREATE INDEX IF NOT EXISTS idx_control_route_backend
        ON control_route_candidates(backend, tool_name)""",
    """CREATE TABLE IF NOT EXISTS control_quota_windows (
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
    )""",
    """CREATE TABLE IF NOT EXISTS control_routing_decisions (
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
    )""",
    """CREATE INDEX IF NOT EXISTS idx_control_decision_capability
        ON control_routing_decisions(capability, id DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_control_decision_context
        ON control_routing_decisions(context_id, id DESC)""",
    """CREATE TABLE IF NOT EXISTS control_route_affinity (
        capability TEXT NOT NULL,
        context_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY (capability, context_id)
    )""",
    # ── kater.capabilities.store: capability registry ──────────────
    """CREATE TABLE IF NOT EXISTS control_capabilities (
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
        method TEXT,
        path TEXT,
        timeout_seconds REAL,
        mutation INTEGER NOT NULL DEFAULT 0,
        idempotency_required INTEGER NOT NULL DEFAULT 0,
        updated_at REAL NOT NULL,
        PRIMARY KEY (capability_id, version)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_control_cap_lifecycle
        ON control_capabilities(lifecycle_state)""",
    """CREATE INDEX IF NOT EXISTS idx_control_cap_package
        ON control_capabilities(package_id)""",
)

_BROWSER_V2 = (
    """CREATE TABLE IF NOT EXISTS browser_sessions (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_browser_sessions_state ON browser_sessions(state)",
    """CREATE TABLE IF NOT EXISTS browser_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        ok INTEGER NOT NULL DEFAULT 1,
        started_at REAL NOT NULL,
        duration_ms REAL NOT NULL DEFAULT 0,
        url TEXT,
        error TEXT,
        detail TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_browser_actions_session ON browser_actions(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_browser_actions_started ON browser_actions(started_at)",
)

_AUTOMATIONS_V3 = (
    """CREATE TABLE IF NOT EXISTS automations (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_automations_enabled ON automations(enabled)",
)

_REMOTE_CONTEXTS_V4 = (
    """CREATE TABLE IF NOT EXISTS remote_contexts (
        context_id TEXT PRIMARY KEY,
        principal_id TEXT NOT NULL,
        label TEXT,
        profile TEXT NOT NULL DEFAULT 'core',
        scopes TEXT NOT NULL DEFAULT '[]',
        repository TEXT,
        environment TEXT,
        allowed_capabilities TEXT NOT NULL DEFAULT '[]',
        expires_at REAL,
        revoked_at REAL,
        created_at REAL NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_remote_contexts_principal ON remote_contexts(principal_id)",
)

_USAGE_EVENTS_V5 = (
    """CREATE TABLE IF NOT EXISTS usage_events (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_usage_events_ts ON usage_events(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_usage_events_cap ON usage_events(capability)",
)

_CAPABILITY_AUDIT_V6 = (
    """CREATE TABLE IF NOT EXISTS capability_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        capability_id TEXT NOT NULL,
        principal_id TEXT,
        context_id TEXT,
        outcome TEXT NOT NULL,
        reason TEXT,
        duration_ms REAL,
        profile TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_capability_audit_ts ON capability_audit(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_capability_audit_cap ON capability_audit(capability_id)",
)

_AUTOMATION_META_V7 = (
    """CREATE TABLE IF NOT EXISTS automation_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at REAL NOT NULL
    )""",
)

# An install that already had automations before ``automation_meta`` existed has,
# by definition, been seeded once. Record the marker (key kept in sync with
# ``kater.automations.store.DEFAULTS_SEEDED_KEY``) so the engine's default upsert
# does not run again on the next start, resurrecting deleted built-ins and
# resetting customised ones. A fresh database has no automations at this point,
# so the insert selects no row and the engine seeds the defaults normally.
_AUTOMATION_DEFAULTS_ADOPTED_V8 = (
    """INSERT INTO automation_meta (key, value, updated_at)
       SELECT 'defaults_seeded', '1', CAST(strftime('%s', 'now') AS REAL)
       WHERE EXISTS (SELECT 1 FROM automations)
         AND NOT EXISTS (SELECT 1 FROM automation_meta WHERE key = 'defaults_seeded')""",
)

_CONNECTORS_V9 = (
    """CREATE TABLE IF NOT EXISTS connectors (
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
    )""",
)

#: Ordered, append-only. Add new versions at the end; never edit a released one.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="baseline", statements=_BASELINE),
    Migration(version=2, name="browser_lane", statements=_BROWSER_V2),
    Migration(version=3, name="automations", statements=_AUTOMATIONS_V3),
    Migration(version=4, name="remote_contexts", statements=_REMOTE_CONTEXTS_V4),
    Migration(version=5, name="usage_events", statements=_USAGE_EVENTS_V5),
    Migration(version=6, name="capability_audit", statements=_CAPABILITY_AUDIT_V6),
    Migration(version=7, name="automation_meta", statements=_AUTOMATION_META_V7),
    Migration(
        version=8,
        name="automation_defaults_adopted",
        statements=_AUTOMATION_DEFAULTS_ADOPTED_V8,
    ),
    Migration(version=9, name="connectors", statements=_CONNECTORS_V9),
)

_CREATE_SCHEMA_TABLE = f"""CREATE TABLE IF NOT EXISTS {SCHEMA_TABLE} (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at REAL NOT NULL,
    checksum TEXT NOT NULL
)"""
_SELECT_APPLIED = f"SELECT version, name, applied_at, checksum FROM {SCHEMA_TABLE} ORDER BY version"  # noqa: S608
_INSERT_APPLIED = (
    f"INSERT INTO {SCHEMA_TABLE} (version, name, applied_at, checksum) VALUES (?, ?, ?, ?)"  # noqa: S608
)


# ── Connection plumbing ────────────────────────────────────────────


def resolve_db_path() -> Path:
    """Locate the shared database exactly like :mod:`kater.storage` does."""
    configured = Path(load_settings().db_path).expanduser()
    return configured if configured.is_absolute() else Path.cwd() / configured


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the migration connection with the stores' WAL/busy-timeout setup."""
    target = Path(path) if path is not None else resolve_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return conn


@contextmanager
def _session(target: sqlite3.Connection | Path | str | None) -> Iterator[sqlite3.Connection]:
    """Yield a usable connection, closing only the ones we opened ourselves."""
    if isinstance(target, sqlite3.Connection):
        yield target
        return
    conn = connect(target)
    try:
        yield conn
    finally:
        conn.close()


def _database_name(conn: sqlite3.Connection) -> str:
    try:
        for row in conn.execute("PRAGMA database_list"):
            if row[1] == "main":
                return str(row[2]) or ":memory:"
    except sqlite3.DatabaseError:  # pragma: no cover - defensive
        pass
    return ":memory:"


# ── Version bookkeeping ────────────────────────────────────────────


def applied_versions(conn: sqlite3.Connection) -> dict[int, str]:
    """Return ``{version: checksum}``, creating the bookkeeping table if absent."""
    conn.execute(_CREATE_SCHEMA_TABLE)
    conn.commit()
    return _read_applied(conn)


def _read_applied(conn: sqlite3.Connection) -> dict[int, str]:
    """Read recorded versions without writing; empty when the table is absent."""
    try:
        rows = conn.execute(_SELECT_APPLIED).fetchall()
    except sqlite3.OperationalError:
        return {}
    # Positional access: callers may hand us a connection without a row factory.
    return {int(row[0]): str(row[3]) for row in rows}


def _drift(applied: dict[int, str]) -> list[str]:
    """Describe disagreements between recorded history and the code."""
    known = {m.version: m for m in MIGRATIONS}
    problems: list[str] = []
    for version, checksum in sorted(applied.items()):
        migration = known.get(version)
        if migration is None:
            problems.append(
                f"version {version} is recorded as applied but unknown to this Kater build "
                "(the database was written by a newer version)"
            )
        elif migration.checksum != checksum:
            problems.append(
                f"version {version} ({migration.name}) was applied with checksum "
                f"{checksum[:12]}… but the code now hashes to {migration.checksum[:12]}… — "
                "a released migration was edited; revert it and append a new migration instead"
            )
    return problems


def pending(conn: sqlite3.Connection) -> list[Migration]:
    """Migrations present in the code but not yet recorded in the database."""
    applied = _read_applied(conn)
    return [m for m in MIGRATIONS if m.version not in applied]


def latest_version() -> int:
    return max((m.version for m in MIGRATIONS), default=0)


# ── Runner ─────────────────────────────────────────────────────────


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    """Run one migration and record it, all inside a single transaction."""
    previous_isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            # BEGIN IMMEDIATE serialises writers, so re-check under the write
            # lock: another process may have applied this version between our
            # snapshot of the recorded versions and acquiring the lock. If so,
            # commit the empty transaction and treat it as already applied
            # instead of hitting a primary-key conflict on the insert.
            already = conn.execute(
                f"SELECT 1 FROM {SCHEMA_TABLE} WHERE version = ?",  # noqa: S608
                (migration.version,),
            ).fetchone()
            if already is not None:
                conn.execute("COMMIT")
                return
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                _INSERT_APPLIED,
                (migration.version, migration.name, time.time(), migration.checksum),
            )
        except Exception as exc:
            conn.execute("ROLLBACK")
            raise MigrationError(
                f"migration {migration.version} ({migration.name}) failed and was rolled back: "
                f"{exc}"
            ) from exc
        conn.execute("COMMIT")
    finally:
        conn.isolation_level = previous_isolation


def _raise_on_fatal_drift(applied: dict[int, str]) -> None:
    """Reject edited applied migrations; warn on unknown newer versions."""
    problems = _drift(applied)
    fatal = [p for p in problems if "was applied with checksum" in p]
    if fatal:
        raise MigrationError("; ".join(fatal))
    for problem in problems:
        _log.warning("schema drift: %s", problem)


def run_migrations(
    conn: sqlite3.Connection | Path | str | None = None,
    *,
    dry_run: bool = False,
) -> list[MigrationResult]:
    """Bring the database to the latest version, reporting what each version did.

    ``dry_run`` reports what would happen without touching the schema; already
    applied versions come back as ``skipped`` and the rest as ``pending``.
    """
    with _session(conn) as db:
        applied = _read_applied(db) if dry_run else applied_versions(db)
        _raise_on_fatal_drift(applied)

        results: list[MigrationResult] = []
        for migration in MIGRATIONS:
            if migration.version in applied:
                results.append(MigrationResult(migration.version, migration.name, "skipped"))
                continue
            if dry_run:
                results.append(MigrationResult(migration.version, migration.name, "pending"))
                continue
            _apply(db, migration)
            _log.info("applied migration %d (%s)", migration.version, migration.name)
            results.append(MigrationResult(migration.version, migration.name, "applied"))
        return results


def _is_current(conn: sqlite3.Connection) -> bool:
    """Single-SELECT check that every known version is already recorded."""
    if not MIGRATIONS:
        return True
    placeholders = ", ".join("?" for _ in MIGRATIONS)
    query = f"SELECT COUNT(*) FROM {SCHEMA_TABLE} WHERE version IN ({placeholders})"  # noqa: S608
    try:
        row = conn.execute(query, [m.version for m in MIGRATIONS]).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(row) and int(row[0]) == len(MIGRATIONS)


def ensure_migrated(conn: sqlite3.Connection | Path | str | None = None) -> None:
    """Idempotent startup hook: migrate when needed; always check checksum drift."""
    with _session(conn) as db:
        if _is_current(db):
            # Still verify recorded checksums match the code — otherwise a
            # drifted install would silently skip run_migrations' fatal check.
            _raise_on_fatal_drift(_read_applied(db))
            return
        run_migrations(db)


def schema_status(conn: sqlite3.Connection | Path | str | None = None) -> dict[str, Any]:
    """Report schema state for the CLI, the REST API and the dashboard.

    Read-only: a database that has never been migrated reports version 0 with
    every migration pending rather than acquiring the bookkeeping table.
    """
    with _session(conn) as db:
        try:
            rows = db.execute(_SELECT_APPLIED).fetchall()
        except sqlite3.OperationalError:
            rows = []
        database = _database_name(db)
    applied = {int(row[0]): str(row[3]) for row in rows}
    names = {m.version: m.name for m in MIGRATIONS}
    return {
        "current_version": max(applied, default=0),
        "latest_version": latest_version(),
        "pending": [
            {"version": m.version, "name": m.name} for m in MIGRATIONS if m.version not in applied
        ],
        "applied": [
            {
                "version": int(row[0]),
                "name": names.get(int(row[0]), str(row[1])),
                "applied_at": float(row[2]),
            }
            for row in rows
        ],
        "database": database,
        "dirty": bool(_drift(applied)),
    }
