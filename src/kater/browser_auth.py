"""Opaque, process-local browser sessions; provider authorization is checked per request."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from urllib.parse import unquote, urlsplit

from kater.oidc import OidcCallbackResult, OidcError, load_oidc_config, userinfo

SESSION_COOKIE = "kater_session"
LOGIN_COOKIE = "kater_login"
_MAX_SESSIONS = 4096


@dataclass(frozen=True)
class BrowserSession:
    subject: str
    access_token: str
    expires_at: float


_sessions: dict[str, BrowserSession] = {}
_lock = threading.Lock()


def cookie_value(header: str | None, name: str) -> str:
    try:
        cookies = SimpleCookie(header or "")
        return cookies[name].value if name in cookies else ""
    except CookieError:
        return ""


def cookie(name: str, value: str, *, max_age: int, path: str = "/") -> str:
    cfg = load_oidc_config()
    secure = "; Secure" if (cfg.redirect_uri or "").startswith("https://") else ""
    return f"{name}={value}; Path={path}; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"


def safe_return_to(value: str) -> str:
    """Permit same-origin paths only, including after percent decoding by intermediaries."""
    check = value
    for _ in range(4):
        if (not check.startswith("/") or check.startswith("//")
                or "\\" in check or any(ord(c) < 32 or ord(c) == 127 for c in check)):
            return "/dashboard"
        try:
            parsed = urlsplit(check)
        except ValueError:
            return "/dashboard"
        if parsed.scheme or parsed.netloc:
            return "/dashboard"
        decoded = unquote(check)
        if decoded == check:
            return value
        check = decoded
    return "/dashboard"


def _key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(result: OidcCallbackResult) -> str:
    # Do not turn successful authentication into an implicit product entitlement.
    userinfo(result.access_token, result.subject)
    now = time.time()
    if result.expires_at <= now:
        raise OidcError("oidc_session_invalid")
    value = secrets.token_urlsafe(32)
    with _lock:
        for key in [key for key, session in _sessions.items() if session.expires_at <= now]:
            del _sessions[key]
        if len(_sessions) >= _MAX_SESSIONS:
            raise OidcError("oidc_busy")
        _sessions[_key(value)] = BrowserSession(
            result.subject, result.access_token, result.expires_at,
        )
    return value


def authenticate_session(value: str) -> BrowserSession:
    with _lock:
        session = _sessions.get(_key(value))
    if session is None or session.expires_at <= time.time():
        revoke_session(value)
        raise OidcError("oidc_session_invalid")
    try:
        userinfo(session.access_token, session.subject)
    except OidcError as exc:
        if exc.code in {"oidc_session_invalid", "oidc_entitlement_required"}:
            revoke_session(value)
        raise
    # Logout racing an in-flight upstream check must not restore authorization.
    with _lock:
        if _sessions.get(_key(value)) is not session:
            raise OidcError("oidc_session_invalid")
    return session


def revoke_session(value: str) -> None:
    with _lock:
        _sessions.pop(_key(value), None)


def reset_sessions() -> None:
    with _lock:
        _sessions.clear()


def valid_origin(origin: str | None) -> bool:
    callback = load_oidc_config().redirect_uri or ""
    parts = urlsplit(callback)
    return bool(origin and parts.netloc and origin == f"{parts.scheme}://{parts.netloc}")
