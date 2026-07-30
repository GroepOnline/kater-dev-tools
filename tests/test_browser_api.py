"""REST API coverage for the native browser lane."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kater.api import ROUTER, Request, Response
from kater.browser.models import (
    ActionKind,
    ActionResult,
    BrowserSession,
    ProviderKind,
    SessionState,
)
from kater.browser.providers import BrowserUnavailableError
from kater.browser.session import SessionLimitError, UnknownSessionError
from tests._rest import call


def _call_raw_body(method: str, path: str, raw_body: bytes) -> Response:
    """Dispatch a request with a raw (possibly malformed) body, bypassing json.dumps."""
    matched = ROUTER.match(method, path)
    assert matched is not None, f"{method} {path} has no route"
    route, params = matched
    req = Request(
        method=method,
        path=path,
        query={},
        headers={"content-type": "application/json"},
        raw_body=raw_body,
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
        params=params,
    )
    return route.handler(req)

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
    """Create a ready local browser session with fixed test metadata.

    Parameters:
        session_id (str): Identifier for the browser session.

    Returns:
        BrowserSession: A browser session configured with deterministic test values.
    """
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
    """
    Create a successful browser action result with fixed timing and page metadata.

    Parameters:
        session_id (str): Identifier of the browser session.
        kind (ActionKind): Type of action represented by the result.

    Returns:
        ActionResult: A successful action result for the specified session and action type.
    """
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
    """
    Create a mock browser session manager with predefined responses for API tests.

    Returns:
        MagicMock: A configured manager mock with session lifecycle, action, screenshot, and
            statistics responses.
    """
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
    """Verify that a browser API route is registered in the router.

    Parameters:
        method (str): HTTP method to match.
        path (str): Route path to match.
    """
    assert ROUTER.match(method, path) is not None, f"{method} {path} missing from ROUTER"


def test_browser_providers_returns_list() -> None:
    """Validate that the browser providers endpoint returns a non-empty provider list with the
        expected fields."""
    resp = call("GET", "/api/browser/providers")
    assert resp.status == 200
    assert isinstance(resp.payload, dict)
    providers = resp.payload["providers"]
    assert isinstance(providers, list)
    assert providers
    assert {"kind", "available", "detail"} <= set(providers[0])


def test_browser_sessions_list_empty() -> None:
    """Verify that the browser sessions endpoint returns an empty session list and manager
        statistics."""
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
    """Verify that the browser sessions endpoint requests only live sessions when filtering is
        enabled."""
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
    """Verify that the browser API closes an individual session and all sessions successfully."""
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


def test_browser_create_session_limit_reached() -> None:
    manager = _fake_manager()
    manager.create.side_effect = SessionLimitError(
        "browser session limit reached (4); close a session first"
    )
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call("POST", "/api/browser/sessions", body={})
    assert resp.status == 400
    assert resp.payload is not None
    assert "limit reached" in resp.payload["error"]


def test_browser_close_session_unknown_returns_404() -> None:
    manager = _fake_manager()
    sid = "bsess_missingmissingmissingmissingmi"
    manager.close.side_effect = UnknownSessionError(sid)
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call("DELETE", f"/api/browser/sessions/{sid}")
    assert resp.status == 404
    assert resp.payload is not None
    assert sid in resp.payload["error"]


def test_browser_act_unknown_session_returns_404() -> None:
    manager = _fake_manager()
    manager.get.return_value = None
    sid = "bsess_missingmissingmissingmissingmi"
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call(
            "POST",
            f"/api/browser/sessions/{sid}/act",
            body={"kind": "reload"},
        )
    assert resp.status == 404
    manager.act.assert_not_called()


def test_browser_screenshot_unknown_session_returns_404() -> None:
    manager = _fake_manager()
    manager.get.return_value = None
    sid = "bsess_missingmissingmissingmissingmi"
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call(
            "POST",
            f"/api/browser/sessions/{sid}/screenshot",
            body={},
        )
    assert resp.status == 404
    manager.screenshot.assert_not_called()


def test_browser_create_session_malformed_json_body() -> None:
    manager = _fake_manager()
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = _call_raw_body("POST", "/api/browser/sessions", b"{not valid json")
    assert resp.status == 400
    assert resp.payload is not None
    assert "malformed" in resp.payload["error"].lower()
    manager.create.assert_not_called()


def test_browser_act_malformed_json_body() -> None:
    manager = _fake_manager()
    sid = "bsess_deadbeefdeadbeefdeadbeefdeadbeef"
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = _call_raw_body(
            "POST", f"/api/browser/sessions/{sid}/act", b"{not valid json"
        )
    assert resp.status == 400
    assert resp.payload is not None
    assert "malformed" in resp.payload["error"].lower()


def test_browser_screenshot_malformed_json_body() -> None:
    manager = _fake_manager()
    sid = "bsess_deadbeefdeadbeefdeadbeefdeadbeef"
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = _call_raw_body(
            "POST", f"/api/browser/sessions/{sid}/screenshot", b"{not valid json"
        )
    assert resp.status == 400
    assert resp.payload is not None
    assert "malformed" in resp.payload["error"].lower()


def test_browser_close_all_reports_error() -> None:
    manager = _fake_manager()
    manager.close_all.side_effect = BrowserUnavailableError("provider crashed")
    with patch("kater.api.routes.get_manager", return_value=manager):
        resp = call("DELETE", "/api/browser/sessions")
    assert resp.status == 400
    assert resp.payload == {"error": "provider crashed"}
