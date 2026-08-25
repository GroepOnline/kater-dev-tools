from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from kater.cli import app
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

runner = CliRunner()


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()


def _internal_record(
    *,
    status: ConnectorStatus = ConnectorStatus.DISABLED,
    permissions: dict[str, PermissionLevel] | None = None,
) -> ConnectorRecord:
    return ConnectorRecord(
        id="clitest",
        display_name="CLI Test",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(ConnectorCapability(id="clitest.read", description="read"),),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions=permissions or {},
        status=status,
        origin="dynamic",
    )


def test_connector_list_json_reports_seeded_and_custom_rows():
    upsert_connector(_internal_record())
    result = runner.invoke(app, ["connector", "list", "--profile", "ops", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    ids = {row["id"] for row in payload["connectors"]}
    assert "clitest" in ids


def test_connector_enable_then_disable_persists_state():
    upsert_connector(_internal_record())

    enabled = runner.invoke(
        app, ["connector", "enable", "clitest", "--profile", "ops", "--level", "read"]
    )
    assert enabled.exit_code == 0
    record = get_connector("clitest")
    assert record is not None
    assert record.status is ConnectorStatus.ENABLED
    assert record.permission_for("ops") is PermissionLevel.READ

    disabled = runner.invoke(app, ["connector", "disable", "clitest"])
    assert disabled.exit_code == 0
    assert get_connector("clitest").status is ConnectorStatus.DISABLED


def test_connector_enable_rejects_invalid_level():
    upsert_connector(_internal_record())
    result = runner.invoke(
        app, ["connector", "enable", "clitest", "--profile", "ops", "--level", "superuser"]
    )
    assert result.exit_code == 1
    assert "invalid level" in result.stdout


def test_connector_enable_unknown_connector_fails_closed():
    result = runner.invoke(app, ["connector", "enable", "nope", "--profile", "ops"])
    assert result.exit_code == 1
    assert "connector_not_found" in result.stdout


def test_connector_invoke_rejects_non_object_args():
    upsert_connector(_internal_record(status=ConnectorStatus.ENABLED))
    result = runner.invoke(
        app,
        ["connector", "invoke", "clitest", "clitest.read", "--profile", "ops", "--args", "[1,2]"],
    )
    assert result.exit_code == 1
    assert "must be a JSON object" in result.stdout


def test_connector_invoke_internal_without_handler_fails_closed():
    upsert_connector(
        _internal_record(
            status=ConnectorStatus.ENABLED,
            permissions={"ops": PermissionLevel.READ},
        )
    )
    result = runner.invoke(
        app,
        ["connector", "invoke", "clitest", "clitest.read", "--profile", "ops"],
    )
    assert result.exit_code == 1
    assert "no_internal_handler" in result.stdout
