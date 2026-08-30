from __future__ import annotations

from unittest.mock import patch

import pytest

from kater.capabilities.audit import clear_capability_audit, query_capability_audit, reset_cache
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    PermissionLevel,
)
from kater.connectors.store import clear_connector_state, upsert_connector
from kater.executor import execute, search_tools


@pytest.fixture(autouse=True)
def catalog(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PROFILE", raising=False)
    (tmp_path / ".kater").mkdir()
    reset_cache()
    clear_connector_state()
    clear_capability_audit()
    yield
    clear_connector_state()
    reset_cache()


def _record(connector_id: str, *, permission: PermissionLevel = PermissionLevel.WRITE):
    return ConnectorRecord(
        id=connector_id,
        display_name=connector_id.title(),
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(
            ConnectorCapability(
                id=f"{connector_id}.issues.create",
                description=f"Create an issue in {connector_id}",
                mutation=True,
                input_schema={"type": "object"},
            ),
            ConnectorCapability(
                id=f"{connector_id}.issues.read",
                description=f"Read issues from {connector_id}",
            ),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops"}),
        permissions={"ops": permission},
        status=ConnectorStatus.ENABLED,
        origin="dynamic",
    )


def test_search_tools_ranks_intent_and_hides_unavailable():
    upsert_connector(_record("linear"))
    upsert_connector(_record("other", permission=PermissionLevel.READ))
    result = search_tools("create linear issue", profile="ops")
    assert result["tools"][0]["capability_id"] == "linear.issues.create"
    assert all(item["available"] for item in result["tools"])
    assert "other.issues.create" not in {item["capability_id"] for item in result["tools"]}


def test_search_tools_can_explain_unavailable_matches():
    upsert_connector(_record("linear", permission=PermissionLevel.READ))
    result = search_tools("linear create", profile="ops", include_unavailable=True)
    tool = next(item for item in result["tools"] if item["capability_id"] == "linear.issues.create")
    assert tool["available"] is False
    assert tool["required_permission"] == "write"
    assert tool["granted_permission"] == "read"


def test_execute_resolves_connector_and_audits_success():
    upsert_connector(_record("linear"))
    with patch("kater.connectors.internal.invoke", return_value={"id": "LIN-1"}) as mocked:
        result = execute(
            "linear.issues.create",
            {"title": "Bug"},
            profile="ops",
            principal_id="agent-1",
            context_id="ctx-1",
        )
    assert result["connector_id"] == "linear"
    assert result["result"] == {"id": "LIN-1"}
    mocked.assert_called_once()
    rows = query_capability_audit(capability_id="linear.issues.create")
    assert rows[0]["outcome"] == "allowed"
    assert rows[0]["principal_id"] == "agent-1"


def test_execute_denied_by_existing_permission_policy_and_audited():
    upsert_connector(_record("linear", permission=PermissionLevel.READ))
    with pytest.raises(Exception, match="needs write"):
        execute("linear.issues.create", {}, profile="ops")
    rows = query_capability_audit(capability_id="linear.issues.create")
    assert rows[0]["outcome"] == "denied"


def test_execute_requires_explicit_connector_when_capability_is_ambiguous():
    first = _record("first")
    second = ConnectorRecord.from_mapping(
        {
            **_record("second").as_dict(),
            "capabilities": [
                {
                    "id": "shared.read",
                    "description": "shared",
                    "mutation": False,
                }
            ],
        }
    )
    first = ConnectorRecord.from_mapping(
        {
            **first.as_dict(),
            "capabilities": [
                {
                    "id": "shared.read",
                    "description": "shared",
                    "mutation": False,
                }
            ],
        }
    )
    upsert_connector(first)
    upsert_connector(second)
    with pytest.raises(Exception, match="ambiguous"):
        execute("shared.read", {}, profile="ops")


def test_runtime_profile_boundary_blocks_unserved_profile(monkeypatch):
    monkeypatch.setenv("KATER_PROFILE", "research,web")
    upsert_connector(_record("linear"))
    with pytest.raises(Exception, match="not served"):
        search_tools("linear", profile="ops")


def test_audit_storage_failure_does_not_turn_successful_write_into_retry_signal():
    upsert_connector(_record("linear"))
    with (
        patch("kater.connectors.internal.invoke", return_value={"id": "LIN-2"}),
        patch("kater.executor.record_capability_audit", side_effect=OSError("disk full")),
    ):
        result = execute("linear.issues.create", {"title": "Bug"}, profile="ops")
    assert result["result"] == {"id": "LIN-2"}
    assert result["audit_id"] is None
    assert result["audit_recorded"] is False
