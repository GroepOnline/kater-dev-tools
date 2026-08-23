"""Fail-closed errors for the connector control plane."""

from __future__ import annotations


class ConnectorError(Exception):
    """Base class for connector control-plane failures."""

    def __init__(self, code: str, message: str, *, connector_id: str | None = None) -> None:
        self.code = code
        self.connector_id = connector_id
        super().__init__(message)

    def as_dict(self) -> dict[str, str | None]:
        return {
            "error": self.code,
            "message": str(self),
            "connector_id": self.connector_id,
        }


class ConnectorExistsError(ConnectorError):
    def __init__(self, connector_id: str) -> None:
        super().__init__(
            "duplicate_connector",
            f"connector {connector_id!r} is already registered",
            connector_id=connector_id,
        )


class ConnectorNotFoundError(ConnectorError):
    def __init__(self, connector_id: str) -> None:
        super().__init__(
            "connector_not_found",
            f"connector {connector_id!r} is not registered",
            connector_id=connector_id,
        )


class ConnectorValidationError(ConnectorError):
    def __init__(self, message: str, *, connector_id: str | None = None) -> None:
        super().__init__("invalid_connector", message, connector_id=connector_id)


class ConnectorAuthError(ConnectorError):
    def __init__(self, message: str, *, connector_id: str | None = None) -> None:
        super().__init__("auth_missing", message, connector_id=connector_id)


class ConnectorPolicyError(ConnectorError):
    def __init__(
        self,
        message: str,
        *,
        connector_id: str | None = None,
        code: str = "policy_blocked",
    ) -> None:
        super().__init__(code, message, connector_id=connector_id)


class ConnectorCapabilityError(ConnectorError):
    def __init__(self, message: str, *, connector_id: str | None = None) -> None:
        super().__init__("capability_missing", message, connector_id=connector_id)


class ConnectorUnavailableError(ConnectorError):
    def __init__(
        self,
        message: str,
        *,
        connector_id: str | None = None,
        code: str = "unavailable",
    ) -> None:
        super().__init__(code, message, connector_id=connector_id)
