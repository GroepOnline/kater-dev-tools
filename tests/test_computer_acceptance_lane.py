"""Focused contract/lifecycle tests for the Kater Computer acceptance lane."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kater.capabilities.computer import (
    COMPUTER_CAPABILITY_IDS,
    VENDORED_CONTRACT,
    ComputerConnector,
    ContractDigestError,
    build_invocation_request,
    computer_tool_source,
    load_computer_manifests,
    load_computer_manifests_from_udo,
    make_invocation_result,
    revoke_computer_capability,
    validate_invocation_envelope,
)
from kater.capabilities.models import LifecycleState
from kater.capabilities.registry import CapabilityRegistry
from kater.control_plane import ProviderAccount, upsert_route_candidate
from kater.proxy.base import MockBackend


def test_vendored_contract_loads_the_schema_owned_acceptance_catalog() -> None:
    manifests = load_computer_manifests(VENDORED_CONTRACT)

    assert tuple(item.capability_id for item in manifests) == COMPUTER_CAPABILITY_IDS
    assert all(item.package_id == "computer" for item in manifests)
    assert manifests[0].method == "POST"
    assert manifests[0].path == "/filesystem/read"


def test_loader_rejects_contract_digest_drift(tmp_path: Path) -> None:
    payload = json.loads(VENDORED_CONTRACT.read_text(encoding="utf-8"))
    payload["source_digest"] = "sha256:" + "0" * 64
    drifted = tmp_path / "computer-capabilities.json"
    drifted.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ContractDigestError, match="digest"):
        load_computer_manifests(drifted)


def test_udo_loader_requires_generated_contract(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with pytest.raises(ContractDigestError, match="generated Computer contract missing"):
        load_computer_manifests_from_udo(tmp_path)


def test_computer_ids_are_managed_and_unknown_ids_are_denied() -> None:
    registry = CapabilityRegistry()
    registry.register(load_computer_manifests(VENDORED_CONTRACT)[0])

    assert registry.is_managed(COMPUTER_CAPABILITY_IDS[0])
    assert not registry.is_managed("computer.unknown")
    connector = ComputerConnector(load_computer_manifests(VENDORED_CONTRACT), registry)
    assert connector.is_reserved("computer.unknown") is True
    assert connector.is_reserved("filesystem.unknown") is True
    assert connector.call("filesystem.unknown", {})["error"]["code"] == "capability_denied"


def test_revoke_changes_registry_snapshot_and_denies_next_call() -> None:
    registry = CapabilityRegistry()
    for manifest in load_computer_manifests(VENDORED_CONTRACT):
        registry.register(manifest)
    before = registry.snapshot()

    registry.revoke("filesystem.read", "1.0.0")
    after = registry.snapshot()

    assert after.version > before.version
    assert "filesystem.read" not in {item.capability_id for item in after.manifests}
    assert registry.is_invocable("filesystem.read")[0] is False
    assert registry.get("filesystem.read", "1.0.0").lifecycle_state == LifecycleState.REVOKED  # type: ignore[union-attr]


def test_revoke_persists_before_publishing_registry_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    from kater.capabilities.store import (
        clear_capability_state,
        get_capability,
        upsert_capability,
    )

    registry = CapabilityRegistry()
    manifests = load_computer_manifests(VENDORED_CONTRACT)
    for manifest in manifests:
        upsert_capability(manifest)
        registry.register(manifest)
    revoke_computer_capability(registry, "filesystem.read", "1.0.0")
    assert get_capability("filesystem.read", "1.0.0").lifecycle_state == LifecycleState.REVOKED  # type: ignore[union-attr]
    clear_capability_state()


def test_canonical_invocation_request_and_denial_envelope() -> None:
    request = build_invocation_request(
        capability_id="filesystem.read",
        computer_session_id="csess_" + "a" * 32,
        machine_id="mach_" + "b" * 32,
        workspace_id="ws_" + "c" * 32,
        workspace_generation=1,
        arguments={"path": "README.md"},
        request_id="req_" + "d" * 32,
        deadline_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        idempotency_key="idem_" + "e" * 32,
    )
    result = make_invocation_result(request, status="denied", error_code="capability_denied")

    validate_invocation_envelope(result)
    assert result["status"] == "denied"
    assert result["error"]["code"] == "capability_denied"
    assert result["request_id"] == request["request_id"]


def test_invocation_request_requires_contract_metadata() -> None:
    with pytest.raises(ValueError, match="deadline_at"):
        build_invocation_request(
            capability_id="filesystem.read",
            computer_session_id="csess_" + "a" * 32,
            machine_id="mach_" + "b" * 32,
            workspace_id="ws_" + "c" * 32,
            workspace_generation=1,
            arguments={},
        )


def test_connector_requires_active_core_medium_source() -> None:
    manifests = load_computer_manifests(VENDORED_CONTRACT)
    source = computer_tool_source()
    connector = ComputerConnector(manifests, CapabilityRegistry(), source=source)
    assert connector.source_allowed(profile="core", max_risk=source.risk)
    assert not connector.source_allowed(profile="research", max_risk=source.risk)


def test_proxy_connector_hides_revoked_capability_without_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = CapabilityRegistry()
    manifests = load_computer_manifests(VENDORED_CONTRACT)
    for manifest in manifests:
        registry.register(manifest)
    from kater.proxy.manager import ProxyManager

    manager = ProxyManager()
    manager.register_computer_connector(ComputerConnector(manifests, registry))
    upsert_route_candidate(
        "filesystem.read",
        ProviderAccount(
            account_id="collision",
            provider="fallback",
            backend="fallback",
            tool_name="read",
            scopes=frozenset(),
        ),
    )
    manager.register_backend(
        "fallback",
        MockBackend(
            tools=[{"name": "read", "inputSchema": {"type": "object"}}],
            responses={"read": {"unexpected": True}},
        ),
    )
    assert "filesystem.read" in {item["name"] for item in manager.list_tools()}
    registry.revoke("filesystem.read", "1.0.0")
    assert "filesystem.read" not in {item["name"] for item in manager.list_tools()}
    denied = manager.call_tool("filesystem.read", {})
    assert denied["status"] == "denied"
    assert denied["error"]["code"] == "capability_denied"
