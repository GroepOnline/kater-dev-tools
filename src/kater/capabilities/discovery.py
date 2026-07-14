from __future__ import annotations

import re

from kater.capabilities.models import (
    CapabilityManifest,
    DiscoveredCapability,
    DiscoveryContext,
    LifecycleState,
    approval_expected_for,
    risk_rank,
)
from kater.capabilities.registry import CapabilityRegistry, get_default_registry

_DISCOVERABLE = frozenset({LifecycleState.ACTIVE, LifecycleState.CANARY})
_INTENT_WORD = re.compile(r"[a-z0-9_./-]+", re.IGNORECASE)


class CapabilityDenied(Exception):
    """Raised when a registered capability is not invocable."""

    def __init__(self, capability_id: str, reason: str) -> None:
        self.capability_id = capability_id
        self.reason = reason
        super().__init__(f"capability {capability_id!r} denied: {reason}")


def _profile_match(manifest: CapabilityManifest, context: DiscoveryContext) -> bool:
    if not manifest.profiles:
        return True
    if not context.profile_ids:
        return True
    return bool(manifest.profiles & context.profile_ids)


def _scope_match(manifest: CapabilityManifest, context: DiscoveryContext) -> bool:
    if not context.required_scopes:
        return True
    return context.required_scopes.issubset(manifest.required_scopes)


def _tag_match(manifest: CapabilityManifest, context: DiscoveryContext) -> bool:
    if not context.tags_any:
        return True
    return bool(manifest.tags & context.tags_any)


def _health_ok(manifest: CapabilityManifest, registry: CapabilityRegistry) -> bool:
    """Foundation health: ok unless a named healthcheck capability is non-invocable."""
    check_id = manifest.healthcheck_capability_id
    if not check_id:
        return True
    ok, _reason = registry.is_invocable(check_id)
    return ok


def _intent_words(intent: str) -> frozenset[str]:
    return frozenset(m.group(0).lower() for m in _INTENT_WORD.finditer(intent))


def _intent_boost(manifest: CapabilityManifest, words: frozenset[str]) -> bool:
    if not words:
        return False
    haystack = " ".join(
        (
            manifest.capability_id.lower(),
            manifest.description.lower(),
            " ".join(sorted(t.lower() for t in manifest.tags)),
        )
    )
    return any(word in haystack for word in words)


def discover(
    context: DiscoveryContext,
    registry: CapabilityRegistry | None = None,
) -> list[DiscoveredCapability]:
    """Compile the minimal capability set for a discovery context."""
    reg = registry if registry is not None else get_default_registry()
    max_rank = risk_rank(context.max_risk)
    words = _intent_words(context.task_intent)

    matched: list[tuple[bool, CapabilityManifest, bool]] = []
    for manifest in reg.list(include_non_active=True):
        if manifest.lifecycle_state not in _DISCOVERABLE:
            continue
        if not _profile_match(manifest, context):
            continue
        if risk_rank(manifest.risk_class) > max_rank:
            continue
        if not _scope_match(manifest, context):
            continue
        if not _tag_match(manifest, context):
            continue
        health_ok = _health_ok(manifest, reg)
        if not health_ok and not context.include_unhealthy:
            continue
        boosted = _intent_boost(manifest, words)
        matched.append((boosted, manifest, health_ok))

    # Intent matches first; stable secondary sort by capability_id then version.
    matched.sort(key=lambda row: (not row[0], row[1].capability_id, row[1].version))

    return [
        DiscoveredCapability(
            capability_id=manifest.capability_id,
            version=manifest.version,
            digest=manifest.digest,
            description=manifest.description,
            risk_class=manifest.risk_class,
            lifecycle_state=manifest.lifecycle_state,
            required_scopes=manifest.required_scopes,
            input_schema=dict(manifest.input_schema),
            approval_expected=approval_expected_for(manifest.risk_class),
            health_ok=health_ok,
        )
        for _boosted, manifest, health_ok in matched
    ]


def assert_invocable(
    capability_id: str,
    registry: CapabilityRegistry | None = None,
) -> None:
    """Raise CapabilityDenied when a registered capability is not invocable."""
    reg = registry if registry is not None else get_default_registry()
    ok, reason = reg.is_invocable(capability_id)
    if not ok:
        raise CapabilityDenied(capability_id, reason)
