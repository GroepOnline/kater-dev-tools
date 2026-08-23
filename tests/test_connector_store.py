from __future__ import annotations

import sqlite3

import pytest

from kater.connectors.errors import ConnectorExistsError, ConnectorValidationError
from kater.connectors.health import evaluate_health
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    HealthState,
    PermissionLevel,
)
from kater.connectors.store import (
    clear_connector_state,
    create_connector,
    get_connector,
    list_connectors,
    reload_store,
    set_profile_permission,
    set_status,
    upsert_connector,
)


def _sample_record(
    connector_id: str = "demo.connector",
    *,
    status: ConnectorStatus = ConnectorStatus.DISABLED,
    origin: str = "dynamic",
    metadata: dict | None = None,
) -> ConnectorRecord:
    return ConnectorRecord(
        id=connector_id,
        display_name="Demo Connector",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(ConnectorCapability(id="demo.read"),),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.ENV, ref="DEMO_TOKEN"),
        profiles=frozenset({"core"}),
        permissions={},
        status=status,
        metadata=metadata or {},
        origin=origin,
    )


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()


def test_create_and_get_connector() -> None:
    record = _sample_record()
    created = create_connector(record)
    assert created.status is ConnectorStatus.DISABLED
    loaded = get_connector(record.id)
    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.auth_binding.ref == "DEMO_TOKEN"
    assert loaded.capabilities[0].id == "demo.read"


def test_duplicate_create_raises() -> None:
    record = _sample_record()
    create_connector(record)
    with pytest.raises(ConnectorExistsError):
        create_connector(record)


def test_upsert_updates_existing_connector() -> None:
    record = _sample_record()
    create_connector(record)
    updated = upsert_connector(
        ConnectorRecord(
            id=record.id,
            display_name="Updated Demo",
            type=ConnectorType.INTERNAL,
            version="2.0.0",
            transport=ConnectorTransport(kind="native"),
            capabilities=(ConnectorCapability(id="demo.write", mutation=True),),
            auth_binding=record.auth_binding,
            status=ConnectorStatus.VALIDATED,
            origin="dynamic",
        )
    )
    assert updated.display_name == "Updated Demo"
    assert updated.version == "2.0.0"
    assert updated.status is ConnectorStatus.VALIDATED
    loaded = get_connector(record.id)
    assert loaded is not None
    assert loaded.display_name == "Updated Demo"


def test_malformed_transport_rejected_on_create() -> None:
    with pytest.raises(ValueError, match="transport"):
        ConnectorRecord(
            id="bad.transport",
            display_name="Bad",
            type=ConnectorType.MCP,
            version="1.0.0",
            transport=ConnectorTransport(kind="http", endpoint=""),
            auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        )


def test_metadata_with_secret_keys_rejected() -> None:
    with pytest.raises(ValueError, match="secret keys"):
        ConnectorRecord(
            id="bad.meta",
            display_name="Bad",
            type=ConnectorType.INTERNAL,
            version="1.0.0",
            transport=ConnectorTransport(kind="native"),
            auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
            metadata={"api_key": "should-not-live-here"},
        )


def test_restart_reload_preserves_state_without_health(tmp_path) -> None:
    record = _sample_record()
    create_connector(record)
    set_status(record.id, ConnectorStatus.DISABLED)
    set_profile_permission(record.id, "core", PermissionLevel.READ)

    reload_store()
    loaded = get_connector(record.id)
    assert loaded is not None
    assert loaded.status is ConnectorStatus.DISABLED
    assert loaded.permissions["core"] is PermissionLevel.READ
    assert loaded.auth_binding.ref == "DEMO_TOKEN"

    db_path = tmp_path / ".kater" / "kater.db"
    conn = sqlite3.connect(db_path)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(connectors)").fetchall()
    }
    conn.close()
    assert "health" not in columns

    health = evaluate_health(loaded, profile="core")
    assert health.state is HealthState.DISABLED


def test_enabled_stdio_mcp_is_healthy_without_http_endpoint() -> None:
    record = ConnectorRecord(
        id="github",
        display_name="GitHub",
        type=ConnectorType.MCP,
        version="1.0.0",
        transport=ConnectorTransport(kind="stdio", command="npx", args=("mcp",)),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        status=ConnectorStatus.ENABLED,
        origin="seed",
    )
    health = evaluate_health(record)
    assert health.state is HealthState.HEALTHY


def test_seed_enabled_connector_may_stay_enabled() -> None:
    record = _sample_record(status=ConnectorStatus.ENABLED, origin="seed")
    created = create_connector(record)
    assert created.status is ConnectorStatus.ENABLED


def test_dynamic_create_forces_disabled_even_if_enabled_requested() -> None:
    record = _sample_record(status=ConnectorStatus.ENABLED, origin="dynamic")
    created = create_connector(record)
    assert created.status is ConnectorStatus.DISABLED


def test_malformed_row_raises_validation_error(tmp_path) -> None:
    record = _sample_record("broken.row")
    create_connector(record)
    db_path = tmp_path / ".kater" / "kater.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE connectors SET transport_json = ? WHERE id = ?",
        ("not-json", record.id),
    )
    conn.commit()
    conn.close()
    reload_store()
    with pytest.raises(ConnectorValidationError):
        get_connector(record.id)


def test_list_connectors_returns_persisted_rows() -> None:
    create_connector(_sample_record("alpha.demo"))
    create_connector(_sample_record("beta.demo"))
    ids = [item.id for item in list_connectors()]
    assert ids == ["alpha.demo", "beta.demo"]
