from __future__ import annotations

import pytest

from kater.browser.models import (
    MAX_ACTION_TIMEOUT_MS,
    NAVIGATING_KINDS,
    SESSION_ID_PREFIX,
    ActionKind,
    ActionResult,
    BrowserAction,
    BrowserSession,
    ProviderKind,
    SessionState,
    is_session_id,
    new_session_id,
)


def test_new_session_id_shape():
    session_id = new_session_id()
    assert session_id.startswith(SESSION_ID_PREFIX)
    assert len(session_id) == len(SESSION_ID_PREFIX) + 32
    assert is_session_id(session_id)
    assert new_session_id() != session_id


@pytest.mark.parametrize(
    "value",
    ["", "bsess_", "bsess_zz", "sess_" + "a" * 32, "bsess_" + "A" * 32, "bsess_" + "a" * 31],
)
def test_is_session_id_rejects_bad_shapes(value):
    assert not is_session_id(value)


def test_session_to_dict_and_expiry():
    session = BrowserSession(
        session_id=new_session_id(),
        provider=ProviderKind.LOCAL,
        state=SessionState.READY,
        created_at=100.0,
        last_used_at=100.0,
        expires_at=200.0,
        label="scratch",
    )
    payload = session.to_dict()
    assert payload["provider"] == "local"
    assert payload["state"] == "ready"
    assert payload["viewport"] == {"width": 1280, "height": 800}
    assert not session.is_expired(199.0)
    assert session.is_expired(200.0)
    assert not session.with_state(SessionState.CLOSED, expires_at=0.0).is_expired(1e9)


def test_session_with_state_is_immutable_update():
    session = BrowserSession(
        session_id=new_session_id(),
        provider=ProviderKind.LOCAL,
        state=SessionState.PENDING,
        created_at=1.0,
        last_used_at=1.0,
        expires_at=2.0,
    )
    updated = session.with_state(SessionState.READY, title="Docs")
    assert session.state is SessionState.PENDING
    assert updated.state is SessionState.READY
    assert updated.title == "Docs"
    assert updated.session_id == session.session_id


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "navigate", "url": "https://example.com"},
        {"kind": "click", "selector": "#go"},
        {"kind": "type", "selector": "#q", "text": "kater"},
        {"kind": "press", "key": "Enter"},
        {"kind": "select", "selector": "#s", "value": "one"},
        {"kind": "evaluate", "expression": "1 + 1"},
        {"kind": "wait", "timeout_ms": 250},
        {"kind": "wait", "selector": "#ready"},
        {"kind": "screenshot", "full_page": True},
        {"kind": "snapshot"},
        {"kind": "extract_text"},
        {"kind": "scroll", "delta_y": 400},
        {"kind": "back"},
        {"kind": "forward"},
        {"kind": "reload"},
    ],
)
def test_action_from_dict_accepts_valid_payloads(payload):
    action = BrowserAction.from_dict(payload)
    assert action.kind is ActionKind(payload["kind"])


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "requires a 'kind'"),
        ({"kind": "teleport"}, "unknown action kind"),
        ({"kind": "navigate"}, "requires 'url'"),
        ({"kind": "navigate", "url": "   "}, "requires 'url'"),
        ({"kind": "click"}, "requires 'selector'"),
        ({"kind": "type", "selector": "#q"}, "requires 'text'"),
        ({"kind": "press"}, "requires 'key'"),
        ({"kind": "evaluate"}, "requires 'expression'"),
        ({"kind": "select", "selector": "#s"}, "requires 'value'"),
        ({"kind": "wait"}, "requires 'selector' or 'timeout_ms'"),
        ({"kind": "navigate", "url": "https://a.test", "nope": 1}, "unknown action field"),
        ({"kind": "click", "selector": 42}, "must be a string"),
        ({"kind": "click", "selector": "#a", "timeout_ms": "soon"}, "must be a number"),
        ({"kind": "click", "selector": "#a", "timeout_ms": 0}, "must be >= 1"),
    ],
)
def test_action_from_dict_rejects_bad_payloads(payload, message):
    with pytest.raises(ValueError, match=message):
        BrowserAction.from_dict(payload)


def test_action_from_dict_accepts_enum_kind_and_round_trips():
    action = BrowserAction.from_dict({"kind": ActionKind.NAVIGATE, "url": " https://a.test "})
    assert action.url == "https://a.test"
    assert action.to_dict() == {"kind": "navigate", "url": "https://a.test"}


def test_action_to_dict_keeps_full_page_flag_only_when_set():
    assert BrowserAction(kind=ActionKind.SCREENSHOT).to_dict() == {"kind": "screenshot"}
    assert BrowserAction(kind=ActionKind.SCREENSHOT, full_page=True).to_dict() == {
        "kind": "screenshot",
        "full_page": True,
    }


def test_action_result_to_dict_omits_none_values():
    result = ActionResult(
        ok=True,
        kind=ActionKind.SNAPSHOT,
        session_id="bsess_" + "a" * 32,
        started_at=1.0,
        duration_ms=12.5,
        snapshot=({"tag": "button", "selector": "#go"},),
    )
    payload = result.to_dict()
    assert payload == {
        "ok": True,
        "kind": "snapshot",
        "session_id": "bsess_" + "a" * 32,
        "started_at": 1.0,
        "duration_ms": 12.5,
        "snapshot": [{"tag": "button", "selector": "#go"}],
    }
    assert "error" not in payload
    assert "screenshot_b64" not in payload


def test_action_result_reports_errors():
    result = ActionResult(
        ok=False,
        kind=ActionKind.NAVIGATE,
        session_id="bsess_" + "b" * 32,
        started_at=0.0,
        duration_ms=1.0,
        error="policy: blocked",
    )
    payload = result.to_dict()
    assert payload["ok"] is False
    assert payload["error"] == "policy: blocked"
    assert "title" not in payload


def test_action_from_dict_clamps_timeout_ms_to_hard_max():
    action = BrowserAction.from_dict(
        {"kind": "wait", "timeout_ms": MAX_ACTION_TIMEOUT_MS * 10}
    )
    assert action.timeout_ms == MAX_ACTION_TIMEOUT_MS


def test_evaluate_is_a_navigating_kind():
    assert ActionKind.EVALUATE in NAVIGATING_KINDS
