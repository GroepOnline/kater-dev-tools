"""Value types for the native browser lane.

Pure data: enums, frozen dataclasses and validation. No I/O, no provider
imports, so this module is safe to import from the API, CLI and MCP layers.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

SESSION_ID_PREFIX = "bsess_"
SESSION_ID_HEX_LEN = 32

DEFAULT_VIEWPORT = (1280, 800)

# Hard ceiling for untrusted timeout_ms input (policy may clamp further).
MAX_ACTION_TIMEOUT_MS = 300_000


def new_session_id() -> str:
    """Return a fresh opaque session id (``bsess_`` + 32 hex chars)."""
    return f"{SESSION_ID_PREFIX}{secrets.token_hex(16)}"


def is_session_id(value: str) -> bool:
    """Validate the format of a browser session ID.

    Parameters:
        value (str): Candidate session ID.

    Returns:
        bool: `true` if the value has the required prefix and lowercase hexadecimal suffix, `false`
            otherwise.
    """
    if not value.startswith(SESSION_ID_PREFIX):
        return False
    suffix = value[len(SESSION_ID_PREFIX) :]
    if len(suffix) != SESSION_ID_HEX_LEN:
        return False
    return all(ch in "0123456789abcdef" for ch in suffix)


class SessionState(StrEnum):
    PENDING = "pending"
    READY = "ready"
    BUSY = "busy"
    CLOSED = "closed"
    FAILED = "failed"


class ProviderKind(StrEnum):
    """Where the browser actually runs.

    LOCAL  — Playwright-managed Chromium in this process' machine.
    CDP    — attach to any Chrome DevTools Protocol endpoint (Browserless,
             Steel Browser, ``chrome --remote-debugging-port``).
    REMOTE — a hosted session API (Steel Browser REST) that hands back a CDP url.
    """

    LOCAL = "local"
    CDP = "cdp"
    REMOTE = "remote"


class ActionKind(StrEnum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    SNAPSHOT = "snapshot"
    EXTRACT_TEXT = "extract_text"
    EVALUATE = "evaluate"
    BACK = "back"
    FORWARD = "forward"
    RELOAD = "reload"
    SELECT = "select"


# Actions that can leave the current origin, so the resulting URL has to be
# re-checked against the policy afterwards (redirect-to-internal defence).
NAVIGATING_KINDS = frozenset(
    {
        ActionKind.NAVIGATE,
        ActionKind.CLICK,
        ActionKind.PRESS,
        ActionKind.BACK,
        ActionKind.FORWARD,
        ActionKind.RELOAD,
        ActionKind.SELECT,
        ActionKind.EVALUATE,
    }
)

# field name -> kinds that require it
_REQUIRED_FIELDS: dict[ActionKind, tuple[str, ...]] = {
    ActionKind.NAVIGATE: ("url",),
    ActionKind.CLICK: ("selector",),
    ActionKind.TYPE: ("selector", "text"),
    ActionKind.PRESS: ("key",),
    ActionKind.EVALUATE: ("expression",),
    ActionKind.SELECT: ("selector", "value"),
}

_ACTION_FIELDS = frozenset(
    {
        "kind",
        "url",
        "selector",
        "text",
        "key",
        "timeout_ms",
        "full_page",
        "expression",
        "delta_y",
        "value",
    }
)


@dataclass(frozen=True)
class BrowserSession:
    """One isolated browser context owned by an agent."""

    session_id: str
    provider: ProviderKind
    state: SessionState
    created_at: float
    last_used_at: float
    expires_at: float
    current_url: str | None = None
    title: str | None = None
    label: str | None = None
    profile: str = "core"
    viewport_width: int = DEFAULT_VIEWPORT[0]
    viewport_height: int = DEFAULT_VIEWPORT[1]
    error: str | None = None

    def is_expired(self, now: float) -> bool:
        """Determine whether the browser session has expired.

        Parameters:
            now (float): The current timestamp.

        Returns:
            bool: `True` if the session has an expiration time and the timestamp has reached it,
                `False` otherwise.
        """
        return self.expires_at > 0 and now >= self.expires_at

    def with_state(self, state: SessionState, **changes: Any) -> BrowserSession:
        """Create a new session record with an updated state and optional field changes.

        Parameters:
            state (SessionState): The session lifecycle state to assign.
            **changes (Any): Field values to update in the new session record.

        Returns:
            BrowserSession: A new session record containing the requested updates.
        """
        return replace(self, state=state, **changes)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the browser session as a JSON-compatible dictionary.

        Returns:
            dict[str, Any]: A dictionary containing the session fields, enum values as
                strings, and viewport dimensions nested under ``viewport``.
        """
        return {
            "session_id": self.session_id,
            "provider": self.provider.value,
            "state": self.state.value,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "expires_at": self.expires_at,
            "current_url": self.current_url,
            "title": self.title,
            "label": self.label,
            "profile": self.profile,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "error": self.error,
        }


@dataclass(frozen=True)
class BrowserAction:
    """One agent-issued instruction for a page."""

    kind: ActionKind
    url: str | None = None
    selector: str | None = None
    text: str | None = None
    key: str | None = None
    timeout_ms: int | None = None
    full_page: bool = False
    expression: str | None = None
    delta_y: int | None = None
    value: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrowserAction:
        """
        Create a validated browser action from an untrusted dictionary.

        Parameters:
            data (dict[str, Any]): Action fields to validate and convert.

        Returns:
            BrowserAction: The validated browser action.

        Raises:
            ValueError: If the input is not a dictionary, contains unknown fields, omits required
                fields, uses an unsupported action kind, or contains invalid field values.
        """
        if not isinstance(data, dict):
            raise ValueError("action must be an object")
        unknown = sorted(set(data) - _ACTION_FIELDS)
        if unknown:
            raise ValueError(f"unknown action field(s): {', '.join(unknown)}")
        raw_kind = data.get("kind")
        if raw_kind is None:
            raise ValueError("action requires a 'kind'")
        if isinstance(raw_kind, ActionKind):
            kind = raw_kind
        else:
            try:
                kind = ActionKind(str(raw_kind).strip().lower())
            except ValueError as exc:
                allowed = ", ".join(k.value for k in ActionKind)
                raise ValueError(
                    f"unknown action kind: {raw_kind!r} (expected one of {allowed})"
                ) from exc

        for name in _REQUIRED_FIELDS.get(kind, ()):
            raw = data.get(name)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                raise ValueError(f"action '{kind.value}' requires '{name}'")
        if kind is ActionKind.WAIT and not data.get("selector") and not data.get("timeout_ms"):
            raise ValueError("action 'wait' requires 'selector' or 'timeout_ms'")

        timeout_ms = _opt_int(data.get("timeout_ms"), "timeout_ms", minimum=1)
        if timeout_ms is not None:
            timeout_ms = min(timeout_ms, MAX_ACTION_TIMEOUT_MS)

        return cls(
            kind=kind,
            url=_opt_str(data.get("url"), "url"),
            selector=_opt_str(data.get("selector"), "selector"),
            text=_opt_str(data.get("text"), "text", strip=False),
            key=_opt_str(data.get("key"), "key"),
            timeout_ms=timeout_ms,
            full_page=bool(data.get("full_page", False)),
            expression=_opt_str(data.get("expression"), "expression", strip=False),
            delta_y=_opt_int(data.get("delta_y"), "delta_y"),
            value=_opt_str(data.get("value"), "value", strip=False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the browser action into a dictionary containing its defined fields.

        Returns:
            dict[str, Any]: The action kind and any configured action parameters.
        """
        out: dict[str, Any] = {"kind": self.kind.value}
        names = ("url", "selector", "text", "key", "timeout_ms", "expression", "delta_y", "value")
        for name in names:
            val = getattr(self, name)
            if val is not None:
                out[name] = val
        if self.full_page:
            out["full_page"] = True
        return out


@dataclass(frozen=True)
class ActionResult:
    """Outcome of one action, shaped for direct JSON return to an agent."""

    ok: bool
    kind: ActionKind
    session_id: str
    started_at: float
    duration_ms: float
    url: str | None = None
    title: str | None = None
    text: str | None = None
    screenshot_b64: str | None = None
    snapshot: tuple[dict[str, Any], ...] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the action outcome into a JSON-compatible dictionary.

        Returns:
            dict[str, Any]: The result fields, including optional output fields when available.
        """
        out: dict[str, Any] = {
            "ok": self.ok,
            "kind": self.kind.value,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
        }
        optional: dict[str, Any] = {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "screenshot_b64": self.screenshot_b64,
            "snapshot": list(self.snapshot) if self.snapshot is not None else None,
            "error": self.error,
        }
        for name, value in optional.items():
            if value is not None:
                out[name] = value
        return out


def _opt_str(value: Any, name: str, *, strip: bool = True) -> str | None:
    """Parse an optional string value with optional whitespace removal.

    Parameters:
        value (Any): The value to parse.
        name (str): Field name used in validation errors.
        strip (bool): Whether to remove leading and trailing whitespace.

    Returns:
        str | None: The processed string, or None when value is None.

    Raises:
        ValueError: If value is not a string or None.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{name}' must be a string")
    return value.strip() if strip else value


def _opt_int(value: Any, name: str, *, minimum: int | None = None) -> int | None:
    """
    Convert an optional numeric value to an integer and enforce a minimum when specified.

    Parameters:
        value (Any): The value to convert.
        name (str): The field name used in validation errors.
        minimum (int | None): The lowest permitted converted value.

    Returns:
        int | None: The converted integer, or None when value is None.

    Raises:
        ValueError: If value is not numeric or the converted value is below minimum.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{name}' must be a number")
    out = int(value)
    if minimum is not None and out < minimum:
        raise ValueError(f"'{name}' must be >= {minimum}")
    return out
