"""Connector lifecycle facade — register, validate, enable, invoke (in-process only)."""

from __future__ import annotations

from typing import Any

from kater.connectors import api as api_connector
from kater.connectors import mcp_lifecycle
from kater.connectors.auth import assert_auth, binding_is_satisfied, missing_auth_names, redact_text
from kater.connectors.errors import (
    ConnectorCapabilityError,
    ConnectorError,
    ConnectorNotFoundError,
    ConnectorUnavailableError,
    ConnectorValidationError,
)
from kater.connectors.health import evaluate_health
from kater.connectors.models import (
    AuthBindingRef,
    ConnectorCapability,
    ConnectorHealth,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    ConnectorView,
    PermissionLevel,
)
from kater.connectors.policy import assert_profile_access
from kater.connectors.store import (
    create_connector,
    delete_connector,
    get_connector,
    list_connectors,
    replace_capabilities,
    set_profile_permission,
    set_status,
    upsert_connector,
)


def discover_mcp(transport: ConnectorTransport | dict[str, Any]) -> list:
    return mcp_lifecycle.discover_mcp(transport)


def _require(connector_id: str) -> ConnectorRecord:
    record = get_connector(connector_id)
    if record is None:
        raise ConnectorNotFoundError(connector_id)
    return record


def register(spec: dict[str, Any]) -> ConnectorRecord:
    payload = dict(spec)
    payload.setdefault("status", ConnectorStatus.DISABLED.value)
    payload.setdefault("permissions", {})
    record = ConnectorRecord.from_mapping(payload)
    created = create_connector(record)
    return created


def validate(connector_id: str) -> ConnectorRecord:
    record = _require(connector_id)
    if record.type is ConnectorType.MCP:
        capabilities = mcp_lifecycle.discover(record)
    elif record.type is ConnectorType.API:
        capabilities = api_connector.discover(record)
    elif record.type is ConnectorType.INTERNAL:
        capabilities = list(record.capabilities)
    else:
        raise ConnectorValidationError(
            f"validation not supported for connector type {record.type.value!r}",
            connector_id=connector_id,
        )
    replace_capabilities(connector_id, capabilities)
    set_status(connector_id, ConnectorStatus.VALIDATED)
    return _require(connector_id)


def bind_auth(connector_id: str, binding: AuthBindingRef) -> ConnectorRecord:
    record = _require(connector_id)
    updated = ConnectorRecord(
        id=record.id,
        display_name=record.display_name,
        type=record.type,
        version=record.version,
        transport=record.transport,
        capabilities=record.capabilities,
        auth_binding=binding,
        profiles=record.profiles,
        permissions=record.permissions,
        status=record.status,
        metadata=record.metadata,
        origin=record.origin,
    )
    return upsert_connector(updated)


def probe(connector_id: str) -> ConnectorHealth:
    return evaluate_health(_require(connector_id))


def enable(
    connector_id: str,
    *,
    profile: str,
    level: PermissionLevel = PermissionLevel.READ,
) -> ConnectorRecord:
    set_profile_permission(connector_id, profile, level)
    set_status(connector_id, ConnectorStatus.ENABLED)
    return _require(connector_id)


def disable(connector_id: str) -> ConnectorRecord:
    set_status(connector_id, ConnectorStatus.DISABLED)
    return _require(connector_id)


def _effective_capability(
    record: ConnectorRecord,
    capability_id: str,
    arguments: dict[str, Any],
) -> ConnectorCapability | None:
    capability = record.capability(capability_id)
    if capability is None:
        return None
    if capability_id == "clickhouse.query":
        query = str((arguments or {}).get("query") or "").strip().upper()
        if query.startswith(("INSERT", "ALTER", "DROP")):
            return ConnectorCapability(
                id=capability.id,
                description=capability.description,
                mutation=True,
                input_schema=capability.input_schema,
                discovered=capability.discovered,
            )
    return capability


def invoke(
    connector_id: str,
    capability_id: str,
    arguments: dict[str, Any],
    *,
    profile: str,
) -> dict[str, Any]:
    record = _require(connector_id)
    assert_auth(record)
    capability = _effective_capability(record, capability_id, arguments)
    if capability is None:
        raise ConnectorCapabilityError(
            f"capability {capability_id!r} not found on connector {connector_id!r}",
            connector_id=connector_id,
        )
    assert_profile_access(
        record,
        profile,
        capability_id,
        mutation=capability.mutation,
    )
    try:
        if record.type is ConnectorType.MCP:
            return mcp_lifecycle.invoke(record, capability_id, arguments)
        if record.type is ConnectorType.API:
            return api_connector.invoke(record, capability_id, arguments)
        raise ConnectorUnavailableError(
            f"invoke not available for connector type {record.type.value!r}",
            connector_id=connector_id,
        )
    except ConnectorError:
        raise
    except Exception as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=connector_id,
        ) from exc


def update(connector_id: str, **patch: Any) -> ConnectorRecord:
    record = _require(connector_id)
    data = record.as_dict()
    data.update(patch)
    updated = ConnectorRecord.from_mapping(data)
    return upsert_connector(updated)


def remove(connector_id: str) -> None:
    delete_connector(connector_id)


def inventory(profile: str) -> list[ConnectorView]:
    views: list[ConnectorView] = []
    for record in list_connectors():
        if record.profiles and profile not in record.profiles:
            continue
        health = evaluate_health(record)
        configured = binding_is_satisfied(record.auth_binding, connector_id=record.id)
        missing = tuple(missing_auth_names(record.auth_binding, connector_id=record.id))
        views.append(
            ConnectorView(
                record=record,
                health=health,
                configured=configured,
                missing_auth=missing,
            )
        )
    return views
