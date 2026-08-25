"""Live connector health evaluation (never persisted)."""

from __future__ import annotations

from kater.connectors.auth import missing_auth_names
from kater.connectors.models import (
    ConnectorHealth,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorType,
    HealthState,
    PermissionLevel,
)


def evaluate_health(
    record: ConnectorRecord,
    *,
    profile: str | None = None,
    probe_ok: bool | None = None,
) -> ConnectorHealth:
    """Compute current health for one connector catalog entry."""
    capability_ids = tuple(cap.id for cap in record.capabilities)

    if record.status is ConnectorStatus.DISABLED:
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.DISABLED,
            detail="connector is disabled",
            capabilities=capability_ids,
        )

    if record.metadata.get("scope") == "out_of_scope":
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.UNSUPPORTED,
            detail="connector is out of scope for this runtime",
            capabilities=capability_ids,
        )

    if profile is not None and record.permission_for(profile) is PermissionLevel.DISABLED:
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.POLICY_BLOCKED,
            detail=f"profile {profile!r} is blocked for this connector",
            capabilities=capability_ids,
        )

    if record.status is ConnectorStatus.ENABLED:
        missing = missing_auth_names(record.auth_binding, connector_id=record.id)
        if missing:
            return ConnectorHealth(
                connector_id=record.id,
                state=HealthState.AUTH_MISSING,
                detail=f"missing auth: {', '.join(missing)}",
                capabilities=capability_ids,
            )

    if record.metadata.get("unsupported_runtime") is True and record.type in {
        ConnectorType.API,
        ConnectorType.MCP,
        ConnectorType.BRIDGE,
    }:
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.UNSUPPORTED,
            detail="connector runtime is unsupported here",
            capabilities=capability_ids,
        )

    if (
        record.status is ConnectorStatus.ENABLED
        and record.transport.kind in {"http", "sse", "bridge"}
        and not (record.transport.endpoint or "").strip()
    ):
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.UNAVAILABLE,
            detail="enabled connector has no endpoint configured",
            capabilities=capability_ids,
        )

    if record.status is not ConnectorStatus.ENABLED:
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.DISABLED,
            detail=f"connector status is {record.status.value}",
            capabilities=capability_ids,
        )

    if probe_ok is False:
        return ConnectorHealth(
            connector_id=record.id,
            state=HealthState.DEGRADED,
            detail="health probe failed",
            capabilities=capability_ids,
        )

    return ConnectorHealth(
        connector_id=record.id,
        state=HealthState.HEALTHY,
        detail="connector is configured and enabled",
        capabilities=capability_ids,
    )
