from __future__ import annotations

import json
import os
from importlib import import_module
from typing import Any
from urllib.parse import parse_qs

from kater.registry import tools_for_profile
from kater.settings import load_settings

MCP_INSTALL_MESSAGE = "MCP support is required. Install with `uv sync` in the Kater repo."


class McpUnavailableError(RuntimeError):
    """Raised when the MCP package is unavailable."""


def create_server(*, profile: str = "core") -> Any:
    try:
        fastmcp_module = import_module("mcp.server.fastmcp")
    except ModuleNotFoundError as exc:
        raise McpUnavailableError(MCP_INSTALL_MESSAGE) from exc

    server = fastmcp_module.FastMCP("kater-dev-tools")

    for tool in tools_for_profile(profile):
        server.tool(name=tool.name)(tool.handler)

    return server


def register_proxy_tools(server: Any, *, proxy: Any, profile: str) -> None:
    del profile
    proxy_enabled = os.environ.get("KATER_PROXY", "0") == "1"
    if not proxy_enabled:
        _register_proxy_status_tool(server)
        return

    try:
        for tool_def in proxy.list_tools():
            _make_proxy_tool(server, tool_def, proxy)
    except Exception:
        _register_proxy_status_tool(server)
        return

    _register_proxy_status_tool(server)


def _register_proxy_status_tool(server: Any) -> None:
    @server.tool(name="kater_proxy_status")
    def proxy_status() -> dict:
        return {
            "enabled": os.environ.get("KATER_PROXY", "0") == "1",
            "backends": 0,
            "tools": 0,
        }


def _make_proxy_tool(server: Any, tool_def: dict, proxy: Any) -> None:
    name = tool_def["name"]
    desc = tool_def["description"]

    def _handler(**kwargs):
        return proxy.call_tool(name, kwargs)

    _handler.__doc__ = desc
    server.tool(name=name, description=desc)(_handler)


class AuthASGIMiddleware:
    """ASGI middleware that gates the MCP transport with Kater auth.

    The MCP SSE surface is the real gateway door; without this every tool is
    reachable by anyone who can hit ``/sse``. When ``auth.mode == "none"`` the
    middleware is a pass-through (local-only default).
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        from kater.authgate import AuthContext, authenticate

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        decision = authenticate(
            AuthContext(
                settings=load_settings(),
                authorization_header=headers.get("authorization"),
                query_api_key=query.get("api_key", [None])[0],
            )
        )
        if not decision.allowed:
            await self._send_401(send, decision.error or "Unauthorized")
            return

        await self._app(scope, receive, send)

    @staticmethod
    async def _send_401(send: Any, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b'Bearer realm="kater"'),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def build_sse_app(*, profile: str = "core", use_proxy: bool = False) -> Any:
    """Return the FastMCP SSE ASGI app wrapped with Kater auth."""
    server = create_server(profile=profile)
    if use_proxy:
        from kater.proxy import get_proxy

        proxy = get_proxy()
        try:
            proxy.start(profile)
            register_proxy_tools(server, proxy=proxy, profile=profile)
        except Exception:
            _register_proxy_status_tool(server)
    return AuthASGIMiddleware(server.sse_app())


def serve(
    *,
    profile: str = "core",
    host: str = "127.0.0.1",
    port: int = 9090,
    use_proxy: bool = False,
) -> None:
    import uvicorn

    app = build_sse_app(profile=profile, use_proxy=use_proxy)
    uvicorn.run(app, host=host, port=port, log_level="warning")
