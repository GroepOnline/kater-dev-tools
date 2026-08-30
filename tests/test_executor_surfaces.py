from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from kater.cli import app
from kater.connectors.internal import register_internal_handler, unregister_internal_handler
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
from kater.connectors.store import clear_connector_state, upsert_connector
from tests._rest import call

runner = CliRunner()


@pytest.fixture(autouse=True)
def catalog(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PROFILE", raising=False)
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    unregister_internal_handler("demoexec")
    yield
    unregister_internal_handler("demoexec")
    clear_connector_state()


def _record(*, permission: PermissionLevel = PermissionLevel.WRITE) -> ConnectorRecord:
    return ConnectorRecord(
        id="demoexec",
        display_name="Demo Executor",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(
            ConnectorCapability(id="demoexec.items.read", description="Read demo items"),
            ConnectorCapability(
                id="demoexec.items.create",
                description="Create a demo item",
                mutation=True,
                input_schema={"type": "object"},
            ),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions={"ops": permission},
        status=ConnectorStatus.ENABLED,
        origin="dynamic",
    )


def test_rest_search_is_readable_and_profile_filtered():
    upsert_connector(_record())
    response = call("GET", "/api/tools/search", query={"q": ["create demo"], "profile": ["ops"]})
    assert response.status == 200
    assert response.payload is not None
    ids = [tool["capability_id"] for tool in response.payload["tools"]]
    assert ids[0] == "demoexec.items.create"


def test_rest_execute_requires_admin_and_uses_executor():
    upsert_connector(_record())
    register_internal_handler("demoexec", lambda _record, _cap, args: {"created": args["name"]})
    body = {
        "capability_id": "demoexec.items.create",
        "profile": "ops",
        "arguments": {"name": "x"},
    }
    denied = call("POST", "/api/execute", body=body)
    assert denied.status == 403
    allowed = call(
        "POST",
        "/api/execute",
        body=body,
        headers={"authorization": "Bearer admin-secret"},
    )
    assert allowed.status == 200
    assert allowed.payload is not None
    assert allowed.payload["result"] == {"created": "x"}


def test_cli_search_and_execute():
    upsert_connector(_record())
    register_internal_handler("demoexec", lambda _record, _cap, args: {"echo": args})

    searched = runner.invoke(app, ["search-tools", "demo read", "--profile", "ops"])
    assert searched.exit_code == 0
    payload = json.loads(searched.stdout)
    assert payload["tools"][0]["capability_id"] == "demoexec.items.read"

    executed = runner.invoke(
        app,
        [
            "execute",
            "demoexec.items.create",
            "--profile",
            "ops",
            "--args",
            '{"name":"hello"}',
        ],
    )
    assert executed.exit_code == 0
    result = json.loads(executed.stdout)
    assert result["result"] == {"echo": {"name": "hello"}}


def test_cli_execute_cannot_bypass_profile_permission():
    upsert_connector(_record(permission=PermissionLevel.READ))
    register_internal_handler("demoexec", lambda _record, _cap, _args: {"should": "not run"})
    result = runner.invoke(
        app,
        ["execute", "demoexec.items.create", "--profile", "ops", "--args", "{}"],
    )
    assert result.exit_code == 1
    assert "needs write" in result.output
