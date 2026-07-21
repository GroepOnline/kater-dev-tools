"""The single authentication gate for every Kater transport.

Auth policy used to be duplicated across three callers: the REST handler
(`api._authenticate`), the MCP SSE middleware (`mcp_server.AuthASGIMiddleware`)
and the WebSocket handler (`websocket._check_auth`). Each re-implemented the
public-path allowlist, the `mode == "none"` bypass, and credential extraction.

This module is the one place the rule lives. Transports only translate their
request shape into an `AuthContext`; the decision logic is here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kater.settings import KaterSettings, check_auth

# Endpoints that bootstrap auth itself (OAuth) or report liveness must stay
# reachable without credentials. Only meaningful for the REST API transport.
PUBLIC_API_PATHS = frozenset({"/health", "/authorize", "/token", "/register", "/revoke"})
PUBLIC_API_PREFIXES = ("/.well-known",)
DASHBOARD_PUBLIC_PATHS = frozenset({"/", "/dashboard"})


@dataclass(frozen=True)
class AuthContext:
    settings: KaterSettings
    authorization_header: str | None = None
    query_api_key: str | None = None
    # Set by the REST API transport to enable the public-path allowlist.
    # Transports without public paths (MCP, WebSocket) leave it None.
    path: str | None = None


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


def authenticate(ctx: AuthContext) -> AuthDecision:
    """Decide whether a request may proceed.

    Invariants:
    - A REST request to a public path is always allowed.
    - ``mode == "none"`` allows everything (local-only default).
    - ``apikey`` / ``oauth`` delegate credential verification to
      :func:`kater.settings.check_auth` (constant-time key compare, token
      validation), so verification logic stays in one place.
    - An unknown auth mode is denied (fail closed).
    """
    if ctx.path is not None and _is_public_path(ctx.path):
        return AuthDecision(True)

    ok, error = check_auth(ctx.settings, ctx.authorization_header, ctx.query_api_key)
    return AuthDecision(ok, error)
