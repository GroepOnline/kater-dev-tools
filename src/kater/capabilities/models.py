from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class RiskClass(StrEnum):
    READ = "read"
    LOCAL_WRITE = "local_write"
    EXTERNAL_WRITE = "external_write"
    DEPLOY = "deploy"
    DESTRUCTIVE = "destructive"
    SECRET_ACCESS = "secret_access"  # noqa: S105 — risk class label, not a credential
    PRIVILEGED_INFRA = "privileged_infra"


class LifecycleState(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    CANARY = "canary"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


class CapabilityTransport(StrEnum):
    NATIVE = "native"
    STDIO_MCP = "stdio_mcp"
    REMOTE_MCP = "remote_mcp"
    HTTP = "http"
    SSE = "sse"


_RISK_RANK: dict[RiskClass, int] = {
    RiskClass.READ: 0,
    RiskClass.LOCAL_WRITE: 1,
    RiskClass.EXTERNAL_WRITE: 2,
    RiskClass.DEPLOY: 3,
    RiskClass.DESTRUCTIVE: 4,
    RiskClass.SECRET_ACCESS: 5,
    RiskClass.PRIVILEGED_INFRA: 6,
}

_LOW_APPROVAL_RISKS = frozenset({RiskClass.READ, RiskClass.LOCAL_WRITE})

_SEMVER_LIKE = re.compile(
    r"^v?\d+(?:\.\d+){0,3}"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def risk_rank(risk: RiskClass) -> int:
    """Inclusive ordinal for risk comparisons (higher = more privileged)."""
    try:
        return _RISK_RANK[risk]
    except KeyError as exc:
        raise ValueError(f"unknown risk class: {risk!r}") from exc


def approval_expected_for(risk: RiskClass) -> bool:
    """True when risk is beyond READ / LOCAL_WRITE."""
    return risk not in _LOW_APPROVAL_RISKS


def _require_nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _require_enum(name: str, value: object, enum_type: type[StrEnum]) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{name} must be a {enum_type.__name__}")


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    capability_id: str
    package_id: str
    publisher_id: str
    version: str
    digest: str
    transport: CapabilityTransport
    description: str
    input_schema: dict
    output_schema: dict
    required_scopes: frozenset[str]
    risk_class: RiskClass
    data_classification: str
    profiles: frozenset[str]
    healthcheck_capability_id: str | None = None
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    rollback_version: str | None = None
    network_targets: tuple[str, ...] = ()
    tags: frozenset[str] = field(default_factory=frozenset)
    method: str | None = None
    path: str | None = None
    timeout_seconds: float | None = None
    mutation: bool = False
    idempotency_required: bool = False

    def __post_init__(self) -> None:
        _require_nonempty("capability_id", self.capability_id)
        if "__" in self.capability_id:
            raise ValueError("capability_id cannot contain '__'")
        _require_nonempty("package_id", self.package_id)
        _require_nonempty("publisher_id", self.publisher_id)
        _require_nonempty("version", self.version)
        if not _SEMVER_LIKE.match(self.version):
            raise ValueError(f"version must be semver-like, got {self.version!r}")
        if self.digest and not self.digest.startswith("sha256:"):
            raise ValueError("digest must be empty or start with 'sha256:'")
        _require_enum("transport", self.transport, CapabilityTransport)
        _require_enum("risk_class", self.risk_class, RiskClass)
        _require_enum("lifecycle_state", self.lifecycle_state, LifecycleState)
        _require_nonempty("data_classification", self.data_classification)
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.input_schema, dict):
            raise ValueError("input_schema must be a dict")
        if not isinstance(self.output_schema, dict):
            raise ValueError("output_schema must be a dict")
        if not isinstance(self.required_scopes, frozenset):
            raise ValueError("required_scopes must be a frozenset")
        if not isinstance(self.profiles, frozenset):
            raise ValueError("profiles must be a frozenset")
        if not isinstance(self.tags, frozenset):
            raise ValueError("tags must be a frozenset")
        if not isinstance(self.network_targets, tuple):
            raise ValueError("network_targets must be a tuple")
        if self.healthcheck_capability_id is not None:
            _require_nonempty("healthcheck_capability_id", self.healthcheck_capability_id)
            if "__" in self.healthcheck_capability_id:
                raise ValueError("healthcheck_capability_id cannot contain '__'")
        if self.rollback_version is not None and not self.rollback_version.strip():
            raise ValueError("rollback_version must be non-empty when set")
        if self.method is not None and not self.method.strip():
            raise ValueError("method must be non-empty when set")
        if self.path is not None and not self.path.startswith("/"):
            raise ValueError("path must start with '/'")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(self.mutation, bool) or not isinstance(self.idempotency_required, bool):
            raise ValueError("mutation and idempotency_required must be bools")


@dataclass(frozen=True, slots=True)
class DiscoveryContext:
    principal_id: str = "anonymous"
    profile_ids: frozenset[str] = field(default_factory=lambda: frozenset({"core"}))
    task_intent: str = ""
    repository: str | None = None
    environment: str | None = None
    required_scopes: frozenset[str] = field(default_factory=frozenset)
    max_risk: RiskClass = RiskClass.EXTERNAL_WRITE
    include_unhealthy: bool = False
    tags_any: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _require_nonempty("principal_id", self.principal_id)
        if not isinstance(self.profile_ids, frozenset):
            raise ValueError("profile_ids must be a frozenset")
        if not isinstance(self.required_scopes, frozenset):
            raise ValueError("required_scopes must be a frozenset")
        if not isinstance(self.tags_any, frozenset):
            raise ValueError("tags_any must be a frozenset")
        _require_enum("max_risk", self.max_risk, RiskClass)
        if not isinstance(self.task_intent, str):
            raise ValueError("task_intent must be a string")
        if not isinstance(self.include_unhealthy, bool):
            raise ValueError("include_unhealthy must be a bool")


@dataclass(frozen=True, slots=True)
class DiscoveredCapability:
    capability_id: str
    version: str
    digest: str
    description: str
    risk_class: RiskClass
    lifecycle_state: LifecycleState
    required_scopes: frozenset[str]
    input_schema: dict
    approval_expected: bool
    health_ok: bool

    def __post_init__(self) -> None:
        _require_nonempty("capability_id", self.capability_id)
        if "__" in self.capability_id:
            raise ValueError("capability_id cannot contain '__'")
        _require_nonempty("version", self.version)
        _require_enum("risk_class", self.risk_class, RiskClass)
        _require_enum("lifecycle_state", self.lifecycle_state, LifecycleState)
        if not isinstance(self.required_scopes, frozenset):
            raise ValueError("required_scopes must be a frozenset")
        if not isinstance(self.input_schema, dict):
            raise ValueError("input_schema must be a dict")
        if not isinstance(self.approval_expected, bool):
            raise ValueError("approval_expected must be a bool")
        if not isinstance(self.health_ok, bool):
            raise ValueError("health_ok must be a bool")
