"""Authoritative agent-session work/event transport: REST, MCP, auth, OpenAPI."""

from __future__ import annotations

import json

import pytest

from kater.api.session_routes import SESSION_CAPABILITIES, SESSION_OPENAPI_PATHS
from kater.authgate import RequestIdentity, set_request_identity
from kater.capabilities import audit as capability_audit
from kater.control_plane import contexts
from kater.control_plane import session_transport as transport
from kater.control_plane import tokens as context_tokens
from kater.control_plane.models import AgentState
from kater.openapi_spec import generate_spec
from kater.registry import build_native_tools
from kater.session_tools import (
    kater_session_append,
    kater_session_cancel,
    kater_session_continue,
    kater_session_events,
    kater_session_submit,
)
from tests._rest import call


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-session-secret")
    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    transport.reset_cache()
    capability_audit.reset_cache()
    yield tmp_path
    capability_audit.reset_cache()
    transport.reset_cache()
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


def _create_context(**kwargs):
    body = {"principal_id": "agent-session", **kwargs}
    created = call("POST", "/api/contexts", body=body)
    assert created.status == 201
    assert created.payload is not None
    return created.payload["context_id"]


def _token(context_id: str, headers: bool = True) -> dict[str, str]:
    issued = call("POST", f"/api/contexts/{context_id}/token", body={"ttl_seconds": 600})
    assert issued.status == 200
    assert issued.payload is not None
    token = issued.payload["token"]
    return {"X-Kater-Context": token} if headers else {"Authorization": f"Bearer {token}"}


def test_session_routes_are_registered() -> None:
    from kater.api import ROUTER

    for method, path in [
        ("GET", "/api/contexts/rctx_x/session"),
        ("POST", "/api/contexts/rctx_x/session/continue"),
        ("GET", "/api/contexts/rctx_x/session/work"),
        ("POST", "/api/contexts/rctx_x/session/work"),
        ("GET", "/api/contexts/rctx_x/session/work/awrk_x"),
        ("POST", "/api/contexts/rctx_x/session/work/awrk_x/cancel"),
        ("POST", "/api/contexts/rctx_x/session/work/awrk_x/transition"),
        ("GET", "/api/contexts/rctx_x/session/events"),
        ("POST", "/api/contexts/rctx_x/session/events"),
        ("GET", "/api/contexts/rctx_x/session/events/stream"),
    ]:
        assert ROUTER.match(method, path) is not None, f"{method} {path}"


def test_openapi_includes_session_transport_paths() -> None:
    spec = generate_spec()
    for path in SESSION_OPENAPI_PATHS:
        assert path in spec["paths"], path
    from kater.api import ROUTER

    for route in ROUTER._routes:
        if "/session" in route.pattern:
            assert route.pattern in spec["paths"]


def test_builtins_and_mcp_tools_expose_session_capabilities(ctx_db) -> None:
    from kater.capabilities.registry import get_default_registry, reset_default_registry

    reset_default_registry()
    ids = {item.capability_id for item in get_default_registry().list()}
    assert set(SESSION_CAPABILITIES) <= ids
    names = {tool.name for tool in build_native_tools()}
    assert {
        "kater_session_continue",
        "kater_session_submit",
        "kater_session_events",
        "kater_session_cancel",
        "kater_session_append",
    } <= names
    reset_default_registry()


def test_submit_continue_poll_stream_cancel_and_correlation(ctx_db) -> None:
    context_id = _create_context()
    continued = call("POST", f"/api/contexts/{context_id}/session/continue")
    assert continued.status == 200
    assert continued.payload is not None
    assert continued.payload["correlation"]["katerContextId"] == context_id
    assert continued.payload["agent_state"] == AgentState.IDLE.value

    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "summarize the open PRs", "correlation": {"katerContextId": context_id}},
    )
    assert submitted.status == 201
    assert submitted.payload is not None
    work = submitted.payload["work"]
    assert work["state"] == AgentState.WAITING.value
    assert work["correlation"]["katerContextId"] == context_id
    assert submitted.payload["events"][0]["type"] == "work.submitted"
    assert submitted.payload["events"][1]["type"] == "work.state"
    work_id = work["work_id"]

    polled = call("GET", f"/api/contexts/{context_id}/session/events")
    assert polled.status == 200
    assert polled.payload is not None
    types = [event["type"] for event in polled.payload["events"]]
    assert "session.continued" in types
    assert "work.submitted" in types
    assert polled.payload["katerContextId"] == context_id
    next_seq = polled.payload["next_seq"]

    streamed = call(
        "GET",
        f"/api/contexts/{context_id}/session/events/stream",
        query={"after_seq": ["0"]},
    )
    assert streamed.status == 200
    assert streamed.content_type.startswith("text/event-stream")
    body = streamed.encoded().decode()
    assert "event: work.submitted" in body
    assert "katerContextId" in body

    json_stream = call(
        "GET",
        f"/api/contexts/{context_id}/session/events",
        query={"after_seq": [str(next_seq)], "stream": ["1"]},
    )
    assert json_stream.content_type.startswith("text/event-stream")

    cancelled = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/cancel",
        body={"reason": "operator"},
    )
    assert cancelled.status == 200
    assert cancelled.payload is not None
    assert cancelled.payload["work"]["state"] == AgentState.CANCELLED.value
    assert cancelled.payload["event"]["type"] == "work.cancelled"


def test_mismatched_kater_context_id_is_rejected(ctx_db) -> None:
    context_id = _create_context()
    resp = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "hello", "correlation": {"katerContextId": "rctx_other"}},
    )
    assert resp.status == 400
    assert resp.payload is not None
    assert "katerContextId" in resp.payload["error"]


def test_empty_prompt_rejected(ctx_db) -> None:
    context_id = _create_context()
    resp = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "   "},
    )
    assert resp.status == 400


def test_unknown_event_stays_kater_neutral(ctx_db) -> None:
    context_id = _create_context()
    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "work"},
    )
    work_id = submitted.payload["work"]["work_id"]  # type: ignore[index]
    appended = call(
        "POST",
        f"/api/contexts/{context_id}/session/events",
        body={
            "type": "anthropic.tool_use",
            "work_id": work_id,
            "payload": {"hint": "looks like a vendor event"},
        },
    )
    assert appended.status == 201
    assert appended.payload is not None
    event = appended.payload["event"]
    assert event["type"] == "event.unknown"
    assert event["provider"] is None
    assert event["payload"]["original_type"] == "anthropic.tool_use"

    explicit = call(
        "POST",
        f"/api/contexts/{context_id}/session/events",
        body={"type": "work.progress", "work_id": work_id, "provider": "anthropic"},
    )
    assert explicit.status == 201
    assert explicit.payload is not None
    assert explicit.payload["event"]["provider"] == "anthropic"
    assert explicit.payload["event"]["type"] == "work.progress"


def test_transition_uses_existing_agent_state_machine(ctx_db) -> None:
    context_id = _create_context()
    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "run"},
    )
    work_id = submitted.payload["work"]["work_id"]  # type: ignore[index]
    working = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/transition",
        body={"state": "working", "reason": "runtime-claimed"},
    )
    assert working.status == 200
    illegal = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/transition",
        body={"state": "idle"},
    )
    assert illegal.status == 409
    completed = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/transition",
        body={"state": "completed"},
    )
    assert completed.status == 200
    again = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/cancel",
        body={},
    )
    assert again.status == 409


def test_scoped_token_cannot_touch_foreign_session(ctx_db) -> None:
    own = _create_context(principal_id="agent-a", allowed_capabilities=["kater.session"])
    other = _create_context(principal_id="agent-b")
    headers = _token(own)
    missing = call("GET", f"/api/contexts/{other}/session", headers=headers)
    assert missing.status == 404
    submit = call(
        "POST",
        f"/api/contexts/{other}/session/work",
        body={"prompt": "nope"},
        headers=headers,
    )
    assert submit.status == 404
    poll = call("GET", f"/api/contexts/{other}/session/events", headers=headers)
    assert poll.status == 404


def test_capability_allowlist_denies_submit_and_records_audit(ctx_db) -> None:
    context_id = _create_context(
        principal_id="agent-cap",
        allowed_capabilities=["kater.session.events.read", "kater.session.continue"],
    )
    headers = _token(context_id)
    readable = call("GET", f"/api/contexts/{context_id}/session", headers=headers)
    assert readable.status == 200
    denied = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "blocked"},
        headers=headers,
    )
    assert denied.status == 403
    assert denied.payload is not None
    assert "kater.session.work.submit" in denied.payload["error"]
    rows = capability_audit.query_capability_audit(
        capability_id="kater.session.work.submit", context_id=context_id
    )
    assert rows
    assert rows[0]["outcome"] == "denied"


def test_revoked_context_rejects_mutations_but_projection_is_404_owned(ctx_db) -> None:
    context_id = _create_context()
    call("POST", f"/api/contexts/{context_id}/revoke")
    cont = call("POST", f"/api/contexts/{context_id}/session/continue")
    assert cont.status == 409
    submit = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "late"},
    )
    assert submit.status == 409
    listed = call("GET", f"/api/contexts/{context_id}/session/events")
    assert listed.status == 200


def test_bearer_context_token_binds_session_mutations(ctx_db) -> None:
    context_id = _create_context(
        principal_id="agent-bearer",
        allowed_capabilities=["kater.session"],
    )
    headers = _token(context_id, headers=False)
    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "via bearer"},
        headers=headers,
    )
    assert submitted.status == 201


def test_wait_ms_poll_returns_empty_without_spinning(ctx_db) -> None:
    context_id = _create_context()
    polled = call(
        "GET",
        f"/api/contexts/{context_id}/session/events",
        query={"after_seq": ["0"], "wait_ms": ["20"]},
    )
    assert polled.status == 200
    assert polled.payload is not None
    assert polled.payload["events"] == []
    assert polled.payload["next_seq"] == 0


def test_mcp_tools_roundtrip_with_request_identity(ctx_db) -> None:
    record = contexts.create_context(principal_id="mcp-agent")
    set_request_identity(RequestIdentity(principal_id="mcp-agent", context_id=record.context_id))
    continued = kater_session_continue(record.context_id)
    assert continued["ok"] is True
    submitted = kater_session_submit(record.context_id, "from mcp")
    assert submitted["ok"] is True
    work_id = submitted["work"]["work_id"]
    events = kater_session_events(record.context_id)
    assert events["ok"] is True
    assert events["total"] >= 2
    appended = kater_session_append(
        record.context_id,
        "vendor.mystery",
        work_id=work_id,
        payload_json=json.dumps({"x": 1}),
    )
    assert appended["ok"] is True
    assert appended["event"]["type"] == "event.unknown"
    assert appended["event"]["provider"] is None
    cancelled = kater_session_cancel(record.context_id, work_id)
    assert cancelled["ok"] is True
    set_request_identity(None)


def test_mcp_tool_does_not_leak_foreign_context(ctx_db) -> None:
    own = contexts.create_context(
        principal_id="mcp-own",
        allowed_capabilities=["kater.session"],
    )
    other = contexts.create_context(principal_id="mcp-other")
    set_request_identity(
        RequestIdentity(
            principal_id="mcp-own",
            context_id=own.context_id,
            allowed_capabilities=frozenset({"kater.session"}),
        )
    )
    result = kater_session_submit(other.context_id, "steal")
    assert result["ok"] is False
    assert result["status"] == 404
    set_request_identity(None)


def test_append_event_can_transition_work_state(ctx_db) -> None:
    context_id = _create_context()
    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "go"},
    )
    work_id = submitted.payload["work"]["work_id"]  # type: ignore[index]
    appended = call(
        "POST",
        f"/api/contexts/{context_id}/session/events",
        body={"type": "work.state", "work_id": work_id, "payload": {"state": "working"}},
    )
    assert appended.status == 201
    assert appended.payload is not None
    assert appended.payload["work"]["state"] == "working"


def test_missing_context_is_404(ctx_db) -> None:
    missing = "rctx_" + ("b" * 32)
    assert call("GET", f"/api/contexts/{missing}/session").status == 404
    assert call("POST", f"/api/contexts/{missing}/session/continue").status == 404


def test_list_and_get_work_are_context_scoped(ctx_db) -> None:
    context_id = _create_context()
    other = _create_context(principal_id="other-work")
    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "scoped"},
    )
    work_id = submitted.payload["work"]["work_id"]  # type: ignore[index]
    listed = call("GET", f"/api/contexts/{context_id}/session/work")
    assert listed.status == 200
    assert listed.payload is not None
    assert listed.payload["total"] == 1
    assert listed.payload["work"][0]["work_id"] == work_id
    got = call("GET", f"/api/contexts/{context_id}/session/work/{work_id}")
    assert got.status == 200
    assert got.payload is not None
    assert got.payload["prompt"] == "scoped"
    foreign = call("GET", f"/api/contexts/{other}/session/work/{work_id}")
    assert foreign.status == 404


def test_accept_event_stream_polls_as_sse(ctx_db) -> None:
    context_id = _create_context()
    call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "sse"},
    )
    streamed = call(
        "GET",
        f"/api/contexts/{context_id}/session/events",
        headers={"Accept": "text/event-stream"},
    )
    assert streamed.status == 200
    assert streamed.content_type.startswith("text/event-stream")
    assert b"event: work.submitted" in streamed.encoded()


def test_capability_allowlist_denies_continue_cancel_transition_append(ctx_db) -> None:
    context_id = _create_context(
        principal_id="agent-narrow",
        allowed_capabilities=[
            "kater.session.events.read",
            "kater.session.work.submit",
        ],
    )
    headers = _token(context_id)
    submitted = call(
        "POST",
        f"/api/contexts/{context_id}/session/work",
        body={"prompt": "allowed submit"},
        headers=headers,
    )
    assert submitted.status == 201
    work_id = submitted.payload["work"]["work_id"]  # type: ignore[index]
    continue_denied = call(
        "POST",
        f"/api/contexts/{context_id}/session/continue",
        headers=headers,
    )
    assert continue_denied.status == 403
    cancel_denied = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/cancel",
        body={"reason": "nope"},
        headers=headers,
    )
    assert cancel_denied.status == 403
    transition_denied = call(
        "POST",
        f"/api/contexts/{context_id}/session/work/{work_id}/transition",
        body={"state": "working"},
        headers=headers,
    )
    assert transition_denied.status == 403
    append_denied = call(
        "POST",
        f"/api/contexts/{context_id}/session/events",
        body={"type": "work.progress"},
        headers=headers,
    )
    assert append_denied.status == 403
    rows = capability_audit.query_capability_audit(
        capability_id="kater.session.work.cancel", context_id=context_id
    )
    assert rows
    assert rows[0]["outcome"] == "denied"

