"""Uniform connector capability search and execution surface.

This is the agent-facing execution layer above the connector catalog. It does
not duplicate connector auth, policy, transport, or lifecycle logic: search
projects that state, while execute delegates enforcement to connectors.registry.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from kater.capabilities.audit import record_capability_audit
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
from kater.connectors.models import HealthState, permission_allows
from kater.connectors.store import get_connector, list_connectors

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
                    "capability_id": capability.id,
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
        if record.capability(capability_id) is None:
            raise ConnectorCapabilityError(
                f"capability {capability_id!r} not found on connector {connector_id!r}",
                connector_id=connector_id,
            )
        return connector_id

    prefix = capability_id.split(".", 1)[0] if "." in capability_id else ""
    if prefix:
        record = get_connector(prefix)
        if record is not None and record.capability(capability_id) is not None:
            return prefix

    owners = [
        record.id for record in list_connectors() if record.capability(capability_id) is not None
    ]
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
        )
    except Exception:
        _log.exception("capability audit write failed for %s", capability_id)
        return None


def execute(
    capability_id: str,
    arguments: dict[str, Any],
    *,
    profile: str,
    connector_id: str | None = None,
    principal_id: str = "anonymous",
    context_id: str | None = None,
) -> dict[str, Any]:
    """Resolve and execute one capability through existing connector enforcement."""
    if not isinstance(arguments, dict):
        raise ConnectorCapabilityError("arguments must be an object")
    _assert_served_profile(profile)
    _seed_catalog()
    resolved_connector = _resolve_connector(capability_id, connector_id)
    started = time.perf_counter()
    outcome = "allowed"
    reason: str | None = None

    try:
        result = connector_registry.invoke(
            resolved_connector,
            capability_id,
            arguments,
            profile=profile,
        )
    except (ConnectorPolicyError, ConnectorAuthError, ConnectorCapabilityError) as exc:
        outcome = "denied"
        reason = redact_text(str(exc))
        raise
    except ConnectorError as exc:
        outcome = "error"
        reason = redact_text(str(exc))
        raise
    except Exception as exc:
        outcome = "error"
        reason = redact_text(str(exc))
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000.0
        audit_id = _record_audit(
            capability_id=capability_id,
            principal_id=principal_id,
            context_id=context_id,
            outcome=outcome,
            reason=reason or f"connector={resolved_connector}",
            duration_ms=duration_ms,
            profile=profile,
        )

    return {
        "connector_id": resolved_connector,
        "capability_id": capability_id,
        "profile": profile,
        "audit_id": audit_id,
        "audit_recorded": audit_id is not None,
        "duration_ms": round(duration_ms, 3),
        "result": result,
    }
