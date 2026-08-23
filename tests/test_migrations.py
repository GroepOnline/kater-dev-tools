from __future__ import annotations

import sqlite3

import pytest

from kater import migrations, storage
from kater.capabilities import store as capabilities_store
from kater.control_plane import store as control_store
from kater.migrations import Migration, MigrationError

BASELINE_TABLES = (
    "events",
    "gate_audit",
    "control_route_candidates",
    "control_quota_windows",
    "control_routing_decisions",
    "control_route_affinity",
    "control_capabilities",
)

POST_BASELINE_TABLES = (
    "browser_sessions",
    "browser_actions",
    "automations",
    "remote_contexts",
    "usage_events",
    "capability_audit",
    "automation_meta",
    "connectors",
)

LEGACY_EVENTS_DDL = """
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
"""


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "kater.db"


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_fresh_database_gets_the_full_baseline(db_path) -> None:
    results = migrations.run_migrations(db_path)

    assert [r.status for r in results] == ["applied"] * len(migrations.MIGRATIONS)
    conn = sqlite3.connect(db_path)
    try:
        tables = _tables(conn)
        assert set(BASELINE_TABLES) <= tables
        assert migrations.SCHEMA_TABLE in tables
        recorded = conn.execute(
            f"SELECT version, name, checksum FROM {migrations.SCHEMA_TABLE}"  # noqa: S608
        ).fetchall()
    finally:
        conn.close()
    assert [(row[0], row[1]) for row in recorded] == [
        (m.version, m.name) for m in migrations.MIGRATIONS
    ]
    assert recorded[0][2] == migrations.MIGRATIONS[0].checksum
    assert set(POST_BASELINE_TABLES) <= tables

    status = migrations.schema_status(db_path)
    assert status["current_version"] == migrations.latest_version()
    assert status["latest_version"] == 9
    assert any(m.name == "usage_events" for m in migrations.MIGRATIONS)
    assert status["pending"] == []
    assert status["dirty"] is False
    assert status["database"] == str(db_path)


def test_run_migrations_is_idempotent(db_path) -> None:
    migrations.run_migrations(db_path)

    second = migrations.run_migrations(db_path)

    assert [r.status for r in second] == ["skipped"] * len(migrations.MIGRATIONS)


def test_dry_run_reports_pending_without_touching_the_database(db_path) -> None:
    results = migrations.run_migrations(db_path, dry_run=True)

    assert [r.status for r in results] == ["pending"] * len(migrations.MIGRATIONS)
    conn = sqlite3.connect(db_path)
    try:
        assert _tables(conn) == set()
    finally:
        conn.close()
    status = migrations.schema_status(db_path)
    assert status["current_version"] == 0
    assert [entry["version"] for entry in status["pending"]] == [
        m.version for m in migrations.MIGRATIONS
    ]


def test_legacy_database_adopts_the_baseline_without_losing_rows(db_path) -> None:
    legacy = sqlite3.connect(db_path)
    try:
        legacy.executescript(LEGACY_EVENTS_DDL)
        legacy.execute(
            "INSERT INTO events (type, name, timestamp, metadata) VALUES (?, ?, ?, ?)",
            ("tool_call", "github", 1.0, "{}"),
        )
        legacy.commit()
    finally:
        legacy.close()

    results = migrations.run_migrations(db_path)

    assert [r.status for r in results] == ["applied"] * len(migrations.MIGRATIONS)
    conn = sqlite3.connect(db_path)
    try:
        assert set(BASELINE_TABLES) <= _tables(conn)
        rows = conn.execute("SELECT type, name FROM events").fetchall()
    finally:
        conn.close()
    assert rows == [("tool_call", "github")]


def test_upgrade_marks_pre_v7_automations_as_already_seeded(db_path, monkeypatch) -> None:
    """Adopting an existing install must not re-run the built-in default seed."""
    monkeypatch.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS[:6])
    migrations.run_migrations(db_path)
    monkeypatch.undo()

    conn = sqlite3.connect(db_path)
    try:
        # A customised, disabled built-in; the other built-ins were deleted.
        conn.execute(
            """INSERT INTO automations
               (id, name, enabled, kind, schedule_seconds, config, created_at, updated_at)
               VALUES ('auto_doctor_watch', 'Doctor watch', 0, 'doctor', 999, '{}', 1.0, 1.0)"""
        )
        conn.commit()
    finally:
        conn.close()

    migrations.run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        marker = conn.execute(
            "SELECT value FROM automation_meta WHERE key = 'defaults_seeded'"
        ).fetchone()
        rows = conn.execute(
            "SELECT id, enabled, schedule_seconds FROM automations"
        ).fetchall()
    finally:
        conn.close()
    assert marker is not None
    assert rows == [("auto_doctor_watch", 0, 999)]


def test_fresh_database_is_not_marked_as_seeded(db_path) -> None:
    migrations.run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM automation_meta").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM automations").fetchone()[0] == 0
    finally:
        conn.close()


def test_checksum_drift_on_an_applied_version_is_fatal(db_path) -> None:
    migrations.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"UPDATE {migrations.SCHEMA_TABLE} SET checksum = ? WHERE version = 1",  # noqa: S608
            ("0" * 64,),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(MigrationError, match="released migration was edited"):
        migrations.run_migrations(db_path)

    assert migrations.schema_status(db_path)["dirty"] is True


def test_failing_migration_rolls_back_and_records_nothing(db_path, monkeypatch) -> None:
    broken = Migration(
        version=999,
        name="broken",
        statements=(
            "CREATE TABLE IF NOT EXISTS broken_marker (id INTEGER PRIMARY KEY)",
            "THIS IS NOT SQL",
        ),
    )
    monkeypatch.setattr(migrations, "MIGRATIONS", (*migrations.MIGRATIONS, broken))

    with pytest.raises(MigrationError, match="rolled back"):
        migrations.run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        tables = _tables(conn)
        versions = [
            row[0]
            for row in conn.execute(
                f"SELECT version FROM {migrations.SCHEMA_TABLE}"  # noqa: S608
            )
        ]
    finally:
        conn.close()
    assert "broken_marker" not in tables
    assert versions == [m.version for m in migrations.MIGRATIONS if m.version != 999]
    # Migrations that ran before the failure stayed committed.
    assert set(BASELINE_TABLES) <= tables
    assert set(POST_BASELINE_TABLES) <= tables


def test_ensure_migrated_writes_nothing_when_up_to_date(db_path) -> None:
    migrations.run_migrations(db_path)

    conn = migrations.connect(db_path)
    try:
        statements: list[str] = []
        conn.set_trace_callback(statements.append)
        changes_before = conn.total_changes

        migrations.ensure_migrated(conn)

        conn.set_trace_callback(None)
        assert conn.total_changes == changes_before
        assert statements  # current-check + checksum drift read
        assert all(s.strip().upper().startswith("SELECT") for s in statements)
    finally:
        conn.close()


def test_ensure_migrated_bootstraps_an_empty_database(db_path) -> None:
    migrations.ensure_migrated(db_path)

    conn = sqlite3.connect(db_path)
    try:
        assert set(BASELINE_TABLES) <= _tables(conn)
    finally:
        conn.close()


def test_ensure_migrated_detects_checksum_drift(db_path) -> None:
    migrations.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"UPDATE {migrations.SCHEMA_TABLE} SET checksum = ? WHERE version = 1",  # noqa: S608
            ("0" * 64,),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(MigrationError, match="released migration was edited"):
        migrations.ensure_migrated(db_path)


def test_migration_checksum_ignores_formatting_only_changes() -> None:
    one = Migration(version=1, name="x", statements=("CREATE TABLE a (id INTEGER)",))
    two = Migration(version=1, name="x", statements=("CREATE   TABLE a\n  (id INTEGER)",))
    three = Migration(version=1, name="x", statements=("CREATE TABLE b (id INTEGER)",))

    assert one.checksum == two.checksum
    assert one.checksum != three.checksum


def test_pending_and_applied_versions_track_each_other(db_path) -> None:
    conn = migrations.connect(db_path)
    try:
        assert [m.version for m in migrations.pending(conn)] == [
            m.version for m in migrations.MIGRATIONS
        ]

        migrations.run_migrations(conn)

        assert migrations.pending(conn) == []
        assert migrations.applied_versions(conn) == {
            m.version: m.checksum for m in migrations.MIGRATIONS
        }
    finally:
        conn.close()


def _schema_objects(conn: sqlite3.Connection) -> dict[tuple[str, str], str]:
    return {
        (row[0], row[1]): " ".join((row[2] or "").split())
        for row in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
        if row[1] != migrations.SCHEMA_TABLE
    }


def test_baseline_matches_the_ad_hoc_ddl_of_every_owning_module() -> None:
    """The baseline must stay a faithful copy while the stores still self-create."""
    legacy_schemas = [
        getattr(module, "_SCHEMA", None) for module in (capabilities_store, control_store, storage)
    ]
    if any(schema is None for schema in legacy_schemas):
        pytest.skip("a store no longer self-creates its tables; the baseline owns them now")

    legacy = sqlite3.connect(":memory:")
    fresh = sqlite3.connect(":memory:")
    try:
        for schema in legacy_schemas:
            assert isinstance(schema, str)
            legacy.executescript(schema)
        migrations.run_migrations(fresh)

        legacy_objects = _schema_objects(legacy)
        fresh_objects = _schema_objects(fresh)
        # Later migrations add tables beyond the ad-hoc store schemas under test.
        assert {k: v for k, v in fresh_objects.items() if k in legacy_objects} == legacy_objects
        assert set(POST_BASELINE_TABLES) <= {name for _kind, name in fresh_objects}
    finally:
        legacy.close()
        fresh.close()


def test_default_path_resolution_follows_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    migrations.ensure_migrated()

    assert migrations.resolve_db_path() == tmp_path / ".kater" / "kater.db"
    status = migrations.schema_status()
    assert status["current_version"] == migrations.latest_version()
    assert status["database"] == str(tmp_path / ".kater" / "kater.db")
