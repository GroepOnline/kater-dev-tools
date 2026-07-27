"""REST API coverage for the native browser lane."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kater.api import ROUTER
from kater.browser.models import (
    ActionKind,
    ActionResult,
    BrowserSession,
    ProviderKind,
    SessionState,
)
from kater.browser.providers import BrowserUnavailableError
from tests._rest import call

BROWSER_ROUTES = [
    ("GET", "/api/browser/providers"),
    ("GET", "/api/browser/sessions"),
    ("POST", "/api/browser/sessions"),
    ("GET", "/api/browser/sessions/bsess_deadbeefdeadbeefdeadbeefdeadbeef"),
    ("DELETE", "/api/browser/sessions/bsess_deadbeefdeadbeefdeadbeefdeadbeef"),
    ("POST", "/api/browser/sessions/bsess_deadbeefdeadbeefdeadbeefdeadbeef/act"),
    ("POST", "/api/browser/sessions/bsess_deadbeefdeadbeefdeadbeefdeadbeef/screenshot"),
    ("GET", "/api/browser/stats"),
    ("DELETE", "/api/browser/sessions"),
]


def _session(session_id: str = "bsess_deadbeefdeadbeefdeadbeefdeadbeef") -> BrowserSession:
    return BrowserSession(
        session_id=session_id,
        provider=ProviderKind.LOCAL,
        state=SessionState.READY,
        created_at=1.0,
        last_used_at=1.0,
        expires_at=100.0,
        label="lane",
        profile="core",
    )


def _result(session_id: str, kind: ActionKind = ActionKind.RELOAD) -> ActionResult:
    return ActionResult(
        ok=True,
        kind=kind,
        session_id=session_id,
        started_at=1.0,
        duration_ms=12.5,
        url="https://example.com",
        title="Example",
    )


def _fake_manager() -> MagicMock:
    session = _session()
    manager = MagicMock()
    manager.list_sessions.return_value = []
    manager.stats.return_value = {
        "sessions": 0,
        "live": 0,
        "by_state": {state.value: 0 for state in SessionState},
        "provider": "local",
        "provider_started": False,
        "provider_info": None,
        "total_actions": 0,
        "persisted_actions": 0,
        "max_sessions": 4,
        "last_error": None,
    }
    manager.create.return_value = session
    manager.get.return_value = session
    manager.close.return_value = session.with_state(SessionState.CLOSED)
    manager.close_all.return_value = 1
    manager.act.return_value = _result(session.session_id)
    manager.screenshot.return_value = _result(session.session_id, ActionKind.SCREENSHOT)
    return manager


@pytest.mark.parametrize("method,path", BROWSER_ROUTES)
def test_browser_routes_registered(method: str, path: str) -> None:
    assert ROUTER.match(method, path) is not None, f"{method} {path} missing from ROUTER"


def test_browser_providers_returns_list() -> None:
    resp = call("GET", "/api/browser/providers")
    assert resp.status == 200
    assert isinstance(resp.payload, dict)
    providers = resp.payload["providers"]
    assert isinstance(providers, list)
    assert providers
    assert {"kind", "available", "detail"} <= set(providers[0])


def test_browser_sessions_list_empty() -> None:
    manager = _fake_manager()
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call("GET", "/api/browser/sessions")
    assert resp.status == 200
    assert resp.payload == {
        "sessions": [],
        "stats": manager.stats.return_value,
    }
    manager.list_sessions.assert_called_once_with(live_only=False)


def test_browser_sessions_list_live_only() -> None:
    manager = _fake_manager()
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call(
            "GET",
            "/api/browser/sessions",
            query={"live_only": ["true"]},
        )
    assert resp.status == 200
    manager.list_sessions.assert_called_once_with(live_only=True)


def test_browser_create_session_ok() -> None:
    manager = _fake_manager()
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call(
            "POST",
            "/api/browser/sessions",
            body={"label": "lane", "profile": "ops", "width": 1024, "height": 768},
        )
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["session"]["session_id"].startswith("bsess_")
    manager.create.assert_called_once_with(
        label="lane",
        profile="ops",
        viewport=(1024, 768),
    )


def test_browser_create_session_unavailable() -> None:
    manager = _fake_manager()
    manager.create.side_effect = BrowserUnavailableError("playwright is not installed")
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call("POST", "/api/browser/sessions", body={})
    assert resp.status == 400
    assert resp.payload == {"error": "playwright is not installed"}


def test_browser_get_session_ok_and_404() -> None:
    manager = _fake_manager()
    sid = manager.get.return_value.session_id
    with patch("kater.api.routes.get_manager", return_value=manager):
        ok = call("GET", f"/api/browser/sessions/{sid}")
        manager.get.return_value = None
        missing = call("GET", "/api/browser/sessions/bsess_missingmissingmissingmissingmi")
    assert ok.status == 200
    assert ok.payload is not None
    assert ok.payload["session_id"] == sid
    assert missing.status == 404


def test_browser_close_session_and_close_all() -> None:
    manager = _fake_manager()
    sid = manager.close.return_value.session_id
    with patch("kater.api.routes.get_manager", return_value=manager):
        one = call("DELETE", f"/api/browser/sessions/{sid}")
        all_resp = call("DELETE", "/api/browser/sessions")
    assert one.status == 200
    assert one.payload is not None
    assert one.payload["session"]["state"] == "closed"
    assert all_resp.status == 200
    assert all_resp.payload == {"closed": 1}


def test_browser_act_and_screenshot() -> None:
    manager = _fake_manager()
    sid = "bsess_deadbeefdeadbeefdeadbeefdeadbeef"
    with patch("kater.api.routes.get_manager", return_value=manager):
        act = call(
            "POST",
            f"/api/browser/sessions/{sid}/act",
            body={"kind": "navigate", "url": "https://example.com"},
        )
        shot = call(
            "POST",
            f"/api/browser/sessions/{sid}/screenshot",
            body={"full_page": True},
        )
        bad = call(
            "POST",
            f"/api/browser/sessions/{sid}/act",
            body={"kind": "navigate"},
        )
    assert act.status == 200
    assert act.payload is not None
    assert act.payload["ok"] is True
    manager.act.assert_called_once()
    assert shot.status == 200
    manager.screenshot.assert_called_once_with(sid, full_page=True)
    assert bad.status == 400
    assert bad.payload is not None
    assert "url" in bad.payload["error"]


def test_browser_stats() -> None:
    manager = _fake_manager()
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call("GET", "/api/browser/stats")
    assert resp.status == 200
    assert resp.payload == manager.stats.return_value
