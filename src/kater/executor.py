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
from typing import Any

from kater.capabilities.audit import record_capability_audit
from kater.connections import (
    default_connection_id,
    get_connection_view,
    parse_connection_id,
    resolve_integration_id,
)
from kater.connectors import registry as connector_registry
from kater.connectors.auth import redact_text
from kater.connectors.errors import (
    ConnectorAuthError,
    ConnectorCapabilityError,
    ConnectorError,
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
    lookup_idempotency,
    new_ids,
    run_with_timeout,
    store_idempotency,
    validate_action_input,
)
from kater.toolkits import invoke_native_action, native_action_ids

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

    for record in list_connectors():
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
            from kater.connectors.errors import ConnectorNotFoundError

            raise ConnectorNotFoundError(connector_id)
        if record.capability(capability_id) is None and capability_id not in native_action_ids():
            raise ConnectorCapabilityError(
                f"capability {capability_id!r} not found on connector {connector_id!r}",
                connector_id=connector_id,
            )
        return connector_id

    prefix = capability_id.split(".", 1)[0] if "." in capability_id else ""
    if prefix:
        record = get_connector(prefix)
        if record is not None and (
            record.capability(capability_id) is not None or capability_id in native_action_ids()
        ):
            return prefix

    owners = [
        record.id for record in list_connectors() if record.capability(capability_id) is not None
    ]
    if capability_id in native_action_ids() and "github" not in owners:
        owners.append("github")
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
    if action in native_action_ids():
        from kater.toolkits.github import GITHUB_PR_ACTIONS

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
    if action in native_action_ids():
        return invoke_native_action(action, payload)
    return connector_registry.invoke(
        integration_id,
        action,
        payload,
        profile=profile,
    )


def _assert_connection(connection_id: str, integration_id: str) -> None:
    view = get_connection_view(connection_id)
    if view is None:
        raise ConnectorCapabilityError(
            f"connection {connection_id!r} is not registered",
            connector_id=integration_id,
        )
    parsed, _suffix = parse_connection_id(connection_id)
    if parsed != integration_id:
        raise ConnectorCapabilityError(
            f"connection {connection_id!r} does not belong to {integration_id!r}",
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
    resolved_action = (action or capability_id or "").strip()
    if not resolved_action:
        raise ConnectorCapabilityError("action is required")
    payload = input if input is not None else arguments
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ConnectorCapabilityError("input must be an object")

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
    connection_id = connection or ""
    integration_id = connector_id or ""
    started = time.perf_counter()
    outcome = "allowed"
    reason: str | None = None
    error_code: str | None = None
    attempts = 0
    result: dict[str, Any] | None = None
    last_error: ConnectorError | None = None

    try:
        _assert_served_profile(policy.profile)
        _seed_catalog()
        if connection:
            integration_id = resolve_integration_id(connection)
            if connector_id and connector_id != integration_id:
                raise ConnectorCapabilityError(
                    f"connection {connection!r} does not match connector {connector_id!r}",
                    connector_id=connector_id,
                )
        elif connector_id:
            integration_id = _resolve_connector(resolved_action, connector_id)
        else:
            integration_id = _resolve_connector(resolved_action, None)

        connection_id = connection or default_connection_id(integration_id)
        _assert_connection(connection_id, integration_id)
        capability = _resolve_action_capability(integration_id, resolved_action)
        if capability is None and resolved_action not in native_action_ids():
            raise ConnectorCapabilityError(
                f"action {resolved_action!r} is not registered",
                connector_id=integration_id,
            )
        if capability is not None:
            validate_action_input(capability.input_schema, payload)
        if (
            resolved_action == "github.pr.merge"
            and policy.expected_head_sha
            and not str(payload.get("expected_head_sha") or "").strip()
        ):
            payload = {**payload, "expected_head_sha": policy.expected_head_sha}
        record = get_connector(integration_id)
        if record is not None:
            assert_profile_access(
                record,
                policy.profile,
                resolved_action,
                mutation=bool(capability.mutation) if capability is not None else False,
            )
        _assert_dangerous_policy(
            resolved_action,
            payload,
            capability,
            policy,
            actor,
            integration_id=integration_id,
        )

        fingerprint = input_fingerprint(connection_id, resolved_action, payload)
        if policy.idempotency_key:
            cached = lookup_idempotency(policy.idempotency_key, fingerprint)
            if cached is not None:
                cached = dict(cached)
                cached["idempotency_replay"] = True
                return cached

        timeout = policy.timeout_seconds
        if timeout is None:
            record = get_connector(integration_id)
            if record is not None:
                timeout = record.transport.timeout_seconds

        while True:
            attempts += 1
            try:
                result = run_with_timeout(
                    lambda: _dispatch(
                        integration_id,
                        resolved_action,
                        payload,
                        profile=policy.profile,
                    ),
                    timeout,
                )
                last_error = None
                break
            except (ConnectorPolicyError, ConnectorAuthError, ConnectorCapabilityError) as exc:
                last_error = exc
                break
            except ConnectorError as exc:
                last_error = exc
                if attempts <= policy.max_retries and is_retryable(exc):
                    continue
                break
            except Exception as exc:
                last_error = ConnectorUnavailableError(
                    redact_text(str(exc)),
                    connector_id=integration_id,
                )
                break
        if last_error is not None:
            if isinstance(
                last_error, (ConnectorPolicyError, ConnectorAuthError, ConnectorCapabilityError)
            ):
                outcome = "denied"
            else:
                outcome = "error"
            error_code = last_error.code
            reason = redact_text(str(last_error))
            raise last_error
        assert result is not None
        reason = f"connection={connection_id}"
        duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        audit_id = _record_audit(
            capability_id=resolved_action,
            principal_id=actor.principal_id or actor.actor_id,
            context_id=policy.context_id,
            outcome="allowed",
            reason=reason,
            duration_ms=duration_ms,
            profile=policy.profile,
            connection_id=connection_id,
            action=resolved_action,
            actor_id=actor.actor_id,
            agent_id=actor.agent_id,
            run_id=run_id,
            trace_id=trace_id,
            idempotency_key=policy.idempotency_key,
        )
        envelope = ExecutionResult(
            ok=True,
            connection_id=connection_id,
            action=resolved_action,
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
        )
        payload_out = envelope.as_dict()
        if policy.idempotency_key:
            store_idempotency(policy.idempotency_key, fingerprint, payload_out)
        return payload_out
    except ConnectorError as exc:
        if outcome == "allowed":
            if isinstance(
                exc, (ConnectorPolicyError, ConnectorAuthError, ConnectorCapabilityError)
            ):
                outcome = "denied"
            else:
                outcome = "error"
        duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        audit_id = _record_audit(
            capability_id=resolved_action,
            principal_id=actor.principal_id or actor.actor_id,
            context_id=policy.context_id,
            outcome=outcome,
            reason=reason or redact_text(str(exc)),
            duration_ms=duration_ms,
            profile=policy.profile,
            connection_id=connection_id,
            action=resolved_action,
            actor_id=actor.actor_id,
            agent_id=actor.agent_id,
            run_id=run_id,
            trace_id=trace_id,
            idempotency_key=policy.idempotency_key,
            error_code=error_code or exc.code,
        )
        failed = ExecutionResult(
            ok=False,
            connection_id=connection_id,
            action=resolved_action,
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
        )
        setattr(exc, "execution", failed.as_dict())
        raise
