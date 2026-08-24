"""Pre-execution validation for chain steps against the connector catalog."""

from __future__ import annotations

from typing import Any

from kater.chains import ChainStep
from kater.connectors import registry
from kater.connectors.auth import assert_auth
from kater.connectors.errors import (
    ConnectorCapabilityError,
    ConnectorNotFoundError,
    ConnectorUnavailableError,
)
from kater.connectors.health import evaluate_health
from kater.connectors.models import HealthState
from kater.connectors.policy import assert_profile_access
from kater.connectors.store import get_connector

_LEGACY_ALIASES: dict[str, tuple[str, str]] = {
    "github_pr_status": ("github", "github.pull_requests.read"),
    "linear_issue_status": ("linear", "linear.issues.read"),
    "sentry_issue_search": ("sentry", "sentry.issues.read"),
}

_HEALTHY_STATES = frozenset(
    {
        HealthState.HEALTHY,
        HealthState.DEGRADED,
    }
)


def chain_step_refs(step: ChainStep | str) -> tuple[str, str] | None:
    tool = step.tool if isinstance(step, ChainStep) else step
    if tool in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[tool]
    if "." not in tool:
        return None
    connector_id = tool.split(".", 1)[0]
    return connector_id, tool


def validate_chain_steps(steps: list[ChainStep], *, profile: str) -> None:
    """Fail closed for steps that map to the connector catalog.

    Unmapped legacy recipe names (``firecrawl_search``, ``kater_summary``)
    stay recipe-only and are not gated here.
    """
    for step in steps:
        ref = chain_step_refs(step)
        if ref is None:
            continue
        connector_id, capability_id = ref
        record = get_connector(connector_id)
        if record is None:
            raise ConnectorNotFoundError(connector_id)
        health = evaluate_health(record)
        if health.state not in _HEALTHY_STATES:
            raise ConnectorUnavailableError(
                f"connector {connector_id!r} is {health.state.value}: {health.detail}",
                connector_id=connector_id,
            )
        capability = record.capability(capability_id)
        if capability is None:
            raise ConnectorCapabilityError(
                f"capability {capability_id!r} not found on connector {connector_id!r}",
                connector_id=connector_id,
            )
        assert_auth(record)
        effective = registry._effective_capability(record, capability_id, {})
        mutation = effective.mutation if effective else capability.mutation
        assert_profile_access(record, profile, capability_id, mutation=mutation)


def assert_chain_runnable(steps: list[ChainStep], *, profile: str) -> None:
    """Seed builtins, then fail closed before a chain recipe is returned."""
    from kater.connectors.seed import seed_builtin_connectors

    seed_builtin_connectors()
    validate_chain_steps(steps, profile=profile)


def invoke_chain_capability(
    connector_id: str,
    capability_id: str,
    arguments: dict[str, Any],
    *,
    profile: str,
) -> dict[str, Any]:
    ref = chain_step_refs(capability_id)
    if ref is None or ref[0] != connector_id:
        raise ConnectorCapabilityError(
            f"capability {capability_id!r} does not belong to connector {connector_id!r}",
            connector_id=connector_id,
        )
    validate_chain_steps(
        [ChainStep(tool=capability_id, reason="chain invoke")],
        profile=profile,
    )
    return registry.invoke(connector_id, capability_id, arguments, profile=profile)
