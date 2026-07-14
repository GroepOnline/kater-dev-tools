from datetime import UTC, datetime, timedelta

import pytest

from kater.control_plane import (
    AGENT_STATE_MACHINE,
    AccountState,
    AgentState,
    InvalidTransition,
    NoRouteAvailable,
    ProviderAccount,
    QuotaAwareRouter,
    QuotaWindow,
    RemoteContext,
    RoutingRequest,
)

NOW = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)


def account(
    account_id: str,
    *,
    remaining: int,
    backend: str | None = None,
    limit: int = 100,
    priority: int = 100,
    cost: float = 0.0,
    latency: float = 100.0,
    state: AccountState = AccountState.ACTIVE,
    cooldown_until: datetime | None = None,
    scopes: frozenset[str] = frozenset({"models.invoke"}),
    resets_at: datetime | None = None,
) -> ProviderAccount:
    return ProviderAccount(
        account_id=account_id,
        provider="provider",
        backend=backend or account_id,
        tool_name="invoke",
        scopes=scopes,
        priority=priority,
        max_concurrent=2,
        cost_per_million_units=cost,
        latency_ms=latency,
        quota_windows=(
            QuotaWindow(
                "monthly",
                limit=limit,
                used=limit - remaining,
                resets_at=resets_at,
            ),
        ),
        state=state,
        cooldown_until=cooldown_until,
    )


def test_router_prefers_quota_headroom_before_minor_cost_difference() -> None:
    decision = QuotaAwareRouter().select(
        [
            account("nearly-empty", remaining=5, cost=0.0, priority=1),
            account("healthy-pool", remaining=90, cost=1.0, priority=10),
        ],
        RoutingRequest("llm.invoke", "ctx-1", frozenset({"models.invoke"}), 2),
        now=NOW,
    )
    assert decision.account_id == "healthy-pool"
    assert decision.backend == "healthy-pool"
    assert decision.tool_name == "invoke"


def test_router_excludes_scope_capacity_quota_and_cooldown_failures() -> None:
    decisions = QuotaAwareRouter().rank(
        [
            account("no-scope", remaining=100, scopes=frozenset()),
            account("exhausted", remaining=0),
            account(
                "cooldown",
                remaining=100,
                state=AccountState.COOLDOWN,
                cooldown_until=NOW + timedelta(minutes=5),
            ),
            account("eligible", remaining=20),
        ],
        RoutingRequest("llm.invoke", "ctx-1", frozenset({"models.invoke"}), 1),
        now=NOW,
    )
    assert [decision.account_id for decision in decisions] == ["eligible"]


def test_expired_cooldown_and_exhausted_reset_window_become_eligible() -> None:
    cooldown = account(
        "cooldown-reset",
        remaining=10,
        state=AccountState.COOLDOWN,
        cooldown_until=NOW - timedelta(seconds=1),
    )
    exhausted = account(
        "quota-reset",
        remaining=0,
        state=AccountState.EXHAUSTED,
        resets_at=NOW - timedelta(seconds=1),
    )
    decisions = QuotaAwareRouter().rank(
        [cooldown, exhausted],
        RoutingRequest("llm.invoke", "ctx-1", frozenset({"models.invoke"})),
        now=NOW,
    )
    assert {decision.account_id for decision in decisions} == {
        "cooldown-reset",
        "quota-reset",
    }


def test_no_route_raises_structured_error() -> None:
    with pytest.raises(NoRouteAvailable, match=r"capability='llm\.invoke'"):
        QuotaAwareRouter().select(
            [account("disabled", remaining=100, state=AccountState.DISABLED)],
            RoutingRequest("llm.invoke", "ctx-1"),
            now=NOW,
        )


def test_remote_context_enforces_expiry_and_scopes() -> None:
    context = RemoteContext(
        context_id="ctx-1",
        principal_id="agent-1",
        scopes=frozenset({"models.invoke", "github.read"}),
        expires_at=NOW + timedelta(minutes=10),
    )
    assert context.allows(frozenset({"models.invoke"}), NOW)
    assert not context.allows(frozenset({"github.write"}), NOW)
    assert not context.allows(
        frozenset({"models.invoke"}),
        NOW + timedelta(minutes=11),
    )


def test_agent_state_machine_rejects_invalid_terminal_transitions() -> None:
    transition = AGENT_STATE_MACHINE.transition(AgentState.IDLE, AgentState.WORKING)
    assert transition.current == AgentState.WORKING
    with pytest.raises(InvalidTransition, match="idle -> completed"):
        AGENT_STATE_MACHINE.transition(AgentState.IDLE, AgentState.COMPLETED)
    with pytest.raises(InvalidTransition, match="completed -> working"):
        AGENT_STATE_MACHINE.transition(AgentState.COMPLETED, AgentState.WORKING)


def test_logical_capability_rejects_prefixed_tool_separator() -> None:
    from kater.control_plane import RouteBinding

    with pytest.raises(ValueError, match="cannot contain"):
        RouteBinding(
            capability="github__search",
            account=account("github", remaining=100),
        )