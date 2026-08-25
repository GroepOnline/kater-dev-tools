from __future__ import annotations

from unittest.mock import patch

import pytest

from kater.connectors import internal as internal_connector
from kater.connectors import mcp_lifecycle, registry
from kater.connectors.errors import ConnectorUnavailableError
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
from kater.proxy.base import MockBackend


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()
    internal_connector.unregister_internal_handler("gateway")


def _bridge_record() -> ConnectorRecord:
    return ConnectorRecord(
        id="orgbridge",
        display_name="Org Bridge",
        type=ConnectorType.BRIDGE,
        version="1.0.0",
        transport=ConnectorTransport(kind="bridge", endpoint="https://bridge.invalid/mcp"),
        capabilities=(
            ConnectorCapability(id="orgbridge.echo", description="echo", discovered=True),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions={"ops": PermissionLevel.READ},
        status=ConnectorStatus.ENABLED,
    )


def test_bridge_transport_requires_endpoint() -> None:
    with pytest.raises(ValueError, match="bridge transport requires an endpoint"):
        ConnectorTransport(kind="bridge", endpoint="")


def test_bridge_invoke_routes_through_mcp_backend() -> None:
    record = _bridge_record()
    upsert_connector(record)
    backend = MockBackend(
        tools=[{"name": "echo", "description": "echo"}],
        responses={"echo": {"content": [{"type": "text", "text": "bridged"}]}},
    )

    with patch.object(mcp_lifecycle, "_create_backend", return_value=backend):
        result = registry.invoke("orgbridge", "orgbridge.echo", {"m": "hi"}, profile="ops")

    assert result["content"][0]["text"] == "bridged"


def _internal_record() -> ConnectorRecord:
    return ConnectorRecord(
        id="gateway",
        display_name="Gateway",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(ConnectorCapability(id="gateway.ping", description="ping"),),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions={"ops": PermissionLevel.READ},
        status=ConnectorStatus.ENABLED,
    )


def test_internal_invoke_fails_closed_without_handler() -> None:
    upsert_connector(_internal_record())
    with pytest.raises(ConnectorUnavailableError) as exc:
        registry.invoke("gateway", "gateway.ping", {}, profile="ops")
    assert exc.value.code == "no_internal_handler"


def test_internal_invoke_dispatches_to_registered_handler() -> None:
    upsert_connector(_internal_record())
    calls: list[str] = []

    def handler(record, capability_id, arguments):
        calls.append(capability_id)
        return {"pong": True, "connector": record.id}

    internal_connector.register_internal_handler("gateway", handler)
    result = registry.invoke("gateway", "gateway.ping", {"_kater_route": "x"}, profile="ops")

    assert result == {"pong": True, "connector": "gateway"}
    assert calls == ["gateway.ping"]


def test_internal_handler_receives_route_stripped_arguments() -> None:
    upsert_connector(_internal_record())
    seen: dict = {}

    def handler(record, capability_id, arguments):
        seen.update(arguments)
        return {"ok": True}

    internal_connector.register_internal_handler("gateway", handler)
    registry.invoke("gateway", "gateway.ping", {"a": 1, "_kater_route": "x"}, profile="ops")

    assert seen == {"a": 1}
