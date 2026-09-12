from __future__ import annotations

import inspect
import json
import time

import pytest
from typer.testing import CliRunner

from kater.capabilities.audit import (
    clear_capability_audit,
    query_capability_audit,
    reset_cache,
)
from kater.cli import app
from kater.connections import (
    ConnectionView,
    get_connection_view,
    integration_manifest,
    list_connection_views,
)
from kater.connectors.errors import ConnectorPolicyError, ConnectorUnavailableError
from kater.connectors.internal import register_internal_handler, unregister_internal_handler
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
from kater.execution import ActorIdentity, PolicyContext, reset_idempotency_cache
from kater.executor import execute
from kater.fabric_catalog import CatalogKind, catalog_payload
from kater.plugins import PluginManifest
from kater.registry import execute_tool, pr_list_tool, pr_merge_tool
from kater.toolkits import GITHUB_TOOLKIT
from tests._rest import call

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PROFILE", raising=False)
    monkeypatch.setenv("KATER_ADMIN_KEY", "admin-secret")
    (tmp_path / ".kater").mkdir()
    reset_cache()
    reset_idempotency_cache()
    clear_connector_state()
    clear_capability_audit()
    unregister_internal_handler("demoexec")
    yield
    unregister_internal_handler("demoexec")
    clear_connector_state()
    reset_cache()
    reset_idempotency_cache()


def _internal(connector_id: str = "demoexec", *, permission: PermissionLevel = PermissionLevel.WRITE):
    return ConnectorRecord(
        id=connector_id,
        display_name=connector_id.title(),
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(
            ConnectorCapability(
                id=f"{connector_id}.items.create",
                description="Create item",
                mutation=True,
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}},
                },
            ),
            ConnectorCapability(id=f"{connector_id}.items.read", description="Read item"),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"ops", "core"}),
        permissions={"ops": permission, "core": permission},
        status=ConnectorStatus.ENABLED,
        origin="dynamic",
    )


def test_plugin_manifest_and_connection_view_are_secret_free():
    manifest = PluginManifest.from_mapping(
        {"id": "kater-core", "name": "Kater Core", "toolkits": ["github"], "version": "1.1.1"}
    )
    assert manifest.as_dict()["toolkits"] == ["github"]
    view = ConnectionView(
        id="github:default",
        toolkit="github",
        integration="github",
        label="default",
        origin="env",
        auth_kind="env",
        configured=False,
        status="auth_missing",
        secret_names=("GITHUB_PERSONAL_ACCESS_TOKEN",),
    )
    dumped = json.dumps(view.as_dict())
    assert "ghp_" not in dumped
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in dumped


def test_canonical_execute_validates_schema_and_records_identity():
    upsert_connector(_internal())
    register_internal_handler("demoexec", lambda _record, _cap, args: {"created": args["name"]})
    result = execute(
        connection="demoexec:default",
        action="demoexec.items.create",
        input={"name": "ticket"},
        identity=ActorIdentity(actor_id="agent-9", kind="agent", agent_id="runner-1"),
        policy_context=PolicyContext(profile="ops", run_id="run-1", trace_id="trace-1"),
    )
    assert result["ok"] is True
    assert result["connection_id"] == "demoexec:default"
    assert result["action"] == "demoexec.items.create"
    assert result["result"] == {"created": "ticket"}
    assert result["identity"]["actor_id"] == "agent-9"
    assert result["run_id"] == "run-1"
    assert result["trace_id"] == "trace-1"
    rows = query_capability_audit(capability_id="demoexec.items.create")
    assert rows[0]["actor_id"] == "agent-9"
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["connection_id"] == "demoexec:default"


def test_schema_validation_rejects_bad_input():
    upsert_connector(_internal())
    register_internal_handler("demoexec", lambda *_args: {"ok": True})
    with pytest.raises(Exception, match="schema validation"):
        execute(
            connection="demoexec:default",
            action="demoexec.items.create",
            input={"nope": True},
            identity=ActorIdentity(actor_id="agent-9"),
            policy_context=PolicyContext(profile="ops"),
        )


def test_idempotency_replays_same_key():
    upsert_connector(_internal())
    calls = {"n": 0}

    def handler(_record, _cap, args):
        calls["n"] += 1
        return {"created": args["name"], "n": calls["n"]}

    register_internal_handler("demoexec", handler)
    first = execute(
        connection="demoexec:default",
        action="demoexec.items.create",
        input={"name": "same"},
        identity=ActorIdentity(actor_id="agent-9"),
        policy_context=PolicyContext(profile="ops", idempotency_key="idem-1"),
    )
    second = execute(
        connection="demoexec:default",
        action="demoexec.items.create",
        input={"name": "same"},
        identity=ActorIdentity(actor_id="agent-9"),
        policy_context=PolicyContext(profile="ops", idempotency_key="idem-1"),
    )
    assert first["result"]["n"] == 1
    assert second["idempotency_replay"] is True
    assert second["result"]["n"] == 1


def test_github_pr_wrappers_use_execute(monkeypatch):
    from kater.connectors.seed import seed_builtin_connectors

    seed_builtin_connectors()
    monkeypatch.setattr(
        "kater.pr_control.pr_list_tool",
        lambda **kwargs: {"count": 1, "pulls": [{"number": 7}], "echo": kwargs},
    )
    listed = pr_list_tool(state="open", limit=5, repo="acme/app")
    assert listed["count"] == 1
    rows = query_capability_audit(capability_id="github.pr.list")
    assert rows[0]["connection_id"] == "github:default"
    assert rows[0]["actor_id"] == "mcp"


def test_github_merge_requires_expected_head_sha():
    from kater.connectors.seed import seed_builtin_connectors

    seed_builtin_connectors()
    with pytest.raises(ConnectorPolicyError, match="expected_head_sha"):
        pr_merge_tool(1, expected_head_sha="", actor="reviewer")


def test_rest_connections_and_canonical_execute():
    upsert_connector(_internal())
    register_internal_handler("demoexec", lambda _record, _cap, args: {"created": args["name"]})
    listed = call("GET", "/api/connections")
    assert listed.status == 200
    assert listed.payload is not None
    assert listed.payload["counts"]["connection"] >= 1
    detail = call("GET", "/api/connections/demoexec:default")
    assert detail.status == 200
    assert detail.payload is not None
    assert detail.payload["id"] == "demoexec:default"
    assert "env" not in detail.payload
    denied = call(
        "POST",
        "/api/execute",
        body={
            "connection": "demoexec:default",
            "action": "demoexec.items.create",
            "input": {"name": "via-api"},
            "identity": {"actor_id": "api-agent"},
            "policy_context": {"profile": "ops"},
        },
    )
    assert denied.status == 403
    allowed = call(
        "POST",
        "/api/execute",
        body={
            "connection": "demoexec:default",
            "action": "demoexec.items.create",
            "input": {"name": "via-api"},
            "identity": {"actor_id": "api-agent"},
            "policy_context": {"profile": "ops", "run_id": "r-api"},
        },
        headers={"authorization": "Bearer admin-secret"},
    )
    assert allowed.status == 200
    assert allowed.payload is not None
    assert allowed.payload["result"] == {"created": "via-api"}
    assert allowed.payload["run_id"] == "r-api"


def test_cli_canonical_execute():
    upsert_connector(_internal())
    register_internal_handler("demoexec", lambda _record, _cap, args: {"echo": args})
    executed = runner.invoke(
        app,
        [
            "execute",
            "--connection",
            "demoexec:default",
            "--action",
            "demoexec.items.create",
            "--profile",
            "ops",
            "--actor",
            "cli-user",
            "--args",
            '{"name":"hello"}',
        ],
    )
    assert executed.exit_code == 0, executed.output
    payload = json.loads(executed.stdout)
    assert payload["result"] == {"echo": {"name": "hello"}}
    assert payload["identity"]["actor_id"] == "cli-user"


def test_list_connection_views_includes_github_default():
    from kater.connectors.seed import seed_builtin_connectors

    seed_builtin_connectors()
    ids = {view.id for view in list_connection_views()}
    assert "github:default" in ids
    assert get_connection_view("github:default") is not None
    manifest = integration_manifest("github")
    assert manifest is not None
    assert "github:default" in manifest.connections
    assert "github.pr.merge" in manifest.actions
    dumped = json.dumps(manifest.as_dict())
    assert "ghp_" not in dumped
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" not in dumped


def test_github_actions_are_in_catalog_and_mcp_execute_surface():
    payload = catalog_payload(kind=CatalogKind.ACTION)
    names = {item["name"] for item in payload["actions"]}
    assert set(GITHUB_TOOLKIT.actions) <= names
    toolkits = catalog_payload(kind=CatalogKind.TOOLKIT)
    github = next(item for item in toolkits["toolkits"] if item["name"] == "github")
    assert "github.pr.merge" in github["capabilities"]
    params = inspect.signature(execute_tool).parameters
    assert {"connection", "action", "input", "actor_id", "run_id", "idempotency_key"} <= set(
        params
    )
    listed = call("GET", "/api/actions")
    assert listed.status == 200
    assert listed.payload is not None
    assert "github.pr.merge" in {item["name"] for item in listed.payload["actions"]}


def test_retries_then_succeeds():
    upsert_connector(_internal())
    calls = {"n": 0}

    def handler(_record, _cap, args):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectorUnavailableError("flaky", connector_id="demoexec")
        return {"created": args["name"], "n": calls["n"]}

    register_internal_handler("demoexec", handler)
    result = execute(
        connection="demoexec:default",
        action="demoexec.items.create",
        input={"name": "retry"},
        identity=ActorIdentity(actor_id="agent-9"),
        policy_context=PolicyContext(profile="ops", max_retries=3),
    )
    assert result["ok"] is True
    assert result["attempts"] == 3
    assert result["result"]["n"] == 3


def test_timeout_is_structured_and_audited():
    upsert_connector(_internal())

    def sleepy(*_args):
        time.sleep(1.5)
        return {"created": "late"}

    register_internal_handler("demoexec", sleepy)
    with pytest.raises(Exception, match="timed out"):
        execute(
            connection="demoexec:default",
            action="demoexec.items.create",
            input={"name": "slow"},
            identity=ActorIdentity(actor_id="agent-9"),
            policy_context=PolicyContext(profile="ops", timeout_seconds=0.2),
        )
    rows = query_capability_audit(capability_id="demoexec.items.create")
    assert rows[0]["outcome"] == "error"
    assert rows[0]["error_code"] == "timeout"


def test_idempotency_conflict_and_dangerous_policy():
    upsert_connector(_internal())
    register_internal_handler("demoexec", lambda _record, _cap, args: {"created": args["name"]})
    execute(
        connection="demoexec:default",
        action="demoexec.items.create",
        input={"name": "a"},
        identity=ActorIdentity(actor_id="agent-9"),
        policy_context=PolicyContext(profile="ops", idempotency_key="idem-2"),
    )
    with pytest.raises(Exception, match="idempotency"):
        execute(
            connection="demoexec:default",
            action="demoexec.items.create",
            input={"name": "b"},
            identity=ActorIdentity(actor_id="agent-9"),
            policy_context=PolicyContext(profile="ops", idempotency_key="idem-2"),
        )
    from kater.connectors.seed import seed_builtin_connectors

    seed_builtin_connectors()
    with pytest.raises(ConnectorPolicyError, match="non-anonymous"):
        execute(
            connection="github:default",
            action="github.pr.merge",
            input={"number": 1, "expected_head_sha": "abc123"},
        )
    with pytest.raises(ConnectorPolicyError, match="not allowed"):
        execute(
            connection="github:default",
            action="github.pr.merge",
            input={"number": 1, "expected_head_sha": "abc123"},
            identity=ActorIdentity(actor_id="reviewer"),
            policy_context=PolicyContext(profile="core", allow_dangerous=False),
        )
