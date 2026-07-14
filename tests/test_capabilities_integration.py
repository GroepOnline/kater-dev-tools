"""SQLite + ProxyManager integration tests for CHE-659 capabilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from kater.capabilities.models import (
    CapabilityManifest,
    CapabilityTransport,
    LifecycleState,
    RiskClass,
)
from kater.capabilities.registry import CapabilityRegistry, reset_default_registry
from kater.capabilities.store import (
    clear_capability_state,
    get_capability,
    list_capabilities,
    set_capability_lifecycle,
    upsert_capability,
)
from kater.control_plane import (
    ProviderAccount,
    clear_control_plane_state,
    upsert_route_candidate,
)
from kater.proxy.base import MockBackend
from kater.proxy.manager import ProxyManager


def _search_schema() -> dict:
    return {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }


def _manifest(
    capability_id: str = "web.search",
    *,
    version: str = "1.0.0",
    digest: str = "sha256:route",
    lifecycle: LifecycleState = LifecycleState.ACTIVE,
) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        package_id="exa",
        publisher_id="onlinechefgroep",
        version=version,
        digest=digest,
        transport=CapabilityTransport.REMOTE_MCP,
        description="Logical web search",
        input_schema=_search_schema(),
        output_schema={"type": "object"},
        required_scopes=frozenset({"web.read"}),
        risk_class=RiskClass.READ,
        data_classification="public",
        profiles=frozenset({"research", "web"}),
        lifecycle_state=lifecycle,
        tags=frozenset({"search"}),
    )


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    reset_default_registry()
    clear_control_plane_state()
    clear_capability_state()
    yield tmp_path
    clear_control_plane_state()
    clear_capability_state()
    reset_default_registry()


def test_capability_store_round_trip(isolated_db: Path) -> None:
    upsert_capability(_manifest())
    got = get_capability("web.search")
    assert got is not None
    assert got.version == "1.0.0"
    assert got.required_scopes == frozenset({"web.read"})
    updated = set_capability_lifecycle("web.search", "1.0.0", LifecycleState.REVOKED)
    assert updated.lifecycle_state == LifecycleState.REVOKED
    active = list_capabilities(include_non_active=False)
    assert active == []
    all_rows = list_capabilities(include_non_active=True)
    assert len(all_rows) == 1


def test_proxy_hides_and_denies_revoked_managed_route(
    isolated_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upsert_route_candidate(
        "web.search",
        ProviderAccount(
            account_id="exa-a",
            provider="exa",
            backend="exa",
            tool_name="search",
            scopes=frozenset({"web.read"}),
        ),
    )
    manager = ProxyManager()
    backend = MockBackend(
        tools=[
            {
                "name": "search",
                "description": "Search the web",
                "inputSchema": _search_schema(),
            }
        ],
        responses={"search": {"answer": "ok"}},
    )
    manager.register_backend("exa", backend)

    names = {tool["name"] for tool in manager.list_tools()}
    assert "web.search" in names

    registry = CapabilityRegistry()
    registry.register(_manifest())
    registry.revoke("web.search", "1.0.0")

    import kater.capabilities.discovery as discovery

    monkeypatch.setattr(discovery, "get_default_registry", lambda: registry)

    names_after = {tool["name"] for tool in manager.list_tools()}
    assert "web.search" not in names_after
    denied = manager.call_tool("web.search", {"query": "Utrecht"})
    assert denied.get("code") == "capability_denied"
    assert "revoked" in str(denied.get("reason", ""))


def test_proxy_unmanaged_backend_tool_still_works(isolated_db: Path) -> None:
    manager = ProxyManager()
    backend = MockBackend(
        tools=[{"name": "search", "inputSchema": _search_schema()}],
        responses={"search": {"ok": True}},
    )
    manager.register_backend("exa", backend)
    result = manager.call_tool("exa__search", {"query": "x"})
    assert result.get("ok") is True
