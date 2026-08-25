"""Connector catalog HTTP routes: admin gate, fail-closed, redacted errors.

In-process ROUTER only. No live provider calls, no secret values in assertions.
"""

from __future__ import annotations

import json

import pytest

from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    PermissionLevel,
)
from kater.connectors.store import clear_connector_state, get_connector, upsert_connector
from tests._rest import call


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    from kater.settings import invalidate_settings_cache

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    invalidate_settings_cache()
    clear_connector_state()
    yield
    clear_connector_state()


def _internal_record(
    *,
    status: ConnectorStatus = ConnectorStatus.DISABLED,
    permissions: dict[str, PermissionLevel] | None = None,
) -> ConnectorRecord:
    return ConnectorRecord(
        id="httptest",
        display_name="HTTP Test",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(ConnectorCapability(id="httptest.read", description="read"),),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions=permissions or {},
        status=status,
        origin="dynamic",
    )


def test_list_is_readable_without_admin():
    upsert_connector(_internal_record())
    resp = call("GET", "/api/connectors", query={"profile": ["ops"]})
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["profile"] == "ops"
    ids = {row["id"] for row in resp.payload["connectors"]}
    assert "httptest" in ids


def test_mutation_requires_admin():
    upsert_connector(_internal_record())
    resp = call("POST", "/api/connectors/httptest/enable", body={"profile": "ops"})
    assert resp.status == 403
    assert resp.payload is not None
    assert resp.payload["error"] == "admin credential required for catalog mutations"
    # Row is untouched by the denied mutation.
    assert get_connector("httptest").status is ConnectorStatus.DISABLED


def test_admin_enable_then_disable():
    upsert_connector(_internal_record())
    headers = {"authorization": "Bearer admin-secret"}

    enabled = call(
        "POST",
        "/api/connectors/httptest/enable",
        body={"profile": "ops", "level": "read"},
        headers=headers,
    )
    assert enabled.status == 200
    assert get_connector("httptest").status is ConnectorStatus.ENABLED

    disabled = call("POST", "/api/connectors/httptest/disable", body={}, headers=headers)
    assert disabled.status == 200
    assert get_connector("httptest").status is ConnectorStatus.DISABLED


def test_enable_rejects_invalid_level():
    upsert_connector(_internal_record())
    headers = {"authorization": "Bearer admin-secret"}
    resp = call(
        "POST",
        "/api/connectors/httptest/enable",
        body={"profile": "ops", "level": "superuser"},
        headers=headers,
    )
    assert resp.status == 400


def test_enable_unknown_connector_maps_to_404():
    headers = {"authorization": "Bearer admin-secret"}
    resp = call(
        "POST",
        "/api/connectors/does-not-exist/enable",
        body={"profile": "ops"},
        headers=headers,
    )
    assert resp.status == 404
    assert resp.payload is not None
    assert resp.payload["error"] == "connector_not_found"


def test_invoke_requires_capability_in_body():
    upsert_connector(
        _internal_record(status=ConnectorStatus.ENABLED, permissions={"ops": PermissionLevel.READ})
    )
    headers = {"authorization": "Bearer admin-secret"}
    resp = call(
        "POST",
        "/api/connectors/httptest/invoke",
        body={"profile": "ops"},
        headers=headers,
    )
    assert resp.status == 400
    assert resp.payload is not None
    assert "capability" in resp.payload["error"]


def test_invoke_internal_without_handler_fails_closed_and_redacted():
    upsert_connector(
        _internal_record(status=ConnectorStatus.ENABLED, permissions={"ops": PermissionLevel.READ})
    )
    headers = {"authorization": "Bearer admin-secret"}
    resp = call(
        "POST",
        "/api/connectors/httptest/invoke",
        body={"profile": "ops", "capability": "httptest.read"},
        headers=headers,
    )
    assert resp.status == 409
    assert resp.payload is not None
    assert resp.payload["error"] == "unavailable"
    assert "Bearer admin-secret" not in json.dumps(resp.payload)
