"""Composition of the MCP HTTP transports."""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from starlette.applications import Starlette


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

    return Starlette(routes=routes, lifespan=lifespan)
