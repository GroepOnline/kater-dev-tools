"""Unit tests for CHE-659 capability manifest registry and discovery."""

from __future__ import annotations

import pytest

from kater.capabilities.builtins import BUILTIN_CAPABILITIES
from kater.capabilities.discovery import CapabilityDenied, assert_invocable, discover
from kater.capabilities.models import (
    CapabilityManifest,
    CapabilityTransport,
    DiscoveryContext,
    LifecycleState,
    RiskClass,
    risk_rank,
)
from kater.capabilities.registry import CapabilityRegistry, reset_default_registry


def _manifest(
    capability_id: str = "demo.tool.run",
    *,
    version: str = "1.0.0",
    digest: str = "sha256:abc",
    risk: RiskClass = RiskClass.READ,
    lifecycle: LifecycleState = LifecycleState.ACTIVE,
    profiles: frozenset[str] | None = None,
    scopes: frozenset[str] | None = None,
    tags: frozenset[str] | None = None,
    description: str = "Demo capability",
) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        package_id="demo",
        publisher_id="online" + "chefgroep",
        version=version,
        digest=digest,
        transport=CapabilityTransport.NATIVE,
        description=description,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_scopes=scopes if scopes is not None else frozenset(),
        risk_class=risk,
        data_classification="internal",
        profiles=profiles if profiles is not None else frozenset({"core"}),
        lifecycle_state=lifecycle,
        tags=tags if tags is not None else frozenset(),
    )


def test_capability_id_rejects_double_underscore() -> None:
    with pytest.raises(ValueError, match="__"):
        _manifest("bad__id")


def test_risk_rank_ordering() -> None:
    assert risk_rank(RiskClass.READ) < risk_rank(RiskClass.EXTERNAL_WRITE)
    assert risk_rank(RiskClass.EXTERNAL_WRITE) < risk_rank(RiskClass.DESTRUCTIVE)


def test_register_idempotent_same_digest() -> None:
    registry = CapabilityRegistry()
    registry.register(_manifest())
    registry.register(_manifest())
    assert len(registry.list()) == 1


def test_register_rejects_digest_mismatch() -> None:
    registry = CapabilityRegistry()
    registry.register(_manifest(digest="sha256:one"))
    with pytest.raises(ValueError, match="different digest"):
        registry.register(_manifest(digest="sha256:two"))


def test_get_prefers_active_latest_version() -> None:
    registry = CapabilityRegistry()
    registry.register(_manifest(version="1.0.0", digest="sha256:a"))
    registry.register(
        _manifest(version="2.0.0", digest="sha256:b", lifecycle=LifecycleState.DEPRECATED)
    )
    registry.register(_manifest(version="1.5.0", digest="sha256:c"))
    got = registry.get("demo.tool.run")
    assert got is not None
    assert got.version == "1.5.0"


def test_unmanaged_capability_is_invocable() -> None:
    registry = CapabilityRegistry()
    ok, reason = registry.is_invocable("exa__web_search_exa")
    assert ok is True
    assert reason == "unmanaged"


def test_revoked_capability_denied() -> None:
    registry = CapabilityRegistry()
    registry.register(_manifest())
    registry.revoke("demo.tool.run", "1.0.0")
    ok, reason = registry.is_invocable("demo.tool.run")
    assert ok is False
    assert "revoked" in reason
    with pytest.raises(CapabilityDenied):
        assert_invocable("demo.tool.run", registry=registry)


def test_discover_filters_by_profile_risk_and_lifecycle() -> None:
    registry = CapabilityRegistry()
    registry.register(_manifest(capability_id="a.read", risk=RiskClass.READ, digest="sha256:1"))
    registry.register(
        _manifest(
            capability_id="b.write",
            risk=RiskClass.EXTERNAL_WRITE,
            digest="sha256:2",
            profiles=frozenset({"ops"}),
        )
    )
    registry.register(
        _manifest(
            capability_id="c.gone",
            digest="sha256:3",
            lifecycle=LifecycleState.REVOKED,
        )
    )
    found = discover(
        DiscoveryContext(profile_ids=frozenset({"core"}), max_risk=RiskClass.READ),
        registry=registry,
    )
    ids = {item.capability_id for item in found}
    assert ids == {"a.read"}


def test_discover_intent_boost_sorts_matches_first() -> None:
    registry = CapabilityRegistry()
    registry.register(
        _manifest(
            capability_id="alpha.other",
            digest="sha256:1",
            description="unrelated",
        )
    )
    registry.register(
        _manifest(
            capability_id="beta.search",
            digest="sha256:2",
            description="Utrecht open data search",
            tags=frozenset({"search"}),
        )
    )
    found = discover(
        DiscoveryContext(profile_ids=frozenset({"core"}), task_intent="utrecht search"),
        registry=registry,
    )
    assert [item.capability_id for item in found] == ["beta.search", "alpha.other"]


def test_builtins_seeded_and_discoverable() -> None:
    reset_default_registry()
    from kater.capabilities.registry import get_default_registry

    registry = get_default_registry()
    ids = {m.capability_id for m in registry.list()}
    assert "kater.profiles.list" in ids
    assert "web.search" in ids
    assert len(BUILTIN_CAPABILITIES) >= 4
    found = discover(DiscoveryContext(profile_ids=frozenset({"core"})))
    assert any(item.capability_id.startswith("kater.") for item in found)
    reset_default_registry()
