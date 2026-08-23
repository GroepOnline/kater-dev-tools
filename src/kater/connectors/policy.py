"""Server-side connector permission enforcement."""

from __future__ import annotations

from kater.connectors.errors import ConnectorPolicyError
from kater.connectors.models import (
    ConnectorRecord,
    ConnectorStatus,
    PermissionLevel,
    capability_required_permission,
    permission_allows,
    permission_rank,
)
from kater.connectors.store import set_profile_permission


def required_permission(
    capability_id: str,
    mutation: bool | None = None,
) -> PermissionLevel:
    """Wrap models.capability_required_permission with optional mutation hint."""
    base = capability_required_permission(capability_id)
    if base is PermissionLevel.ADMIN:
        return PermissionLevel.ADMIN
    if mutation is True:
        return max(base, PermissionLevel.WRITE, key=permission_rank)
    if mutation is False:
        return PermissionLevel.READ
    return base


def assert_profile_access(
    record: ConnectorRecord,
    profile: str,
    capability_id: str,
    *,
    mutation: bool = False,
) -> PermissionLevel:
    """Fail closed when profile access is insufficient for the capability."""
    if record.status is ConnectorStatus.DISABLED:
        raise ConnectorPolicyError(
            f"connector {record.id!r} is disabled",
            connector_id=record.id,
            code="policy_blocked",
        )

    granted = record.permission_for(profile)
    if granted is PermissionLevel.DISABLED:
        raise ConnectorPolicyError(
            f"profile {profile!r} has no access to connector {record.id!r}",
            connector_id=record.id,
            code="policy_blocked",
        )

    if record.profiles and profile not in record.profiles:
        raise ConnectorPolicyError(
            f"profile {profile!r} is not bound to connector {record.id!r}",
            connector_id=record.id,
            code="policy_blocked",
        )

    needed = required_permission(capability_id, mutation=mutation)
    if not permission_allows(granted, needed):
        raise ConnectorPolicyError(
            f"profile {profile!r} needs {needed.value} for {capability_id!r}, has {granted.value}",
            connector_id=record.id,
            code="policy_blocked",
        )
    return granted


def bind_profile(connector_id: str, profile: str, level: PermissionLevel):
    """Persist a profile permission binding for one connector."""
    return set_profile_permission(connector_id, profile, level)
