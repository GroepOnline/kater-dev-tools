from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Generic, TypeVar

from kater.control_plane.models import AgentState, ServiceState

StateT = TypeVar("StateT", bound=StrEnum)


class InvalidTransition(ValueError):
    """Raised when a lifecycle transition violates the canonical state graph."""


@dataclass(frozen=True, slots=True)
class Transition(Generic[StateT]):
    previous: StateT
    current: StateT
    occurred_at: datetime
    reason: str | None = None


class StateMachine(Generic[StateT]):
    def __init__(self, transitions: dict[StateT, frozenset[StateT]]) -> None:
        self._transitions = transitions

    def transition(
        self,
        previous: StateT,
        current: StateT,
        *,
        reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Transition[StateT]:
        if current == previous:
            return Transition(previous, current, occurred_at or datetime.now(UTC), reason)
        allowed = self._transitions.get(previous, frozenset())
        if current not in allowed:
            raise InvalidTransition(f"invalid transition: {previous.value} -> {current.value}")
        return Transition(previous, current, occurred_at or datetime.now(UTC), reason)


AGENT_STATE_MACHINE = StateMachine(
    {
        AgentState.IDLE: frozenset({AgentState.WORKING}),
        AgentState.WORKING: frozenset(
            {
                AgentState.WAITING,
                AgentState.BLOCKED,
                AgentState.FAILED,
                AgentState.REVIEW,
                AgentState.COMPLETED,
            }
        ),
        AgentState.WAITING: frozenset(
            {AgentState.WORKING, AgentState.BLOCKED, AgentState.FAILED}
        ),
        AgentState.BLOCKED: frozenset(
            {AgentState.WORKING, AgentState.FAILED, AgentState.REVIEW}
        ),
        AgentState.FAILED: frozenset({AgentState.WORKING, AgentState.REVIEW}),
        AgentState.REVIEW: frozenset(
            {AgentState.WORKING, AgentState.BLOCKED, AgentState.COMPLETED}
        ),
        AgentState.COMPLETED: frozenset(),
    }
)

SERVICE_STATE_MACHINE = StateMachine(
    {
        ServiceState.STOPPED: frozenset({ServiceState.STARTING}),
        ServiceState.STARTING: frozenset(
            {ServiceState.HEALTHY, ServiceState.DEGRADED, ServiceState.FAILED}
        ),
        ServiceState.HEALTHY: frozenset(
            {ServiceState.DEGRADED, ServiceState.FAILED, ServiceState.STOPPING}
        ),
        ServiceState.DEGRADED: frozenset(
            {ServiceState.HEALTHY, ServiceState.FAILED, ServiceState.STOPPING}
        ),
        ServiceState.FAILED: frozenset({ServiceState.STARTING, ServiceState.STOPPING}),
        ServiceState.STOPPING: frozenset({ServiceState.STOPPED, ServiceState.FAILED}),
    }
)