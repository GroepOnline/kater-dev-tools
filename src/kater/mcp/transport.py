"""Composition of the MCP HTTP transports."""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware

_SSE_ROOT = "/sse"
_STREAMABLE_ROOT = "/mcp"
_STREAMABLE_METHODS = frozenset({"POST", "DELETE"})


class StreamableHttpOnSseMiddleware:
    """Serve Streamable HTTP on the SSE URL for clients that probe POST first.

    Cursor (and other MCP HTTP clients) POST Streamable HTTP to the configured
    URL even when that URL is ``/sse``. FastMCP's SSE route is GET-only, so
    that probe returns 405, Cursor falls back to a GET SSE session, and a later
    ``tools/call`` on an idle or reconnected session surfaces as JSON-RPC
    ``-32602 Invalid request parameters``. Rewriting POST/DELETE ``/sse`` to
    ``/mcp`` lets the first probe succeed and keeps ``tools/call`` on a
    negotiated Streamable HTTP session. GET ``/sse`` stays the legacy SSE
    stream.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path = scope.get("path") or ""
            method = (scope.get("method") or "").upper()
            if path.rstrip("/") == _SSE_ROOT and method in _STREAMABLE_METHODS:
                scope = dict(scope)
                scope["path"] = _STREAMABLE_ROOT
                raw = scope.get("raw_path")
                suffix = b""
                if isinstance(raw, (bytes, bytearray)) and raw.startswith(b"/sse"):
                    suffix = bytes(raw[4:])
                scope["raw_path"] = _STREAMABLE_ROOT.encode("ascii") + suffix
        await self.app(scope, receive, send)


def combine_mcp_transports(server: Any, *, security: Any | None) -> Any:
    """Expose SSE and (when supported) streamable HTTP from one FastMCP server."""
    transport_kwargs: dict[str, Any] = {}
    if security is not None:
        transport_kwargs["transport_security"] = security

    sse_starlette = server.sse_app(**transport_kwargs)
    streamable_factory = getattr(server, "streamable_http_app", None)
    if not callable(streamable_factory):
        return sse_starlette

    stream_starlette = streamable_factory(**transport_kwargs)
    routes = list(sse_starlette.routes) + list(stream_starlette.routes)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # The transport applications own their lifecycle (including the session
        # manager in FastMCP). Enter both contexts rather than copying only the
        # routes, which would silently discard their startup/shutdown hooks.
        async with AsyncExitStack() as stack:
            for transport_app in (sse_starlette, stream_starlette):
                router = getattr(transport_app, "router", None)
                context = getattr(router, "lifespan_context", None)
                if callable(context):
                    await stack.enter_async_context(context(transport_app))
            yield

    return Starlette(
        routes=routes,
        lifespan=lifespan,
        middleware=[Middleware(StreamableHttpOnSseMiddleware)],
    )
