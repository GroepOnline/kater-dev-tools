from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from kater.chains import ChainStep
from kater.connectors.chain_guard import (
    chain_step_refs,
    invoke_chain_capability,
    validate_chain_steps,
)
from kater.connectors.errors import (
    ConnectorCapabilityError,
    ConnectorPolicyError,
    ConnectorUnavailableError,
)
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


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()


def _github_record(*, permission: PermissionLevel = PermissionLevel.READ) -> ConnectorRecord:
    os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "gh_test"
    return ConnectorRecord(
        id="github",
        display_name="GitHub",
        type=ConnectorType.MCP,
        version="1.0.0",
        transport=ConnectorTransport(kind="stdio", command="echo", args=("gh",)),
        capabilities=(
            ConnectorCapability(id="github.pull_requests.read", description="PR read"),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.ENV, ref="GITHUB_PERSONAL_ACCESS_TOKEN"),
        profiles=frozenset({"ops"}),
        permissions={"ops": permission},
        status=ConnectorStatus.ENABLED,
    )


def test_chain_validation_succeeds_when_healthy_and_permitted():
    upsert_connector(_github_record(permission=PermissionLevel.READ))
    steps = [ChainStep(tool="github_pr_status", reason="check pr")]

    validate_chain_steps(steps, profile="ops")
    assert chain_step_refs(steps[0]) == ("github", "github.pull_requests.read")


def test_chain_blocked_by_missing_capability():
    record = _github_record()
    record = ConnectorRecord.from_mapping({**record.as_dict(), "capabilities": []})
    upsert_connector(record)
    steps = [ChainStep(tool="github_pr_status", reason="check pr")]

    with pytest.raises(ConnectorCapabilityError):
        validate_chain_steps(steps, profile="ops")


def test_chain_blocked_by_policy():
    record = _github_record(permission=PermissionLevel.DISABLED)
    upsert_connector(record)
    steps = [ChainStep(tool="github.pull_requests.read", reason="check pr")]

    with pytest.raises(ConnectorPolicyError):
        validate_chain_steps(steps, profile="ops")


def test_chain_blocked_when_connector_disabled():
    record = _github_record()
    record = ConnectorRecord.from_mapping(
        {**record.as_dict(), "status": ConnectorStatus.DISABLED.value}
    )
    upsert_connector(record)
    steps = [ChainStep(tool="github_pr_status", reason="check pr")]

    with pytest.raises(ConnectorUnavailableError):
        validate_chain_steps(steps, profile="ops")


def test_unmapped_recipe_steps_are_not_gated():
    steps = [
        ChainStep(tool="firecrawl_search", reason="find"),
        ChainStep(tool="kater_summary", reason="summarize"),
    ]
    validate_chain_steps(steps, profile="research")


def test_invoke_chain_capability_delegates_to_registry():
    upsert_connector(_github_record(permission=PermissionLevel.READ))

    with patch("kater.connectors.registry.invoke", return_value={"ok": True}) as mocked:
        result = invoke_chain_capability(
            "github",
            "github.pull_requests.read",
            {"owner": "o", "repo": "r"},
            profile="ops",
        )
    assert result == {"ok": True}
    mocked.assert_called_once()
