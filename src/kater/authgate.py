"""The single authentication gate for every Kater transport.

Auth policy used to be duplicated across three callers: the REST handler
(`api._authenticate`), the MCP SSE middleware (`mcp_server.AuthASGIMiddleware`)
and the WebSocket handler (`websocket._check_auth`). Each re-implemented the
public-path allowlist, the `mode == "none"` bypass, and credential extraction.

This module is the one place the rule lives. Transports only translate their
request shape into an `AuthContext`; the decision logic is here.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from kater.control_plane.contexts import ContextRecord
from kater.control_plane.tokens import verify_token
from kater.settings import KaterSettings, check_auth

# Endpoints that bootstrap auth itself (OAuth) or report liveness must stay
# reachable without credentials. Only meaningful for the REST API transport.
PUBLIC_API_PATHS = frozenset(
    {
        "/health",
        "/health/live",
        "/health/ready",
        "/authorize",
        "/token",
        "/register",
        "/revoke",
        "/api/mcp/oauth/callback",
    }
)
PUBLIC_API_PREFIXES = ("/.well-known",)
DASHBOARD_PUBLIC_PATHS = frozenset(
    {
        "/",
        "/dashboard",
        "/studio",
        "/studio/assets/studio.js",
        "/studio/assets/studio.css",
    }
)


@dataclass(frozen=True)
class RequestIdentity:
    """Authenticated caller attributes derived from a scoped context token."""

    principal_id: str | None = None
    context_id: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    # None = unrestricted; empty frozenset = deny all capabilities.
    allowed_capabilities: frozenset[str] | None = None


_current_identity: ContextVar[RequestIdentity | None] = ContextVar(
    "kater_request_identity", default=None
)


@dataclass(frozen=True)
class AuthContext:
    settings: KaterSettings
    authorization_header: str | None = None
    query_api_key: str | None = None
    # Set by the REST API transport to enable the public-path allowlist.
    # Transports without public paths (MCP, WebSocket) leave it None.
    path: str | None = None
    # Optional signed context token (``X-Kater-Context``).
    context_header: str | None = None


@dataclass(frozen=True)
class AuthDecision:
    allowed: bool
    error: str | None = None
    identity: Any | None = None


def _is_public_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in PUBLIC_API_PATHS:
        return True
    return any(normalized.startswith(prefix) for prefix in PUBLIC_API_PREFIXES)


def should_proxy_to_api(path: str) -> bool:
    """HTTP paths owned by the REST API that the MCP gateway must forward."""
    normalized = path.rstrip("/") or "/"
    if normalized in DASHBOARD_PUBLIC_PATHS:
        return True
    if normalized.startswith("/api/"):
        return True
    return _is_public_path(path)


def _extract_bearer(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def identity_from_record(record: ContextRecord) -> RequestIdentity:
    """Map a live context record into a request identity.

    An empty ``allowed_capabilities`` on the stored context means unrestricted
    (the create default); a non-empty set is enforced as an allowlist.
    """
    allowed = record.allowed_capabilities if record.allowed_capabilities else None
    return RequestIdentity(
        principal_id=record.principal_id,
        context_id=record.context_id,
        scopes=frozenset(record.scopes),
        allowed_capabilities=allowed,
    )


def capability_allowed(name: str, allowed: frozenset[str] | None) -> bool:
    """Return True when ``name`` is permitted by an optional capability allowlist.

    ``None`` means unrestricted. Exact match, ``prefix.*`` globs, and dotted
    prefix entries (``kater.profiles`` matches ``kater.profiles.list``) are
    accepted.
    """
    if allowed is None:
        return True
    if name in allowed:
        return True
    for entry in allowed:
        if not entry:
            continue
        if entry.endswith("*") and name.startswith(entry[:-1]):
            return True
        if name.startswith(entry + "."):
            return True
    return False


def resolve_identity_from_headers(
    context_header: str | None,
    authorization_header: str | None,
) -> tuple[RequestIdentity, str | None]:
    """Resolve a context token into an identity.

    Returns ``(identity, error)``. An explicit ``X-Kater-Context`` that fails
    verification yields an error; a Bearer value that is not a context token is
    ignored (it may be an API key / OAuth access token).
    """
    explicit = (context_header or "").strip() or None
    if explicit:
        record = verify_token(explicit)
        if record is None:
            return RequestIdentity(), "Invalid context token."
        return identity_from_record(record), None

    bearer = _extract_bearer(authorization_header)
    if bearer and bearer.count(".") == 1:
        record = verify_token(bearer)
        if record is not None:
            return identity_from_record(record), None
    return RequestIdentity(), None


def resolve_request_identity(req: Any) -> RequestIdentity:
    """Read context identity from a REST :class:`~kater.api.models.Request`."""
    header = req.header("x-kater-context") if hasattr(req, "header") else None
    authorization = req.header("authorization") if hasattr(req, "header") else None
    identity, _error = resolve_identity_from_headers(header, authorization)
    return identity


def get_request_identity() -> RequestIdentity:
    """Return the identity bound to the current request context, if any."""
    return _current_identity.get() or RequestIdentity()


def set_request_identity(identity: RequestIdentity | None) -> None:
    """Bind (or clear) the request-scoped identity for downstream callers."""
    _current_identity.set(identity)


def authenticate(ctx: AuthContext) -> AuthDecision:
    """Decide whether a request may proceed.

    Invariants:
    - A REST request to a public path is always allowed.
    - ``mode == "none"`` allows everything (local-only default).
    - ``apikey`` / ``oauth`` delegate credential verification to
      :func:`kater.settings.check_auth` (constant-time key compare, token
      validation), so verification logic stays in one place.
    - An unknown auth mode is denied (fail closed).
    - When a context token is present (``X-Kater-Context`` or a Bearer that
      verifies as one), :attr:`AuthDecision.identity` is populated.
    """
    if ctx.path is not None and _is_public_path(ctx.path):
        identity, ctx_error = resolve_identity_from_headers(
            ctx.context_header, ctx.authorization_header
        )
        if ctx_error:
            set_request_identity(None)
            return AuthDecision(False, ctx_error)
        set_request_identity(identity)
        return AuthDecision(True, identity=identity)

    ok, error = check_auth(ctx.settings, ctx.authorization_header, ctx.query_api_key)
    if not ok:
        set_request_identity(None)
        return AuthDecision(ok, error)

    identity, ctx_error = resolve_identity_from_headers(
        ctx.context_header, ctx.authorization_header
    )
    if ctx_error:
        set_request_identity(None)
        return AuthDecision(False, ctx_error)
    set_request_identity(identity)
    return AuthDecision(True, identity=identity)
