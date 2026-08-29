"""Connector control-plane models.

This is the catalog of *what Kater can route to*. It is not:

- ``kater.registry.NativeTool`` (the 17 native MCP tools)
- ``kater.capabilities.CapabilityManifest`` (capability fabric manifests)
- ``kater.control_plane`` route candidates (logical capability pools)
- ``kater.capabilities.computer.ComputerConnector`` (Computer/Fleet guest)

Auth values never live on these models. Store ``auth_binding_ref`` only.
Health is computed at read time and is not a persisted truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

_CONNECTOR_ID = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "credential",
        "private_key",
        "access_token",
        "refresh_token",
    }
)


class ConnectorType(StrEnum):
    API = "api"
    MCP = "mcp"
    BRIDGE = "bridge"
    INTERNAL = "internal"


class ConnectorStatus(StrEnum):
    REGISTERED = "registered"
    VALIDATED = "validated"
    DISABLED = "disabled"
    ENABLED = "enabled"


class PermissionLevel(StrEnum):
    DISABLED = "disabled"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"
    AUTH_MISSING = "auth_missing"
    POLICY_BLOCKED = "policy_blocked"


class AuthBindingKind(StrEnum):
    ENV = "env"
    SETTINGS = "settings"
    CHEFVAULT = "chefvault"
    NONE = "none"


_PERMISSION_RANK = {
    PermissionLevel.DISABLED: 0,
    PermissionLevel.READ: 1,
    PermissionLevel.WRITE: 2,
    PermissionLevel.ADMIN: 3,
}

_WRITE_HINTS = ("write", "create", "update", "delete", "merge", "admin", "mutate")


def permission_rank(level: PermissionLevel) -> int:
    return _PERMISSION_RANK[level]


def permission_allows(granted: PermissionLevel, required: PermissionLevel) -> bool:
    if granted is PermissionLevel.DISABLED:
        return False
    return permission_rank(granted) >= permission_rank(required)


def capability_required_permission(capability_id: str) -> PermissionLevel:
    """Map a capability id to the minimum profile permission needed."""
    lowered = capability_id.lower()
    if lowered.endswith(".admin") or ".admin." in lowered:
        return PermissionLevel.ADMIN
    if any(hint in lowered.split(".") for hint in _WRITE_HINTS) or any(
        lowered.endswith(f".{hint}") for hint in _WRITE_HINTS
    ):
        return PermissionLevel.WRITE
    return PermissionLevel.READ


def _require_id(name: str, value: str, pattern: re.Pattern[str]) -> str:
    text = (value or "").strip()
    if not pattern.match(text):
        raise ValueError(f"{name} must match {pattern.pattern}, got {value!r}")
    return text


def looks_like_secret_key(key: str) -> bool:
    lowered = key.strip().lower().replace("-", "_")
    if lowered in _SECRET_KEYS:
        return True
    return any(token in lowered.split("_") for token in _SECRET_KEYS)

_SAFE_SECRET_TEMPLATE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]*\s+)?\$\{[A-Z_][A-Z0-9_]*\}$"
)


def _metadata_secret_paths(value: Any, path: str = "metadata") -> list[str]:
    """Return nested metadata paths whose keys can carry credentials."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if looks_like_secret_key(str(key)):
                found.append(child_path)
            found.extend(_metadata_secret_paths(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_metadata_secret_paths(child, f"{path}[{index}]"))
    return found


@dataclass(frozen=True, slots=True)
class AuthBindingRef:
    """Reference to credentials owned by env / settings / ChefVault.

    ``ref`` is a name (env var, settings key, vault item) never a secret value.
    """

    kind: AuthBindingKind
    ref: str = ""
    credential_provider: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AuthBindingKind):
            raise ValueError("kind must be an AuthBindingKind")
        if self.kind is AuthBindingKind.NONE:
            if (self.ref or "").strip():
                raise ValueError("auth binding kind none must not carry a ref")
            return
        if not (self.ref or "").strip():
            raise ValueError("auth binding ref is required unless kind is none")
        if looks_like_secret_key(self.ref) and self.ref.upper() != self.ref and "=" in self.ref:
            raise ValueError("auth binding ref must not contain credential material")

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "ref": self.ref,
            "credential_provider": self.credential_provider,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> AuthBindingRef:
        if not data:
            return cls(kind=AuthBindingKind.NONE)
        kind_raw = str(data.get("kind") or AuthBindingKind.NONE.value)
        try:
            kind = AuthBindingKind(kind_raw)
        except ValueError as exc:
            raise ValueError(f"unknown auth binding kind: {kind_raw!r}") from exc
        return cls(
            kind=kind,
            ref=str(data.get("ref") or ""),
            credential_provider=str(data.get("credential_provider") or ""),
        )

    @classmethod
    def from_env_names(cls, names: list[str]) -> AuthBindingRef:
        cleaned = [name.strip() for name in names if name and name.strip()]
        if not cleaned:
            return cls(kind=AuthBindingKind.NONE)
        return cls(kind=AuthBindingKind.ENV, ref=",".join(cleaned), credential_provider="env")


@dataclass(frozen=True, slots=True)
class ConnectorTransport:
    """How to reach the connector. No headers with live secrets."""

    kind: str
    endpoint: str = ""
    command: str | None = None
    args: tuple[str, ...] = ()
    headers_template: dict[str, str] = field(default_factory=dict)
    env_template: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        kind = (self.kind or "").strip().lower()
        if kind not in {"http", "stdio", "sse", "native", "bridge"}:
            raise ValueError(f"unsupported transport kind: {self.kind!r}")
        object.__setattr__(self, "kind", kind)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if kind in {"http", "sse", "bridge"} and not (self.endpoint or "").strip():
            raise ValueError(f"{kind} transport requires an endpoint")
        if kind == "stdio" and not (self.command or "").strip():
            raise ValueError("stdio transport requires a command")
        for key, value in self.headers_template.items():
            if value and not _SAFE_SECRET_TEMPLATE.fullmatch(value.strip()):
                raise ValueError(
                    f"header template {key!r} must be a complete ${{ENV}} placeholder "
                    "(optionally with an auth scheme)"
                )
        for key, value in self.env_template.items():
            if (
                looks_like_secret_key(key)
                and value
                and not _SAFE_SECRET_TEMPLATE.fullmatch(value.strip())
            ):
                raise ValueError(
                    f"template {key!r} must be a complete ${{ENV}} placeholder "
                    "(optionally with an auth scheme)"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "endpoint": self.endpoint,
            "command": self.command,
            "args": list(self.args),
            "headers_template": dict(self.headers_template),
            "env_template": dict(self.env_template),
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ConnectorTransport:
        args = data.get("args") or ()
        return cls(
            kind=str(data.get("kind") or ""),
            endpoint=str(data.get("endpoint") or ""),
            command=(str(data["command"]) if data.get("command") else None),
            args=tuple(str(item) for item in args),
            headers_template={
                str(key): str(value)
                for key, value in dict(data.get("headers_template") or {}).items()
            },
            env_template={
                str(key): str(value)
                for key, value in dict(data.get("env_template") or {}).items()
            },
            timeout_seconds=float(data.get("timeout_seconds") or 15.0),
        )


@dataclass(frozen=True, slots=True)
class ConnectorCapability:
    """Machine-readable capability advertised by a connector."""

    id: str
    description: str = ""
    mutation: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    discovered: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id("capability id", self.id, _CAPABILITY_ID))
        if self.mutation is False:
            object.__setattr__(
                self,
                "mutation",
                capability_required_permission(self.id) is not PermissionLevel.READ,
            )

    def required_permission(self) -> PermissionLevel:
        if self.mutation:
            return max(
                capability_required_permission(self.id),
                PermissionLevel.WRITE,
                key=permission_rank,
            )
        return capability_required_permission(self.id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "mutation": self.mutation,
            "input_schema": dict(self.input_schema),
            "discovered": self.discovered,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ConnectorCapability:
        return cls(
            id=str(data.get("id") or ""),
            description=str(data.get("description") or ""),
            mutation=bool(data.get("mutation", False)),
            input_schema=dict(data.get("input_schema") or {}),
            discovered=bool(data.get("discovered", False)),
        )


@dataclass(frozen=True, slots=True)
class ConnectorRecord:
    """Persisted connector catalog entry. Health is not stored here."""

    id: str
    display_name: str
    type: ConnectorType
    version: str
    transport: ConnectorTransport
    capabilities: tuple[ConnectorCapability, ...] = ()
    auth_binding: AuthBindingRef = field(
        default_factory=lambda: AuthBindingRef(AuthBindingKind.NONE)
    )
    profiles: frozenset[str] = field(default_factory=frozenset)
    permissions: dict[str, PermissionLevel] = field(default_factory=dict)
    status: ConnectorStatus = ConnectorStatus.DISABLED
    metadata: dict[str, Any] = field(default_factory=dict)
    origin: str = "dynamic"

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_id("connector id", self.id, _CONNECTOR_ID))
        if not (self.display_name or "").strip():
            raise ValueError("display_name is required")
        if not isinstance(self.type, ConnectorType):
            raise ValueError("type must be a ConnectorType")
        if not (self.version or "").strip():
            raise ValueError("version is required")
        if not isinstance(self.transport, ConnectorTransport):
            raise ValueError("transport is required")
        if not isinstance(self.auth_binding, AuthBindingRef):
            raise ValueError("auth_binding is required")
        if self.status not in ConnectorStatus:
            raise ValueError(f"unknown status: {self.status!r}")
        forbidden = _metadata_secret_paths(self.metadata)
        if forbidden:
            raise ValueError(f"metadata must not contain secret keys: {sorted(forbidden)}")
        caps = tuple(self.capabilities)
        ids = [cap.id for cap in caps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate capability ids on connector")
        object.__setattr__(self, "capabilities", caps)
        object.__setattr__(self, "profiles", frozenset(self.profiles))
        object.__setattr__(self, "permissions", dict(self.permissions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def permission_for(self, profile: str) -> PermissionLevel:
        if profile in self.permissions:
            return self.permissions[profile]
        if self.status is ConnectorStatus.DISABLED:
            return PermissionLevel.DISABLED
        if self.profiles and profile not in self.profiles:
            return PermissionLevel.DISABLED
        if self.status is ConnectorStatus.ENABLED:
            return PermissionLevel.READ
        return PermissionLevel.DISABLED

    def capability(self, capability_id: str) -> ConnectorCapability | None:
        for item in self.capabilities:
            if item.id == capability_id:
                return item
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "type": self.type.value,
            "version": self.version,
            "transport": self.transport.as_dict(),
            "capabilities": [item.as_dict() for item in self.capabilities],
            "auth_binding": self.auth_binding.as_dict(),
            "profiles": sorted(self.profiles),
            "permissions": {key: value.value for key, value in sorted(self.permissions.items())},
            "status": self.status.value,
            "metadata": dict(self.metadata),
            "origin": self.origin,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ConnectorRecord:
        try:
            connector_type = ConnectorType(str(data.get("type") or ""))
        except ValueError as exc:
            raise ValueError(f"unknown connector type: {data.get('type')!r}") from exc
        try:
            status = ConnectorStatus(str(data.get("status") or ConnectorStatus.DISABLED.value))
        except ValueError as exc:
            raise ValueError(f"unknown connector status: {data.get('status')!r}") from exc
        permissions: dict[str, PermissionLevel] = {}
        for profile, level in dict(data.get("permissions") or {}).items():
            permissions[str(profile)] = PermissionLevel(str(level))
        capabilities = tuple(
            ConnectorCapability.from_mapping(item)
            for item in list(data.get("capabilities") or [])
        )
        return cls(
            id=str(data.get("id") or ""),
            display_name=str(data.get("display_name") or data.get("id") or ""),
            type=connector_type,
            version=str(data.get("version") or "1.0.0"),
            transport=ConnectorTransport.from_mapping(dict(data.get("transport") or {})),
            capabilities=capabilities,
            auth_binding=AuthBindingRef.from_mapping(dict(data.get("auth_binding") or {})),
            profiles=frozenset(str(item) for item in list(data.get("profiles") or [])),
            permissions=permissions,
            status=status,
            metadata=dict(data.get("metadata") or {}),
            origin=str(data.get("origin") or "dynamic"),
        )


@dataclass(frozen=True, slots=True)
class ConnectorHealth:
    connector_id: str
    state: HealthState
    detail: str
    capabilities: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "state": self.state.value,
            "detail": self.detail,
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True, slots=True)
class ConnectorView:
    """Agent-facing inventory row: catalog + live health, never secrets."""

    record: ConnectorRecord
    health: ConnectorHealth
    configured: bool
    missing_auth: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = self.record.as_dict()
        payload["health"] = self.health.as_dict()
        payload["configured"] = self.configured
        payload["missing_auth"] = list(self.missing_auth)
        return payload
