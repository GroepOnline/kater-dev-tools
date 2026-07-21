from __future__ import annotations

import json
import logging
from importlib import import_module
from typing import Any
from urllib.parse import parse_qs

from kater.registry import tools_for_profile
from kater.settings import load_settings, resolve_client_ip

_log = logging.getLogger("kater.mcp")

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
    try:
        for tool_def in proxy.list_tools():
            _make_proxy_tool(server, tool_def, proxy)
    except Exception as exc:
        _log.warning("proxy tool registration failed: %s", exc)
        _register_proxy_status_tool(server, proxy=proxy, enabled=False)
        return

    _register_proxy_status_tool(server, proxy=proxy, enabled=True)


def _register_proxy_status_tool(
    server: Any, *, proxy: Any | None = None, enabled: bool = False
) -> None:
    @server.tool(name="kater_proxy_status")
    def proxy_status() -> dict:
        if proxy is None:
            return {"enabled": enabled, "backends": 0, "tools": 0}
        return {
            "enabled": enabled,
            "backends": proxy.backend_count(),
            "tools": proxy.tool_count(),
        }


def _build_proxy_handler(
    tool_name: str,
    input_schema: dict[str, Any],
    proxy: Any,
) -> Any:
    """Build a FastMCP handler whose signature matches the proxied input schema."""
    properties = input_schema.get("properties") or {}
    required = set(input_schema.get("required") or [])

    if not properties:

        def handler() -> Any:
            return proxy.call_tool(tool_name, {})

        handler.__doc__ = tool_name
        return handler

    params: list[str] = []
    body: list[str] = ["    args: dict[str, Any] = {}"]
    required_params: list[str] = []
    optional_params: list[str] = []
    for prop_name in properties:
        if prop_name in required:
            required_params.append(prop_name)
            body.append(f"    if {prop_name} is not None:")
            body.append(f"        args[{prop_name!r}] = {prop_name}")
        else:
            optional_params.append(f"{prop_name}=None")
            body.append(f"    if {prop_name} is not None:")
            body.append(f"        args[{prop_name!r}] = {prop_name}")

    params = required_params + optional_params

    body.append(f"    return proxy.call_tool({tool_name!r}, args)")
    source = f"def handler({', '.join(params)}):\n" + "\n".join(body)
    namespace: dict[str, Any] = {"Any": Any, "proxy": proxy}
    exec(source, namespace)  # noqa: S102 — schema-driven signature; props are catalog-controlled
    handler = namespace["handler"]
    handler.__doc__ = tool_name
    return handler


def _make_proxy_tool(server: Any, tool_def: dict, proxy: Any) -> None:
    name = tool_def["name"]
    desc = tool_def["description"]
    schema = tool_def.get("inputSchema") or {"type": "object", "properties": {}}
    handler = _build_proxy_handler(name, schema, proxy)
    server.tool(name=name, description=desc)(handler)


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

        from kater.api import check_transport_rate_limit
        from kater.authgate import AuthContext, authenticate

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        # Throttle the tool surface (/sse + MCP POST) the same way REST is.
        client = scope.get("client")
        peer_ip = client[0] if client else "unknown"
        client_ip = resolve_client_ip(headers.get("x-forwarded-for"), peer_ip)
        if not check_transport_rate_limit(client_ip):
            await self._send_429(send)
            return

        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        path = scope.get("path") or "/"
        decision = authenticate(
            AuthContext(
                settings=load_settings(),
                authorization_header=headers.get("authorization"),
                query_api_key=query.get("api_key", [None])[0],
                path=path,
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

    @staticmethod
    async def _send_429(send: Any) -> None:
        body = json.dumps({"error": "Rate limit exceeded."}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
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
        except Exception as exc:
            _log.warning("proxy startup failed: %s", exc)
            _register_proxy_status_tool(server)
    from kater.gateway import ApiProxyMiddleware

    inner = AuthASGIMiddleware(server.sse_app())
    return ApiProxyMiddleware(inner)


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
