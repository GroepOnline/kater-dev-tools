from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from kater.control_plane.models import (
    AccountState,
    ProviderAccount,
    RoutingDecision,
    RoutingRequest,
)


class NoRouteAvailable(RuntimeError):
    """Raised when no provider account satisfies policy and capacity constraints."""


@dataclass(frozen=True, slots=True)
class RoutingWeights:
    quota_headroom: float = 55.0
    priority: float = 25.0
    concurrency: float = 10.0
    cost: float = 6.0
    latency: float = 4.0


class QuotaAwareRouter:
    """Deterministically rank account-backed MCP routes without seeing secrets."""

    def __init__(self, weights: RoutingWeights | None = None) -> None:
        self._weights = weights or RoutingWeights()

    def rank(
        self,
        accounts: list[ProviderAccount],
        request: RoutingRequest,
        *,
        now: datetime | None = None,
    ) -> list[RoutingDecision]:
        current = now or datetime.now(UTC)
        decisions: list[RoutingDecision] = []
        for account in accounts:
            decision = self._evaluate(account, request, current)
            if decision is not None:
                decisions.append(decision)
        return sorted(decisions, key=lambda item: (-item.score, item.account_id))

    def select(
        self,
        accounts: list[ProviderAccount],
        request: RoutingRequest,
        *,
        now: datetime | None = None,
    ) -> RoutingDecision:
        ranked = self.rank(accounts, request, now=now)
        if not ranked:
            raise NoRouteAvailable(
                f"no account available for capability={request.capability!r} "
                f"context={request.context_id!r}"
            )
        return ranked[0]

    def _evaluate(
        self,
        account: ProviderAccount,
        request: RoutingRequest,
        now: datetime,
    ) -> RoutingDecision | None:
        if account.effective_state(now) != AccountState.ACTIVE:
            return None
        if account.concurrency_available < 1:
            return None
        if not request.required_scopes.issubset(account.scopes):
            return None
        if any(
            window.remaining_at(now) < request.estimated_units for window in account.quota_windows
        ):
            return None

        quota_ratio = min(
            (window.remaining_ratio_at(now) for window in account.quota_windows),
            default=1.0,
        )
        priority_score = 1.0 / (1.0 + account.priority)
        concurrency_score = account.concurrency_available / account.max_concurrent
        cost_score = 1.0 / (1.0 + account.cost_per_million_units)
        latency_score = 1.0 / (1.0 + account.latency_ms / 1000.0)

        score = (
            quota_ratio * self._weights.quota_headroom
            + priority_score * self._weights.priority
            + concurrency_score * self._weights.concurrency
            + cost_score * self._weights.cost
            + latency_score * self._weights.latency
        )
        reasons = (
            f"quota_headroom={quota_ratio:.3f}",
            f"priority={account.priority}",
            f"concurrency={account.concurrency_available}/{account.max_concurrent}",
            f"cost_per_million={account.cost_per_million_units:.6f}",
            f"latency_ms={account.latency_ms:.1f}",
        )
        return RoutingDecision(
            capability=request.capability,
            account_id=account.account_id,
            provider=account.provider,
            backend=account.backend,
            tool_name=account.tool_name,
            score=round(score, 6),
            reasons=reasons,
        )
