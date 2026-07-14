from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class AccountState(StrEnum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    EXHAUSTED = "exhausted"
    DISABLED = "disabled"


class AgentState(StrEnum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    FAILED = "failed"
    REVIEW = "review"
    COMPLETED = "completed"


class ServiceState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPING = "stopping"


class InterventionKind(StrEnum):
    APPROVAL = "approval"
    CAPACITY = "capacity"
    CONFLICT = "conflict"
    CREDENTIAL = "credential"
    RETRY = "retry"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class QuotaWindow:
    name: str
    limit: int
    used: int = 0
    resets_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("quota window name is required")
        if self.limit < 0:
            raise ValueError("quota limit must be non-negative")
        if self.used < 0:
            raise ValueError("quota usage must be non-negative")

    def effective_used(self, now: datetime) -> int:
        if self.resets_at is not None and now >= self.resets_at:
            return 0
        return self.used

    def remaining_at(self, now: datetime) -> int:
        return max(self.limit - self.effective_used(now), 0)

    def remaining_ratio_at(self, now: datetime) -> float:
        if self.limit == 0:
            return 0.0
        return self.remaining_at(now) / self.limit


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    """One routable account backed by one concrete MCP backend/tool pair.

    Secrets are intentionally absent. Credential resolution remains owned by the
    backend/credential broker; the routing layer only sees operational metadata.
    """

    account_id: str
    provider: str
    backend: str
    tool_name: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    priority: int = 100
    max_concurrent: int = 1
    in_flight: int = 0
    cost_per_million_units: float = 0.0
    latency_ms: float = 0.0
    quota_windows: tuple[QuotaWindow, ...] = ()
    state: AccountState = AccountState.ACTIVE
    cooldown_until: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in ("account_id", "provider", "backend", "tool_name"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be at least one")
        if self.in_flight < 0:
            raise ValueError("in_flight must be non-negative")
        if self.cost_per_million_units < 0:
            raise ValueError("cost must be non-negative")
        if self.latency_ms < 0:
            raise ValueError("latency must be non-negative")

    def effective_state(self, now: datetime) -> AccountState:
        if (
            self.state == AccountState.COOLDOWN
            and self.cooldown_until is not None
            and now >= self.cooldown_until
        ):
            return AccountState.ACTIVE
        if (
            self.state == AccountState.EXHAUSTED
            and self.quota_windows
            and all(
                window.resets_at is not None and now >= window.resets_at
                for window in self.quota_windows
            )
        ):
            return AccountState.ACTIVE
        return self.state

    @property
    def concurrency_available(self) -> int:
        return max(self.max_concurrent - self.in_flight, 0)


@dataclass(frozen=True, slots=True)
class RouteBinding:
    capability: str
    account: ProviderAccount

    def __post_init__(self) -> None:
        if not self.capability:
            raise ValueError("capability is required")
        if "__" in self.capability:
            raise ValueError("logical capability cannot contain '__'")


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    capability: str
    context_id: str
    required_scopes: frozenset[str] = field(default_factory=frozenset)
    estimated_units: int = 1

    def __post_init__(self) -> None:
        if not self.capability:
            raise ValueError("capability is required")
        if not self.context_id:
            raise ValueError("context_id is required")
        if self.estimated_units < 1:
            raise ValueError("estimated_units must be at least one")


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    capability: str
    account_id: str
    provider: str
    backend: str
    tool_name: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RemoteContext:
    context_id: str
    principal_id: str
    scopes: frozenset[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    repository: str | None = None
    environment: str | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return self.expires_at is None or current < self.expires_at

    def allows(self, required_scopes: frozenset[str], now: datetime | None = None) -> bool:
        return self.is_active(now) and required_scopes.issubset(self.scopes)


@dataclass(frozen=True, slots=True)
class Intervention:
    intervention_id: str
    kind: InterventionKind
    summary: str
    context_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    blocking: bool = True
    evidence_refs: tuple[str, ...] = ()