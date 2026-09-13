"""Uniform connector capability search and execution surface.

Canonical call:

    execute(connection, action, input, identity, policy_context)

The positional ``execute(capability_id, arguments, profile=...)`` form remains
as a compatibility wrapper. GitHub PR tools and other native toolkit actions
share this path.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from kater.capabilities.audit import record_capability_audit
from kater.connections import (
    default_connection_id,
    get_connection_view,
    hidden_integration_ids,
    parse_connection_id,
    resolve_integration_id,
)
from kater.connectors import registry as connector_registry
from kater.connectors.auth import redact_text
from kater.connectors.errors import (
    ConnectorAuthError,
    ConnectorCapabilityError,
    ConnectorError,
    ConnectorNotFoundError,
    ConnectorPolicyError,
    ConnectorUnavailableError,
)
from kater.connectors.health import evaluate_health
from kater.connectors.models import ConnectorCapability, HealthState, permission_allows
from kater.connectors.policy import assert_profile_access
from kater.connectors.store import get_connector, list_connectors
from kater.execution import (
    ActorIdentity,
    ExecutionError,
    ExecutionResult,
    PolicyContext,
    action_is_dangerous,
    input_fingerprint,
    is_retryable,
    new_ids,
    release_idempotency,
    reserve_idempotency,
    run_with_timeout,
    store_idempotency,
    validate_action_input,
)
from kater.toolkits import invoke_native_action, native_action_owner
from kater.toolkits.github import GITHUB_PR_ACTIONS

_WORD = re.compile(r"[a-z0-9_.:-]+", re.IGNORECASE)
_AVAILABLE_HEALTH = frozenset({HealthState.HEALTHY, HealthState.DEGRADED})
_log = logging.getLogger("kater.executor")


def _assert_served_profile(profile: str) -> None:
    served_raw = os.environ.get("KATER_PROFILE", "").strip()
    if not served_raw or profile == "core":
        return
    from kater.doctor import parse_profiles

    if profile not in parse_profiles(served_raw):
        raise ConnectorPolicyError(
            f"profile {profile!r} is not served by this Kater runtime",
            code="policy_blocked",
        )


def _seed_catalog() -> None:
    from kater.connectors.seed import seed_builtin_connectors

    try:
        seed_builtin_connectors()
    except ConnectorError:
        raise
    except Exception as exc:
        raise ConnectorUnavailableError(
            f"connector catalog seed failed: {redact_text(str(exc))}",
            code="catalog_seed_failed",
        ) from exc


def _score(
    query: str, connector_id: str, display_name: str, capability_id: str, description: str
) -> int:
    text = query.strip().lower()
    if not text:
        return 1
    words = [match.group(0).lower() for match in _WORD.finditer(text)]
    cap = capability_id.lower()
    connector = f"{connector_id} {display_name}".lower()
    desc = description.lower()
    score = 0
    if text in cap:
        score += 12
    if text in desc:
        score += 7
    for word in words:
        if word in cap:
            score += 5
        elif word in connector:
            score += 3
        elif word in desc:
            score += 2
    return score


def search_tools(
    query: str,
    *,
    profile: str,
    limit: int = 10,
    include_unavailable: bool = False,
) -> dict[str, Any]:
    """Search registered connector capabilities using deterministic lexical ranking."""
    _assert_served_profile(profile)
    _seed_catalog()
    bounded_limit = max(1, min(int(limit), 50))
    matches: list[dict[str, Any]] = []

    hidden = hidden_integration_ids()
    for record in list_connectors():
        if record.id in hidden:
            continue
        health = evaluate_health(record, profile=profile)
        granted = record.permission_for(profile)
        for capability in record.capabilities:
            needed = capability.required_permission()
            available = health.state in _AVAILABLE_HEALTH and permission_allows(granted, needed)
            if not available and not include_unavailable:
                continue
            score = _score(
                query,
                record.id,
                record.display_name,
                capability.id,
                capability.description,
            )
            if query.strip() and score <= 0:
                continue
            matches.append(
                {
                    "connector_id": record.id,
                    "integration_id": record.id,
                    "toolkit": record.id,
                    "connection_id": default_connection_id(record.id),
                    "capability_id": capability.id,
                    "action": capability.id,
                    "description": capability.description,
                    "input_schema": dict(capability.input_schema),
                    "mutation": capability.mutation,
                    "required_permission": needed.value,
                    "granted_permission": granted.value,
                    "health": health.state.value,
                    "available": available,
                    "score": score,
                }
            )

    matches.sort(
        key=lambda item: (-int(item["score"]), item["capability_id"], item["connector_id"])
    )
    selected = matches[:bounded_limit]
    return {
        "query": query,
        "profile": profile,
        "total": len(matches),
        "tools": selected,
    }


def _resolve_connector(capability_id: str, connector_id: str | None) -> str:
    if connector_id:
        record = get_connector(connector_id)
        if record is None:
            raise ConnectorNotFoundError(connector_id)
        owner = native_action_owner(capability_id)
        if record.capability(capability_id) is None and owner != connector_id:
            raise ConnectorCapabilityError(
                f"capability {capability_id!r} not found on connector {connector_id!r}",
                connector_id=connector_id,
            )
        return connector_id

    prefix = capability_id.split(".", 1)[0] if "." in capability_id else ""
    if prefix:
        record = get_connector(prefix)
        owner = native_action_owner(capability_id)
        if record is not None and (
            record.capability(capability_id) is not None or owner == prefix
        ):
            return prefix

    owners = [
        record.id for record in list_connectors() if record.capability(capability_id) is not None
    ]
    owner = native_action_owner(capability_id)
    if owner and owner not in owners:
        owners.append(owner)
    if not owners:
        raise ConnectorCapabilityError(f"capability {capability_id!r} is not registered")
    if len(owners) > 1:
        owners_text = ", ".join(sorted(owners))
        raise ConnectorCapabilityError(
            f"capability {capability_id!r} is ambiguous across connectors: {owners_text}"
        )
    return owners[0]


def _record_audit(
    *,
    capability_id: str,
    principal_id: str,
    context_id: str | None,
    outcome: str,
    reason: str | None,
    duration_ms: float,
    profile: str,
    connection_id: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    idempotency_key: str | None = None,
    error_code: str | None = None,
) -> int | None:
    """Record an execution without turning audit-storage failure into a provider retry."""
    try:
        return record_capability_audit(
            capability_id=capability_id,
            principal_id=principal_id,
            context_id=context_id,
            outcome=outcome,
            reason=reason,
            duration_ms=duration_ms,
            profile=profile,
            connection_id=connection_id,
            action=action,
            actor_id=actor_id,
            agent_id=agent_id,
            run_id=run_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            error_code=error_code,
        )
    except Exception:
        _log.exception("capability audit write failed for %s", capability_id)
        return None


def _coerce_identity(
    identity: ActorIdentity | dict[str, Any] | None,
    *,
    principal_id: str,
) -> ActorIdentity:
    if isinstance(identity, ActorIdentity):
        return identity
    return ActorIdentity.from_mapping(identity, default_actor=principal_id)


def _coerce_policy(
    policy_context: PolicyContext | dict[str, Any] | None,
    *,
    profile: str,
    context_id: str | None,
    timeout_seconds: float | None,
    idempotency_key: str | None,
    run_id: str | None,
    trace_id: str | None,
) -> PolicyContext:
    if isinstance(policy_context, PolicyContext):
        policy = policy_context
    else:
        policy = PolicyContext.from_mapping(
            policy_context,
            profile=profile,
            context_id=context_id,
        )
    updates: dict[str, Any] = {}
    if timeout_seconds is not None:
        updates["timeout_seconds"] = timeout_seconds
    if idempotency_key:
        updates["idempotency_key"] = idempotency_key
    if run_id:
        updates["run_id"] = run_id
    if trace_id:
        updates["trace_id"] = trace_id
    if context_id and not policy.context_id:
        updates["context_id"] = context_id
    if profile and policy.profile == "core" and profile != "core":
        updates["profile"] = profile
    if updates:
        data = policy.as_dict()
        data.update(updates)
        policy = PolicyContext.from_mapping(data)
    return policy


def _resolve_action_capability(
    integration_id: str,
    action: str,
) -> ConnectorCapability | None:
    record = get_connector(integration_id)
    if record is not None:
        found = record.capability(action)
        if found is not None:
            return found
    owner = native_action_owner(action)
    if owner == integration_id:
        for item in GITHUB_PR_ACTIONS:
            if item.id == action:
                return item
    return None


def _dispatch(
    integration_id: str,
    action: str,
    payload: dict[str, Any],
    *,
    profile: str,
) -> dict[str, Any]:
    owner = native_action_owner(action)
    if owner is not None:
        if owner != integration_id:
            raise ConnectorCapabilityError(
                f"action {action!r} is not available on {integration_id!r}",
                connector_id=integration_id,
            )
        return invoke_native_action(action, payload)
    return connector_registry.invoke(
        integration_id,
        action,
        payload,
        profile=profile,
    )


def _assert_connection(
    connection_id: str,
    integration_id: str,
    *,
    require_configured: bool = False,
) -> None:
    view = get_connection_view(connection_id)
    if view is None:
        raise ConnectorCapabilityError(
            f"connection {connection_id!r} is not registered",
            connector_id=integration_id,
        )
    try:
        parsed, _suffix = parse_connection_id(connection_id)
    except ValueError as exc:
        raise ConnectorCapabilityError(str(exc), connector_id=integration_id) from exc
    if parsed != integration_id:
        raise ConnectorCapabilityError(
            f"connection {connection_id!r} does not belong to {integration_id!r}",
            connector_id=integration_id,
        )
    if require_configured and not view.configured:
        raise ConnectorAuthError(
            f"connection {connection_id!r} is missing credentials",
            connector_id=integration_id,
        )


def _assert_dangerous_policy(
    action: str,
    payload: dict[str, Any],
    capability: ConnectorCapability | None,
    policy: PolicyContext,
    identity: ActorIdentity,
    *,
    integration_id: str,
) -> None:
    mutation = bool(capability.mutation) if capability is not None else False
    if not action_is_dangerous(action, mutation=mutation):
        return
    if not policy.allow_dangerous:
        raise ConnectorPolicyError(
            f"dangerous action {action!r} is not allowed in this policy context",
            connector_id=integration_id,
            code="policy_blocked",
        )
    if identity.actor_id == "anonymous":
        raise ConnectorPolicyError(
            f"dangerous action {action!r} requires a non-anonymous actor identity",
            connector_id=integration_id,
            code="policy_blocked",
        )
    if action == "github.pr.merge":
        sha = str(payload.get("expected_head_sha") or policy.expected_head_sha or "").strip()
        if not sha:
            raise ConnectorPolicyError(
                "dangerous write requires a nonempty expected_head_sha",
                connector_id=integration_id,
                code="policy_blocked",
            )


def _normalize_input(
    action: str | None,
    capability_id: str | None,
    raw_input: dict[str, Any] | None,
    arguments: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    resolved = (action or capability_id or "").strip()
    if not resolved:
        raise ConnectorCapabilityError("action is required")
    payload = raw_input if raw_input is not None else arguments
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ConnectorCapabilityError("input must be an object")
    return resolved, payload


def _resolve_integration(
    connection: str | None,
    connector_id: str | None,
    action: str,
) -> str:
    if connection:
        integration_id = resolve_integration_id(connection)
        if connector_id and connector_id != integration_id:
            raise ConnectorCapabilityError(
                f"connection {connection!r} does not match connector {connector_id!r}",
                connector_id=connector_id,
            )
        return integration_id
    return _resolve_connector(action, connector_id)


def _apply_merge_sha(action: str, payload: dict[str, Any], policy: PolicyContext) -> dict[str, Any]:
    if (
        action == "github.pr.merge"
        and policy.expected_head_sha
        and not str(payload.get("expected_head_sha") or "").strip()
    ):
        return {**payload, "expected_head_sha": policy.expected_head_sha}
    return payload


def _authorize_action(
    integration_id: str,
    action: str,
    payload: dict[str, Any],
    policy: PolicyContext,
    actor: ActorIdentity,
) -> None:
    capability = _resolve_action_capability(integration_id, action)
    if capability is None:
        raise ConnectorCapabilityError(
            f"action {action!r} is not registered",
            connector_id=integration_id,
        )
    if capability is not None:
        validate_action_input(capability.input_schema, payload)
    record = get_connector(integration_id)
    if record is not None:
        assert_profile_access(
            record,
            policy.profile,
            action,
            mutation=bool(capability.mutation) if capability is not None else False,
        )
    _assert_dangerous_policy(
        action,
        payload,
        capability,
        policy,
        actor,
        integration_id=integration_id,
    )


@dataclass
class _CallState:
    connection_id: str
    integration_id: str
    payload: dict[str, Any]
    fingerprint: str = ""


def _prepare(
    state: _CallState,
    *,
    connection: str | None,
    connector_id: str | None,
    action: str,
    policy: PolicyContext,
    actor: ActorIdentity,
) -> None:
    _assert_served_profile(policy.profile)
    _seed_catalog()
    state.integration_id = _resolve_integration(connection, connector_id, action)
    state.connection_id = connection or default_connection_id(state.integration_id)
    capability = _resolve_action_capability(state.integration_id, action)
    _assert_connection(state.connection_id, state.integration_id)
    state.payload = _apply_merge_sha(action, state.payload, policy)
    _authorize_action(state.integration_id, action, state.payload, policy, actor)
    if (
        capability is not None
        and capability.mutation
        and native_action_owner(action) == state.integration_id
    ):
        _assert_connection(
            state.connection_id,
            state.integration_id,
            require_configured=True,
        )
    state.fingerprint = input_fingerprint(state.connection_id, action, state.payload)


def _reserve_idempotent(
    policy: PolicyContext,
    fingerprint: str,
    actor: ActorIdentity,
) -> dict[str, Any] | None:
    if not policy.idempotency_key:
        return None
    cached = reserve_idempotency(
        policy.idempotency_key,
        fingerprint,
        principal_id=actor.principal_id or actor.actor_id,
    )
    if cached is None:
        return None
    replay = dict(cached)
    replay["idempotency_replay"] = True
    return replay


def _resolve_timeout(policy: PolicyContext, integration_id: str) -> float | None:
    timeout = policy.timeout_seconds
    if timeout is not None:
        return timeout
    record = get_connector(integration_id)
    if record is not None:
        return record.transport.timeout_seconds
    return None


def _classify_error(exc: ConnectorError) -> str:
    if isinstance(exc, (ConnectorPolicyError, ConnectorAuthError, ConnectorCapabilityError)):
        return "denied"
    return "error"


def _run_attempts(
    integration_id: str,
    action: str,
    payload: dict[str, Any],
    policy: PolicyContext,
) -> tuple[dict[str, Any] | None, ConnectorError | None, int]:
    timeout = _resolve_timeout(policy, integration_id)
    attempts = 0
    last_error: ConnectorError | None = None
    result: dict[str, Any] | None = None
    while True:
        attempts += 1
        try:
            result = run_with_timeout(
                lambda: _dispatch(
                    integration_id,
                    action,
                    payload,
                    profile=policy.profile,
                ),
                timeout,
            )
            return result, None, attempts
        except (ConnectorPolicyError, ConnectorAuthError, ConnectorCapabilityError) as exc:
            return None, exc, attempts
        except ConnectorError as exc:
            last_error = exc
            if attempts <= policy.max_retries and is_retryable(exc):
                continue
            return None, last_error, attempts
        except Exception as exc:
            return (
                None,
                ConnectorUnavailableError(
                    redact_text(str(exc)),
                    connector_id=integration_id,
                ),
                attempts,
            )


def _audit_fields(
    *,
    action: str,
    actor: ActorIdentity,
    policy: PolicyContext,
    connection_id: str,
    run_id: str,
    trace_id: str,
    outcome: str,
    reason: str | None,
    duration_ms: float,
    error_code: str | None = None,
) -> int | None:
    return _record_audit(
        capability_id=action,
        principal_id=actor.principal_id or actor.actor_id,
        context_id=policy.context_id,
        outcome=outcome,
        reason=reason,
        duration_ms=duration_ms,
        profile=policy.profile,
        connection_id=connection_id,
        action=action,
        actor_id=actor.actor_id,
        agent_id=actor.agent_id,
        run_id=run_id,
        trace_id=trace_id,
        idempotency_key=policy.idempotency_key,
        error_code=error_code,
    )


def _success_payload(
    *,
    connection_id: str,
    integration_id: str,
    action: str,
    actor: ActorIdentity,
    policy: PolicyContext,
    run_id: str,
    trace_id: str,
    result: dict[str, Any],
    attempts: int,
    started: float,
    fingerprint: str,
) -> dict[str, Any]:
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    audit_id = _audit_fields(
        action=action,
        actor=actor,
        policy=policy,
        connection_id=connection_id,
        run_id=run_id,
        trace_id=trace_id,
        outcome="allowed",
        reason=f"connection={connection_id}",
        duration_ms=duration_ms,
    )
    payload_out = ExecutionResult(
        ok=True,
        connection_id=connection_id,
        action=action,
        integration_id=integration_id,
        toolkit=integration_id,
        identity=actor,
        run_id=run_id,
        trace_id=trace_id,
        result=result,
        audit_id=audit_id,
        audit_recorded=audit_id is not None,
        duration_ms=duration_ms,
        attempts=attempts,
        extra={"profile": policy.profile, "context_id": policy.context_id},
    ).as_dict()
    if policy.idempotency_key:
        store_idempotency(
            policy.idempotency_key,
            fingerprint,
            payload_out,
            principal_id=actor.principal_id or actor.actor_id,
        )
    return payload_out


def _attach_failure(
    exc: ConnectorError,
    *,
    connection_id: str,
    integration_id: str,
    action: str,
    actor: ActorIdentity,
    policy: PolicyContext,
    run_id: str,
    trace_id: str,
    outcome: str,
    reason: str | None,
    error_code: str | None,
    attempts: int,
    started: float,
) -> None:
    if outcome == "allowed":
        outcome = _classify_error(exc)
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    audit_id = _audit_fields(
        action=action,
        actor=actor,
        policy=policy,
        connection_id=connection_id,
        run_id=run_id,
        trace_id=trace_id,
        outcome=outcome,
        reason=reason or redact_text(str(exc)),
        duration_ms=duration_ms,
        error_code=error_code or exc.code,
    )
    exc.execution = ExecutionResult(
        ok=False,
        connection_id=connection_id,
        action=action,
        integration_id=integration_id,
        toolkit=integration_id,
        identity=actor,
        run_id=run_id,
        trace_id=trace_id,
        error=ExecutionError(
            code=exc.code,
            message=redact_text(str(exc)),
            retryable=is_retryable(exc),
        ),
        audit_id=audit_id,
        audit_recorded=audit_id is not None,
        duration_ms=duration_ms,
        attempts=max(attempts, 1),
        extra={"profile": policy.profile, "context_id": policy.context_id},
    ).as_dict()


def execute(
    capability_id: str | None = None,
    arguments: dict[str, Any] | None = None,
    *,
    connection: str | None = None,
    action: str | None = None,
    input: dict[str, Any] | None = None,
    identity: ActorIdentity | dict[str, Any] | None = None,
    policy_context: PolicyContext | dict[str, Any] | None = None,
    profile: str = "core",
    connector_id: str | None = None,
    principal_id: str = "anonymous",
    context_id: str | None = None,
    timeout_seconds: float | None = None,
    idempotency_key: str | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Execute one action through connection, policy, audit, and toolkit dispatch.

    Canonical form: ``execute(connection, action, input, identity, policy_context)``.
    The positional ``capability_id`` / ``arguments`` form stays as compatibility.
    """
    resolved_action, payload = _normalize_input(action, capability_id, input, arguments)
    actor = _coerce_identity(identity, principal_id=principal_id)
    policy = _coerce_policy(
        policy_context,
        profile=profile,
        context_id=context_id,
        timeout_seconds=timeout_seconds,
        idempotency_key=idempotency_key,
        run_id=run_id,
        trace_id=trace_id,
    )
    run_id, trace_id = new_ids(policy)
    state = _CallState(
        connection_id=connection or "",
        integration_id=connector_id or "",
        payload=payload,
    )
    return _invoke(
        state,
        connection=connection,
        connector_id=connector_id,
        action=resolved_action,
        actor=actor,
        policy=policy,
        run_id=run_id,
        trace_id=trace_id,
    )


def _raise_dispatch_error(last_error: ConnectorError) -> tuple[str, str, str]:
    return _classify_error(last_error), last_error.code, redact_text(str(last_error))


def _invoke(
    state: _CallState,
    *,
    connection: str | None,
    connector_id: str | None,
    action: str,
    actor: ActorIdentity,
    policy: PolicyContext,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    outcome = "allowed"
    reason: str | None = None
    error_code: str | None = None
    attempts = 0
    reserved = False
    try:
        _prepare(
            state,
            connection=connection,
            connector_id=connector_id,
            action=action,
            policy=policy,
            actor=actor,
        )
        replay = _reserve_idempotent(policy, state.fingerprint, actor)
        if replay is not None:
            return replay
        reserved = bool(policy.idempotency_key)
        result, last_error, attempts = _run_attempts(
            state.integration_id, action, state.payload, policy
        )
        if last_error is not None:
            outcome, error_code, reason = _raise_dispatch_error(last_error)
            raise last_error
        if result is None:
            raise ConnectorUnavailableError(
                "action returned no result",
                connector_id=state.integration_id,
            )
        return _success_payload(
            connection_id=state.connection_id,
            integration_id=state.integration_id,
            action=action,
            actor=actor,
            policy=policy,
            run_id=run_id,
            trace_id=trace_id,
            result=result,
            attempts=attempts,
            started=started,
            fingerprint=state.fingerprint,
        )
    except ConnectorError as exc:
        if reserved and policy.idempotency_key:
            release_idempotency(
                policy.idempotency_key,
                principal_id=actor.principal_id or actor.actor_id,
            )
        _attach_failure(
            exc,
            connection_id=state.connection_id,
            integration_id=state.integration_id,
            action=action,
            actor=actor,
            policy=policy,
            run_id=run_id,
            trace_id=trace_id,
            outcome=outcome,
            reason=reason,
            error_code=error_code,
            attempts=attempts,
            started=started,
        )
        raise
