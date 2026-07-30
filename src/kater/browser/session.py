"""Session orchestration for the native browser lane.

Owns the session lifecycle (create → act → close), enforces the policy limits
that are not per-URL (session count, TTL, action deadline), persists every
session and action to SQLite, and broadcasts telemetry so the dashboard's
browser pane can follow along live.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from kater.browser import store
from kater.browser.models import (
    ActionKind,
    ActionResult,
    BrowserAction,
    BrowserSession,
    ProviderKind,
    SessionState,
    new_session_id,
)
from kater.browser.policy import BrowserPolicy, load_policy
from kater.browser.providers import BrowserProvider, ProviderInfo, resolve_provider
from kater.websocket import broadcast_event

_log = logging.getLogger("kater.browser.session")

_LIVE_STATES = frozenset({SessionState.PENDING, SessionState.READY, SessionState.BUSY})


class SessionLimitError(RuntimeError):
    """Raised when a new session would exceed ``policy.max_sessions``."""


class UnknownSessionError(KeyError):
    """Raised when a session id is not known to this manager."""


class BrowserSessionManager:
    """Thread-safe owner of every live browser session in this process."""

    def __init__(
        self,
        *,
        provider: BrowserProvider | None = None,
        policy: BrowserPolicy | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._policy = policy or load_policy()
        self._clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[str, BrowserSession] = {}
        self._handles: dict[str, Any] = {}
        self._action_count = 0
        self._last_error: str | None = None

    # ── properties ─────────────────────────────────────────────────

    @property
    def policy(self) -> BrowserPolicy:
        return self._policy

    @property
    def provider(self) -> BrowserProvider:
        """Resolve the configured provider on first use (never at import time)."""
        with self._lock:
            if self._provider is None:
                self._provider = resolve_provider()
            return self._provider

    # ── lifecycle ──────────────────────────────────────────────────

    def create(
        self,
        label: str | None = None,
        profile: str = "core",
        viewport: tuple[int, int] = (1280, 800),
    ) -> BrowserSession:
        """Open a fresh isolated browser context and register it."""
        now = self._clock()
        width, height = _clamp_viewport(viewport)
        with self._lock:
            live = [s for s in self._sessions.values() if s.state in _LIVE_STATES]
            if len(live) >= self._policy.max_sessions:
                raise SessionLimitError(
                    f"browser session limit reached ({self._policy.max_sessions}); "
                    "close a session first"
                )
            provider = self.provider
            session = BrowserSession(
                session_id=new_session_id(),
                provider=provider.kind,
                state=SessionState.PENDING,
                created_at=now,
                last_used_at=now,
                expires_at=now + self._policy.session_ttl_seconds,
                label=label,
                profile=profile,
                viewport_width=width,
                viewport_height=height,
            )
            self._sessions[session.session_id] = session
        store.upsert_session(session)

        try:
            handle = provider.new_page(session)
        except Exception as exc:
            failed = session.with_state(SessionState.FAILED, error=_describe(exc))
            with self._lock:
                self._sessions[failed.session_id] = failed
                self._last_error = failed.error
            store.upsert_session(failed)
            self._emit("browser_session", {"event": "failed", "session": failed.to_dict()})
            raise

        ready = session.with_state(SessionState.READY, last_used_at=self._clock())
        with self._lock:
            self._handles[ready.session_id] = handle
            self._sessions[ready.session_id] = ready
        store.upsert_session(ready)
        self._emit("browser_session", {"event": "created", "session": ready.to_dict()})
        return ready

    def get(self, session_id: str) -> BrowserSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
        return session if session is not None else store.get_session(session_id)

    def list_sessions(self, *, live_only: bool = False) -> list[BrowserSession]:
        with self._lock:
            sessions = list(self._sessions.values())
        if live_only:
            sessions = [s for s in sessions if s.state in _LIVE_STATES]
        return sorted(sessions, key=lambda s: s.created_at)

    def close(self, session_id: str) -> BrowserSession:
        """Close one session's page and mark it CLOSED (idempotent)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                stored = store.get_session(session_id)
                if stored is None:
                    raise UnknownSessionError(session_id)
                session = stored
            handle = self._handles.pop(session_id, None)
        if handle is not None:
            try:
                self.provider.close_page(handle)
            except Exception as exc:
                _log.debug("close_page failed for %s: %s", session_id, exc)
        closed = session.with_state(SessionState.CLOSED, last_used_at=self._clock())
        with self._lock:
            self._sessions[session_id] = closed
        store.upsert_session(closed)
        self._emit("browser_session", {"event": "closed", "session": closed.to_dict()})
        return closed

    def close_all(self) -> int:
        """Close every session that still holds a page handle (or is live) and stop the provider."""
        with self._lock:
            ids = sorted(
                set(self._handles)
                | {sid for sid, s in self._sessions.items() if s.state in _LIVE_STATES}
            )
        for session_id in ids:
            try:
                self.close(session_id)
            except Exception as exc:
                _log.debug("close failed for %s: %s", session_id, exc)
        with self._lock:
            provider = self._provider
        if provider is not None:
            try:
                provider.stop()
            except Exception as exc:
                _log.debug("provider stop failed: %s", exc)
        return len(ids)

    def reap_expired(self) -> int:
        """Close sessions past their TTL; returns how many were reaped."""
        now = self._clock()
        with self._lock:
            expired = [
                sid
                for sid, s in self._sessions.items()
                if s.state in _LIVE_STATES and s.is_expired(now)
            ]
        reaped = 0
        for session_id in expired:
            try:
                self.close(session_id)
                reaped += 1
            except Exception as exc:
                _log.debug("reap failed for %s: %s", session_id, exc)
        return reaped

    # ── actions ────────────────────────────────────────────────────

    def act(self, session_id: str, action: BrowserAction) -> ActionResult:
        """Run one action. Never raises: failures come back as ``ok=False``."""
        started = self._clock()
        with self._lock:
            session = self._sessions.get(session_id)
            handle = self._handles.get(session_id)
            if session is None:
                return self._error_result(action, session_id, started, "unknown session")
            if session.state is SessionState.CLOSED:
                return self._error_result(action, session_id, started, "session is closed")
            if session.state is SessionState.FAILED:
                return self._error_result(action, session_id, started, "session has failed")
            if session.state is SessionState.BUSY:
                return self._error_result(action, session_id, started, "session is busy")
            if handle is None:
                return self._error_result(
                    action, session_id, started, "session has no live page"
                )
            busy = session.with_state(SessionState.BUSY, last_used_at=started)
            self._sessions[session_id] = busy
        store.upsert_session(busy)

        try:
            result = self.provider.act(handle, action, self._policy)
            next_state = SessionState.READY
        except TimeoutError:
            result = self._error_result(
                action, session_id, started, "action exceeded its deadline"
            )
            next_state = SessionState.FAILED
        except Exception as exc:
            result = self._error_result(action, session_id, started, _describe(exc))
            next_state = SessionState.FAILED

        self._finish(busy, result, next_state)
        return result

    def screenshot(self, session_id: str, full_page: bool = False) -> ActionResult:
        """Capture the live view as a base64 JPEG."""
        return self.act(session_id, BrowserAction(kind=ActionKind.SCREENSHOT, full_page=full_page))

    def _finish(
        self, session: BrowserSession, result: ActionResult, next_state: SessionState
    ) -> None:
        now = self._clock()
        updated = session.with_state(
            next_state,
            last_used_at=now,
            expires_at=now + self._policy.session_ttl_seconds,
            current_url=result.url if result.url is not None else session.current_url,
            title=result.title if result.title is not None else session.title,
            error=result.error,
        )
        handle_to_close: Any | None = None
        with self._lock:
            self._sessions[updated.session_id] = updated
            self._action_count += 1
            if result.error:
                self._last_error = result.error
            if next_state is SessionState.FAILED:
                # Drop the page immediately so FAILED sessions cannot leak Playwright
                # handles or be reused via a second act().
                handle_to_close = self._handles.pop(updated.session_id, None)
        if handle_to_close is not None:
            try:
                self.provider.close_page(handle_to_close)
            except Exception as exc:
                _log.debug("close_page failed for %s: %s", updated.session_id, exc)
        store.upsert_session(updated)
        try:
            store.record_action(result, detail={"title": result.title} if result.title else None)
        except Exception as exc:
            _log.warning("could not persist browser action: %s", exc)
        self._emit(
            "browser_action",
            {
                "session_id": updated.session_id,
                "kind": result.kind.value,
                "ok": result.ok,
                "url": result.url,
                "title": result.title,
                "duration_ms": result.duration_ms,
                "error": result.error,
                "state": updated.state.value,
            },
        )

    # ── introspection ──────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Counts the dashboard's browser pane renders."""
        with self._lock:
            sessions = list(self._sessions.values())
            provider = self._provider
            action_count = self._action_count
            last_error = self._last_error
        by_state = {state.value: 0 for state in SessionState}
        for session in sessions:
            by_state[session.state.value] += 1
        info: ProviderInfo | None = None
        if provider is not None:
            try:
                info = provider.info()
            except Exception as exc:
                _log.debug("provider info failed: %s", exc)
        kind = provider.kind if provider is not None else None
        return {
            "sessions": len(sessions),
            "live": sum(1 for s in sessions if s.state in _LIVE_STATES),
            "by_state": by_state,
            "provider": (kind or ProviderKind.LOCAL).value,
            "provider_started": provider is not None,
            "provider_info": info.to_dict() if info is not None else None,
            "total_actions": action_count,
            "persisted_actions": _safe_count(),
            "max_sessions": self._policy.max_sessions,
            "last_error": last_error,
        }

    # ── helpers ────────────────────────────────────────────────────

    def _error_result(
        self, action: BrowserAction, session_id: str, started: float, message: str
    ) -> ActionResult:
        return ActionResult(
            ok=False,
            kind=action.kind,
            session_id=session_id,
            started_at=started,
            duration_ms=(self._clock() - started) * 1000.0,
            error=message,
        )

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            broadcast_event({"type": event_type, "timestamp": self._clock(), **payload})
        except Exception as exc:
            # Telemetry is best-effort: a disconnected dashboard must never
            # break an agent's browser call.
            _log.debug("browser broadcast failed: %s", exc)

def _describe(exc: BaseException) -> str:
    message = str(exc).strip()
    first = message.splitlines()[0] if message else ""
    return f"{exc.__class__.__name__}: {first}" if first else exc.__class__.__name__

MIN_VIEWPORT = (320, 200)
MAX_VIEWPORT = (2560, 1440)

def _clamp_viewport(viewport: tuple[int, int]) -> tuple[int, int]:
    width = max(MIN_VIEWPORT[0], min(MAX_VIEWPORT[0], int(viewport[0])))
    height = max(MIN_VIEWPORT[1], min(MAX_VIEWPORT[1], int(viewport[1])))
    return width, height

def _safe_count() -> int:
    try:
        return store.count_actions()
    except Exception:
        return 0

_manager: BrowserSessionManager | None = None
_manager_lock = threading.Lock()

def get_manager() -> BrowserSessionManager:
    """Process-wide session manager used by the CLI, REST API and MCP tools."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = BrowserSessionManager()
        return _manager

def set_manager(manager: BrowserSessionManager | None) -> None:
    """Install a manager explicitly (used by tests and by the runtime bootstrap)."""
    global _manager
    with _manager_lock:
        previous = _manager
        if previous is manager:
            return
        _manager = manager
    if previous is not None:
        try:
            previous.close_all()
        except Exception as exc:
            _log.debug("manager shutdown failed: %s", exc)

def reset_manager() -> None:
    """Close everything and drop the singleton."""
    global _manager
    with _manager_lock:
        manager = _manager
        _manager = None
    if manager is not None:
        try:
            manager.close_all()
        except Exception as exc:
            _log.debug("manager shutdown failed: %s", exc)
