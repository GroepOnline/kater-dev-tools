from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from kater.browser import store, tools
from kater.browser.models import (
    ActionKind,
    ActionResult,
    BrowserAction,
    BrowserSession,
    ProviderKind,
    SessionState,
)
from kater.browser.policy import BrowserPolicy
from kater.browser.providers import (
    BrowserProvider,
    PlaywrightProvider,
    ProviderInfo,
    probe_local,
)
from kater.browser.session import (
    BrowserSessionManager,
    SessionLimitError,
    UnknownSessionError,
    get_manager,
    reset_manager,
    set_manager,
)

_LOCAL_PROBE = probe_local()
requires_chromium = pytest.mark.skipif(
    not _LOCAL_PROBE.available, reason=f"local chromium unavailable: {_LOCAL_PROBE.detail}"
)


class FakeProvider(BrowserProvider):
    """In-memory stand-in so session logic is testable without a browser."""

    kind = ProviderKind.LOCAL

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.pages: list[str] = []
        self.closed: list[str] = []
        self.raise_on_act: BaseException | None = None
        self.result_url = "https://example.com/"
        self.result_title = "Example"
        self.actions: list[BrowserAction] = []

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def new_page(self, session: BrowserSession) -> Any:
        self.started = True
        self.pages.append(session.session_id)
        return {"session_id": session.session_id}

    def act(self, handle: Any, action: BrowserAction, policy: BrowserPolicy) -> ActionResult:
        if self.raise_on_act is not None:
            raise self.raise_on_act
        self.actions.append(action)
        return ActionResult(
            ok=True,
            kind=action.kind,
            session_id=handle["session_id"],
            started_at=1.0,
            duration_ms=2.0,
            url=self.result_url,
            title=self.result_title,
        )

    def close_page(self, handle: Any) -> None:
        self.closed.append(handle["session_id"])

    def info(self) -> ProviderInfo:
        return ProviderInfo(self.kind, True, "fake provider")


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def _clean_browser_state():
    store.reset_cache()
    reset_manager()
    yield
    reset_manager()
    store.reset_cache()


@pytest.fixture
def events(monkeypatch):
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr("kater.browser.session.broadcast_event", captured.append)
    return captured


def make_manager(**kwargs) -> tuple[BrowserSessionManager, FakeProvider]:
    provider = FakeProvider()
    policy = kwargs.pop("policy", BrowserPolicy(max_sessions=2, session_ttl_seconds=60))
    manager = BrowserSessionManager(provider=provider, policy=policy, **kwargs)
    return manager, provider


def test_create_registers_and_persists_a_ready_session(events):
    manager, provider = make_manager()
    session = manager.create(label="research", viewport=(1024, 768))

    assert session.state is SessionState.READY
    assert session.label == "research"
    assert session.viewport_width == 1024
    assert provider.pages == [session.session_id]
    assert store.get_session(session.session_id) == session
    assert [e["type"] for e in events] == ["browser_session"]
    assert events[0]["event"] == "created"


def test_create_enforces_max_sessions():
    manager, _ = make_manager()
    manager.create()
    manager.create()
    with pytest.raises(SessionLimitError, match="session limit reached"):
        manager.create()
    manager.close(manager.list_sessions()[0].session_id)
    assert manager.create().state is SessionState.READY


def test_create_marks_the_session_failed_when_the_provider_cannot_open_a_page(events):
    manager, provider = make_manager()

    def boom(session):
        raise RuntimeError("no display")

    provider.new_page = boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="no display"):
        manager.create()
    stored = store.list_sessions()[0]
    assert stored.state is SessionState.FAILED
    assert "no display" in (stored.error or "")
    assert events[0]["event"] == "failed"


def test_act_updates_state_and_persists_the_action(events):
    manager, provider = make_manager()
    session = manager.create()
    events.clear()

    result = manager.act(
        session.session_id, BrowserAction.from_dict({"kind": "navigate", "url": "https://a.test"})
    )

    assert result.ok is True
    assert result.url == "https://example.com/"
    updated = manager.get(session.session_id)
    assert updated is not None
    assert updated.state is SessionState.READY
    assert updated.current_url == "https://example.com/"
    assert updated.title == "Example"

    rows = store.list_actions(session.session_id)
    assert len(rows) == 1
    assert rows[0]["kind"] == "navigate"
    assert rows[0]["ok"] is True
    assert store.get_session(session.session_id) == updated

    assert [e["type"] for e in events] == ["browser_action"]
    assert events[0]["ok"] is True
    assert events[0]["state"] == "ready"


def test_act_never_raises_when_the_provider_explodes():
    manager, provider = make_manager()
    session = manager.create()
    provider.raise_on_act = RuntimeError("target crashed")

    result = manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))

    assert result.ok is False
    assert "target crashed" in (result.error or "")
    failed = manager.get(session.session_id)
    assert failed is not None
    assert failed.state is SessionState.FAILED
    assert store.list_actions(session.session_id)[0]["ok"] is False


def test_act_reports_a_timeout_as_a_failed_result():
    manager, provider = make_manager()
    session = manager.create()
    provider.raise_on_act = TimeoutError()

    result = manager.act(session.session_id, BrowserAction(kind=ActionKind.SNAPSHOT))

    assert result.ok is False
    assert "deadline" in (result.error or "")
    assert session.session_id not in manager._handles
    assert provider.closed == [session.session_id]


def test_failed_session_releases_handle_and_rejects_further_acts():
    manager, provider = make_manager(policy=BrowserPolicy(max_sessions=1, session_ttl_seconds=60))
    session = manager.create()
    provider.raise_on_act = TimeoutError()

    failed = manager.act(session.session_id, BrowserAction(kind=ActionKind.SNAPSHOT))
    assert failed.ok is False
    assert manager.get(session.session_id).state is SessionState.FAILED
    assert manager._handles == {}
    assert manager.stats()["live"] == 0
    assert provider.closed == [session.session_id]

    rejected = manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))
    assert rejected.ok is False
    assert "failed" in (rejected.error or "")

    # Handle was released, so a new session can be created under the limit.
    assert manager.create().state is SessionState.READY


def test_close_all_drains_failed_session_handles():
    manager, provider = make_manager()
    session = manager.create()
    # Simulate a leaked FAILED handle (pre-fix behaviour) by forcing state
    # without going through _finish's cleanup path.
    with manager._lock:
        manager._sessions[session.session_id] = session.with_state(SessionState.FAILED)
    assert session.session_id in manager._handles

    assert manager.close_all() == 1
    assert manager._handles == {}
    assert provider.closed == [session.session_id]
    assert provider.stopped is True


def test_act_rejects_busy_sessions():
    manager, provider = make_manager()
    session = manager.create()
    with manager._lock:
        manager._sessions[session.session_id] = session.with_state(SessionState.BUSY)

    result = manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))
    assert result.ok is False
    assert "busy" in (result.error or "")
    assert provider.actions == []


def test_create_clamps_viewport_to_safe_bounds():
    manager, _ = make_manager()
    huge = manager.create(viewport=(99999, 1))
    assert huge.viewport_width == 2560
    assert huge.viewport_height == 200
    tiny = manager.create(viewport=(10, 10))
    assert tiny.viewport_width == 320
    assert tiny.viewport_height == 200


def test_act_on_unknown_or_closed_sessions_returns_an_error_result():
    manager, _ = make_manager()
    unknown = manager.act("bsess_" + "0" * 32, BrowserAction(kind=ActionKind.RELOAD))
    assert unknown.ok is False
    assert "unknown session" in (unknown.error or "")

    session = manager.create()
    manager.close(session.session_id)
    closed = manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))
    assert closed.ok is False
    assert "closed" in (closed.error or "")


def test_screenshot_delegates_to_act():
    manager, provider = make_manager()
    session = manager.create()
    result = manager.screenshot(session.session_id, full_page=True)
    assert result.ok is True
    assert provider.actions[-1].kind is ActionKind.SCREENSHOT
    assert provider.actions[-1].full_page is True


def test_close_is_idempotent_and_closes_the_page(events):
    manager, provider = make_manager()
    session = manager.create()
    events.clear()

    closed = manager.close(session.session_id)
    assert closed.state is SessionState.CLOSED
    assert provider.closed == [session.session_id]
    assert store.get_session(session.session_id).state is SessionState.CLOSED
    assert events[-1]["event"] == "closed"

    manager.close(session.session_id)
    assert provider.closed == [session.session_id]

    with pytest.raises(UnknownSessionError):
        manager.close("bsess_" + "1" * 32)


def test_close_all_stops_the_provider():
    manager, provider = make_manager()
    manager.create()
    manager.create()
    assert manager.close_all() == 2
    assert provider.stopped is True
    assert manager.list_sessions(live_only=True) == []


def test_reap_expired_closes_sessions_past_their_ttl():
    clock = FakeClock()
    manager, _ = make_manager(
        clock=clock, policy=BrowserPolicy(max_sessions=4, session_ttl_seconds=30)
    )
    stale = manager.create(label="stale")
    clock.advance(31)
    fresh = manager.create(label="fresh")

    assert manager.reap_expired() == 1
    assert manager.get(stale.session_id).state is SessionState.CLOSED
    assert manager.get(fresh.session_id).state is SessionState.READY
    assert manager.reap_expired() == 0


def test_act_extends_the_session_ttl():
    clock = FakeClock()
    manager, _ = make_manager(
        clock=clock, policy=BrowserPolicy(max_sessions=4, session_ttl_seconds=30)
    )
    session = manager.create()
    clock.advance(20)
    manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))
    clock.advance(20)
    assert manager.reap_expired() == 0


def test_stats_shape():
    manager, _ = make_manager()
    session = manager.create()
    manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))
    manager.create()
    manager.close(session.session_id)

    stats = manager.stats()
    assert stats["sessions"] == 2
    assert stats["live"] == 1
    assert stats["by_state"]["ready"] == 1
    assert stats["by_state"]["closed"] == 1
    assert stats["provider"] == "local"
    assert stats["provider_info"]["detail"] == "fake provider"
    assert stats["total_actions"] == 1
    assert stats["persisted_actions"] == 1
    assert stats["max_sessions"] == 2
    assert stats["last_error"] is None


def test_stats_reports_the_last_error():
    manager, provider = make_manager()
    session = manager.create()
    provider.raise_on_act = RuntimeError("target crashed")
    manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD))
    assert "target crashed" in manager.stats()["last_error"]


def test_broadcast_failure_does_not_break_the_call(monkeypatch):
    def explode(event):
        raise RuntimeError("no websocket clients")

    monkeypatch.setattr("kater.browser.session.broadcast_event", explode)
    manager, _ = make_manager()
    session = manager.create()
    assert manager.act(session.session_id, BrowserAction(kind=ActionKind.RELOAD)).ok is True


def test_singleton_accessors():
    reset_manager()
    manager = get_manager()
    assert get_manager() is manager
    reset_manager()
    assert get_manager() is not manager

    injected, _ = make_manager()
    set_manager(injected)
    assert get_manager() is injected


def test_tool_dispatch_round_trip():
    manager, _ = make_manager()
    opened = tools.dispatch("kater_browser_open", {"manager": manager, "label": "lane"})
    assert opened["ok"] is True
    session_id = opened["session"]["session_id"]

    acted = tools.dispatch(
        "kater_browser_act",
        {"manager": manager, "session_id": session_id, "kind": "navigate", "url": "https://a.test"},
    )
    assert acted["ok"] is True

    listed = tools.dispatch("kater_browser_sessions", {"manager": manager})
    assert len(listed["sessions"]) == 1
    assert listed["stats"]["total_actions"] == 1

    assert tools.dispatch("kater_browser_close", {"manager": manager, "session_id": session_id})[
        "ok"
    ]
    assert tools.dispatch("kater_browser_providers", {})["providers"]

    with pytest.raises(KeyError):
        tools.dispatch("kater_browser_teleport", {})


def test_tool_dispatch_reports_validation_errors():
    manager, _ = make_manager()
    opened = tools.dispatch("kater_browser_open", {"manager": manager})
    session_id = opened["session"]["session_id"]
    bad = tools.dispatch(
        "kater_browser_act", {"manager": manager, "session_id": session_id, "kind": "navigate"}
    )
    assert bad["ok"] is False
    assert "requires 'url'" in bad["error"]
    missing_id = tools.dispatch("kater_browser_act", {"manager": manager, "kind": "reload"})
    assert missing_id["ok"] is False


def test_tool_screenshot_and_close_all():
    manager, provider = make_manager()
    opened = tools.dispatch("kater_browser_open", {"manager": manager})
    session_id = opened["session"]["session_id"]

    shot = tools.dispatch(
        "kater_browser_screenshot",
        {"manager": manager, "session_id": session_id, "full_page": True},
    )
    assert shot["ok"] is True
    assert provider.actions[-1].kind is ActionKind.SCREENSHOT

    assert tools.dispatch("kater_browser_screenshot", {"manager": manager})["ok"] is False
    assert tools.dispatch("kater_browser_close", {"manager": manager})["ok"] is False
    unknown = tools.dispatch(
        "kater_browser_close", {"manager": manager, "session_id": "bsess_" + "2" * 32}
    )
    assert unknown["error"].startswith("unknown session")
    assert tools.dispatch("kater_browser_close", {"manager": manager, "all": True})["closed"] == 1


def test_tool_open_reports_the_session_limit():
    manager, _ = make_manager(policy=BrowserPolicy(max_sessions=1))
    assert tools.dispatch("kater_browser_open", {"manager": manager})["ok"] is True
    limited = tools.dispatch("kater_browser_open", {"manager": manager})
    assert limited["ok"] is False
    assert "session limit reached" in limited["error"]


def test_tool_specs_are_well_formed():
    names = [spec["name"] for spec in tools.BROWSER_TOOL_SPECS]
    assert sorted(names) == sorted(tools.HANDLERS)
    assert len(names) == len(set(names))
    for spec in tools.BROWSER_TOOL_SPECS:
        assert spec["description"]
        assert spec["risk"] in {"low", "medium"}
        assert spec["input_schema"]["type"] == "object"
    risks = {spec["name"]: spec["risk"] for spec in tools.BROWSER_TOOL_SPECS}
    assert risks["kater_browser_sessions"] == "low"
    assert risks["kater_browser_providers"] == "low"
    assert risks["kater_browser_act"] == "medium"


# ── real chromium ──────────────────────────────────────────────────

_PAGE = """<!doctype html>
<html><head><title>Kater Browser Lane</title></head>
<body>
  <h1>Browser lane online</h1>
  <p id="para">The quick brown fox jumps over the lazy dog.</p>
  <a id="link" href="/next">Open the next page</a>
  <button id="go" aria-label="Go button">Go</button>
  <input id="q" name="query" placeholder="Search docs">
  <select id="pick"><option value="one">One</option><option value="two">Two</option></select>
</body></html>
"""

_NEXT_PAGE = """<!doctype html>
<html><head><title>Second page</title></head><body><h1>Second page</h1></body></html>
"""


class _PageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = (_NEXT_PAGE if self.path.startswith("/next") else _PAGE).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


@pytest.fixture
def local_site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@requires_chromium
def test_real_chromium_end_to_end(local_site):
    policy = BrowserPolicy(
        allow_private_networks=True,
        max_sessions=1,
        session_ttl_seconds=120,
        action_timeout_ms=10_000,
    )
    manager = BrowserSessionManager(provider=PlaywrightProvider(), policy=policy)
    started = time.time()
    try:
        session = manager.create(label="e2e")
        assert session.state is SessionState.READY

        navigated = manager.act(
            session.session_id, BrowserAction.from_dict({"kind": "navigate", "url": local_site})
        )
        assert navigated.ok is True, navigated.error
        assert navigated.title == "Kater Browser Lane"

        text_action = BrowserAction.from_dict({"kind": "extract_text", "selector": "#para"})
        text = manager.act(session.session_id, text_action)
        assert text.ok is True, text.error
        assert "quick brown fox" in (text.text or "")

        snapshot = manager.act(session.session_id, BrowserAction(kind=ActionKind.SNAPSHOT))
        assert snapshot.ok is True, snapshot.error
        elements = {item["selector"]: item for item in (snapshot.snapshot or ())}
        assert {"#link", "#go", "#q", "#pick"} <= set(elements)
        assert elements["#go"]["name"] == "Go button"
        assert elements["#go"]["tag"] == "button"
        assert elements["#q"]["name"] == "Search docs"

        shot = manager.screenshot(session.session_id)
        assert shot.ok is True, shot.error
        assert (shot.screenshot_b64 or "").startswith("/9j/")  # JPEG magic

        clicked = manager.act(
            session.session_id, BrowserAction.from_dict({"kind": "click", "selector": "#link"})
        )
        assert clicked.ok is True, clicked.error
        assert clicked.url.endswith("/next")
        assert clicked.title == "Second page"

        back = manager.act(session.session_id, BrowserAction(kind=ActionKind.BACK))
        assert back.ok is True, back.error
        assert back.title == "Kater Browser Lane"

        stats = manager.stats()
        assert stats["live"] == 1
        assert stats["total_actions"] == 6
        assert len(store.list_actions(session.session_id)) == 6
    finally:
        manager.close_all()
    assert time.time() - started < 20


@requires_chromium
def test_real_chromium_refuses_blocked_urls(local_site):
    policy = BrowserPolicy(
        allow_private_networks=True,
        deny_domains=("blocked.test",),
        max_sessions=1,
        action_timeout_ms=10_000,
    )
    manager = BrowserSessionManager(provider=PlaywrightProvider(), policy=policy)
    try:
        session = manager.create()
        for url, expected in (
            ("file:///etc/passwd", "never allowed"),
            ("http://blocked.test/", "denied domain"),
        ):
            result = manager.act(
                session.session_id, BrowserAction.from_dict({"kind": "navigate", "url": url})
            )
            assert result.ok is False
            assert expected in (result.error or "")

        ok = manager.act(
            session.session_id, BrowserAction.from_dict({"kind": "navigate", "url": local_site})
        )
        assert ok.ok is True, ok.error

        blocked_eval = manager.act(
            session.session_id, BrowserAction.from_dict({"kind": "evaluate", "expression": "1+1"})
        )
        assert blocked_eval.ok is False
        assert "evaluate is disabled" in (blocked_eval.error or "")
    finally:
        manager.close_all()


@requires_chromium
def test_real_chromium_runs_every_interaction_kind(local_site):
    policy = BrowserPolicy(allow_private_networks=True, max_sessions=1, action_timeout_ms=10_000)
    manager = BrowserSessionManager(provider=PlaywrightProvider(), policy=policy)
    try:
        session = manager.create()

        def run(payload: dict[str, Any]) -> ActionResult:
            result = manager.act(session.session_id, BrowserAction.from_dict(payload))
            assert result.ok is True, f"{payload} failed: {result.error}"
            return result

        run({"kind": "navigate", "url": local_site})
        run({"kind": "type", "selector": "#q", "text": "kater lane"})
        run({"kind": "press", "key": "Tab"})
        run({"kind": "scroll", "delta_y": 200})
        run({"kind": "wait", "selector": "#pick"})
        run({"kind": "wait", "timeout_ms": 50})
        run({"kind": "select", "selector": "#pick", "value": "two"})
        run({"kind": "reload"})
        run({"kind": "click", "selector": "#link"})
        run({"kind": "back"})
        forward = run({"kind": "forward"})
        assert forward.title == "Second page"
        assert run({"kind": "screenshot", "full_page": True}).screenshot_b64
    finally:
        manager.close_all()


@requires_chromium
def test_real_chromium_screenshot_respects_the_byte_cap(local_site):
    policy = BrowserPolicy(
        allow_private_networks=True,
        max_sessions=1,
        action_timeout_ms=10_000,
        max_screenshot_bytes=256,
    )
    manager = BrowserSessionManager(provider=PlaywrightProvider(), policy=policy)
    try:
        session = manager.create()
        manager.act(
            session.session_id, BrowserAction.from_dict({"kind": "navigate", "url": local_site})
        )
        result = manager.screenshot(session.session_id)
        assert result.ok is False
        assert "over the 256 byte cap" in (result.error or "")
    finally:
        manager.close_all()


@requires_chromium
def test_real_chromium_lane_restarts_after_close_all(local_site):
    policy = BrowserPolicy(allow_private_networks=True, max_sessions=1, action_timeout_ms=10_000)
    provider = PlaywrightProvider()
    manager = BrowserSessionManager(provider=provider, policy=policy)
    try:
        first = manager.create()
        assert manager.act(
            first.session_id, BrowserAction.from_dict({"kind": "navigate", "url": local_site})
        ).ok
        manager.close_all()

        second = manager.create()
        result = manager.act(
            second.session_id, BrowserAction.from_dict({"kind": "navigate", "url": local_site})
        )
        assert result.ok is True, result.error
        assert result.title == "Kater Browser Lane"
    finally:
        manager.close_all()


@requires_chromium
def test_real_chromium_allows_evaluate_when_enabled(local_site):
    policy = BrowserPolicy(allow_private_networks=True, max_sessions=1, action_timeout_ms=10_000)
    manager = BrowserSessionManager(
        provider=PlaywrightProvider(allow_evaluate=True), policy=policy
    )
    try:
        session = manager.create()
        manager.act(
            session.session_id, BrowserAction.from_dict({"kind": "navigate", "url": local_site})
        )
        result = manager.act(
            session.session_id,
            BrowserAction.from_dict({"kind": "evaluate", "expression": "document.title"}),
        )
        assert result.ok is True, result.error
        assert result.text == "Kater Browser Lane"
    finally:
        manager.close_all()
