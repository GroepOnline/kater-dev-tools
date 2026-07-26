"""MCP-facing tool specs and handlers for the browser lane.

Deliberately free of any ``kater.registry`` import so the registry can depend
on this module without a cycle: the specs are plain data, and each handler is
a thin function returning a JSON-safe dict.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kater.browser.models import ActionKind, BrowserAction
from kater.browser.policy import PolicyViolation
from kater.browser.providers import BrowserUnavailableError, probe_providers
from kater.browser.session import (
    BrowserSessionManager,
    SessionLimitError,
    UnknownSessionError,
    get_manager,
)

_ACTION_KINDS = [kind.value for kind in ActionKind]

_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string", "description": "Session id from kater_browser_open."},
        "kind": {"type": "string", "enum": _ACTION_KINDS, "description": "Action to perform."},
        "url": {"type": "string", "description": "Target URL (navigate)."},
        "selector": {"type": "string", "description": "CSS selector (click/type/select/wait)."},
        "text": {"type": "string", "description": "Text to fill (type)."},
        "key": {"type": "string", "description": "Key to press, e.g. 'Enter' (press)."},
        "value": {"type": "string", "description": "Option value (select)."},
        "expression": {"type": "string", "description": "JS expression (evaluate, if enabled)."},
        "delta_y": {"type": "integer", "description": "Pixels to scroll vertically (scroll)."},
        "timeout_ms": {"type": "integer", "description": "Per-action timeout override."},
        "full_page": {"type": "boolean", "description": "Capture the full page (screenshot)."},
    },
    "required": ["session_id", "kind"],
    "additionalProperties": False,
}

BROWSER_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "kater_browser_open",
        "description": (
            "Open a policy-guarded browser session and return its id. "
            "Sessions are isolated (own cookies) and expire after the configured TTL."
        ),
        "risk": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Human label shown in the UI."},
                "profile": {"type": "string", "description": "Kater profile owning the session."},
                "width": {"type": "integer", "description": "Viewport width (default 1280)."},
                "height": {"type": "integer", "description": "Viewport height (default 800)."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "kater_browser_act",
        "description": (
            "Run one browser action (navigate, click, type, press, scroll, wait, snapshot, "
            "extract_text, back, forward, reload, select) in an open session. Every URL is "
            "checked against the navigation policy before and after the action."
        ),
        "risk": "medium",
        "input_schema": _ACTION_SCHEMA,
    },
    {
        "name": "kater_browser_screenshot",
        "description": "Capture the current page as a base64 JPEG for the live view.",
        "risk": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "full_page": {"type": "boolean"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "kater_browser_sessions",
        "description": "List browser sessions with their state, URL and lane statistics.",
        "risk": "low",
        "input_schema": {
            "type": "object",
            "properties": {
                "live_only": {"type": "boolean", "description": "Hide closed/failed sessions."}
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "kater_browser_close",
        "description": "Close one browser session, or every session when 'all' is true.",
        "risk": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "all": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "kater_browser_providers",
        "description": (
            "Report which browser backends are available (local Playwright Chromium, "
            "a CDP endpoint, or a Steel Browser session API) without starting one."
        ),
        "risk": "low",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
)


def browser_open_tool(**kwargs: Any) -> dict[str, Any]:
    manager = _manager(kwargs)
    width = int(kwargs.get("width") or 1280)
    height = int(kwargs.get("height") or 800)
    try:
        session = manager.create(
            label=kwargs.get("label"),
            profile=str(kwargs.get("profile") or "core"),
            viewport=(width, height),
        )
    except (SessionLimitError, BrowserUnavailableError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "session": session.to_dict()}


def browser_act_tool(**kwargs: Any) -> dict[str, Any]:
    manager = _manager(kwargs)
    session_id = str(kwargs.get("session_id") or "")
    if not session_id:
        return {"ok": False, "error": "session_id is required"}
    payload = {k: v for k, v in kwargs.items() if k not in ("session_id", "manager")}
    try:
        action = BrowserAction.from_dict(payload)
    except (ValueError, PolicyViolation) as exc:
        return {"ok": False, "error": str(exc)}
    return manager.act(session_id, action).to_dict()


def browser_screenshot_tool(**kwargs: Any) -> dict[str, Any]:
    manager = _manager(kwargs)
    session_id = str(kwargs.get("session_id") or "")
    if not session_id:
        return {"ok": False, "error": "session_id is required"}
    return manager.screenshot(session_id, bool(kwargs.get("full_page", False))).to_dict()


def browser_sessions_tool(**kwargs: Any) -> dict[str, Any]:
    manager = _manager(kwargs)
    live_only = bool(kwargs.get("live_only", False))
    return {
        "sessions": [s.to_dict() for s in manager.list_sessions(live_only=live_only)],
        "stats": manager.stats(),
    }


def browser_close_tool(**kwargs: Any) -> dict[str, Any]:
    manager = _manager(kwargs)
    if bool(kwargs.get("all", False)):
        return {"ok": True, "closed": manager.close_all()}
    session_id = str(kwargs.get("session_id") or "")
    if not session_id:
        return {"ok": False, "error": "session_id is required (or pass all=true)"}
    try:
        session = manager.close(session_id)
    except UnknownSessionError:
        return {"ok": False, "error": f"unknown session: {session_id}"}
    return {"ok": True, "session": session.to_dict()}


def browser_providers_tool(**kwargs: Any) -> dict[str, Any]:
    del kwargs
    return {"providers": [info.to_dict() for info in probe_providers()]}


HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "kater_browser_open": browser_open_tool,
    "kater_browser_act": browser_act_tool,
    "kater_browser_screenshot": browser_screenshot_tool,
    "kater_browser_sessions": browser_sessions_tool,
    "kater_browser_close": browser_close_tool,
    "kater_browser_providers": browser_providers_tool,
}


def dispatch(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke one browser tool by name; raises ``KeyError`` for unknown tools."""
    handler = HANDLERS.get(name)
    if handler is None:
        raise KeyError(f"unknown browser tool: {name}")
    return handler(**(arguments or {}))


def _manager(kwargs: dict[str, Any]) -> BrowserSessionManager:
    """Allow an explicit manager injection (tests, embedded runtimes)."""
    injected = kwargs.pop("manager", None)
    if isinstance(injected, BrowserSessionManager):
        return injected
    return get_manager()
