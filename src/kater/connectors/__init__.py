"""Persistent connector catalog for the Kater control plane.

The bounded native MCP tools stay the external Cursor surface. Connectors live
behind ``kater_adapters`` / chains and are never one-native-tool-per-vendor.
"""

from kater.connectors.errors import (
    ConnectorAuthError,
    ConnectorCapabilityError,
    ConnectorError,
    ConnectorExistsError,
    ConnectorNotFoundError,
    ConnectorPolicyError,
    ConnectorUnavailableError,
    ConnectorValidationError,
)
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorHealth,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    ConnectorView,
    HealthState,
    PermissionLevel,
    capability_required_permission,
    looks_like_secret_key,
    permission_allows,
    permission_rank,
)

__all__ = [
    "AuthBindingKind",
    "AuthBindingRef",
    "ConnectorAuthError",
    "ConnectorCapability",
    "ConnectorCapabilityError",
    "ConnectorError",
    "ConnectorExistsError",
    "ConnectorHealth",
    "ConnectorNotFoundError",
    "ConnectorPolicyError",
    "ConnectorRecord",
    "ConnectorStatus",
    "ConnectorTransport",
    "ConnectorType",
    "ConnectorUnavailableError",
    "ConnectorValidationError",
    "ConnectorView",
    "HealthState",
    "PermissionLevel",
    "capability_required_permission",
    "looks_like_secret_key",
    "permission_allows",
    "permission_rank",
]
