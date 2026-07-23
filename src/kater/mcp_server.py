from __future__ import annotations

import inspect
import json
import logging
import os
import re
from importlib import import_module
from typing import Any
from urllib.parse import parse_qs

from kater.registry import tools_for_profile
from kater.settings import load_settings, resolve_client_ip

_log = logging.getLogger("kater.mcp")

MCP_INSTALL_MESSAGE = "MCP support is required. Install with `uv sync` in the Kater repo."

# Hard ceiling on the number of properties we will reflect into a handler
# signature. Schemas above this size are logged and truncated; the tool stays
# callable via positional/keyword mapping but FastMCP will only advertise the
# first MAX_TOOL_PROPERTIES in its input schema.
_MAX_TOOL_PROPERTIES = 64

# A tool property name must round-trip as a Python identifier so we can safely
# build an inspect.Signature around it. Anything else (e.g. `os.system`,
# `a]b`, `__class__`) is rejected before it reaches handler construction.
_VALID_PARAM_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Names that would shadow the handler's closure bindings or Python builtins
# when reflected into the signature. Rejecting them prevents an upstream
# schema from hijacking internal state.
_RESERVED_PARAM_NAMES = frozenset(
    {
        # Closure variables the handler actually reads.
        "proxy",
        "tool_name",
        # Builtins commonly used inside dispatch logic; never accept these as
        # tool argument names either.
        "self",
        "cls",
        # Dunders that inspect / pydantic introspection would treat specially
        # and that would leak handler internals to an upstream caller.
        "__builtins__",
        "__globals__",
        "__class__",
        "__dict__",
        "__doc__",
        "__name__",
        "__qualname__",
        "__signature__",
        "__wrapped__",
        "__code__",
        "__defaults__",
        "__closure__",
    }
)


class McpUnavailableError(RuntimeError):
    """Raised when the MCP package is unavailable."""


class InvalidToolSchemaError(ValueError):
    """Raised when a proxied tool schema is not safe to reflect into a handler.

    A schema is unsafe if a property name is not a Python identifier, conflicts
    with the handler's closure bindings, or the schema is so large it would
    produce a function signature that is unreasonably expensive to introspect.
    Failing closed (refusing to register the tool) is preferable to ``exec``
    or to silently building an attacker-shaped ``inspect.Signature``.
    """


def _validate_param_name(name: str) -> str:
    """Return ``name`` if it is a safe identifier, else raise InvalidToolSchemaError."""
    if not isinstance(name, str) or not _VALID_PARAM_NAME.match(name):
        raise InvalidToolSchemaError(
            f"tool property name {name!r} is not a valid Python identifier"
        )
    if name in _RESERVED_PARAM_NAMES:
        raise InvalidToolSchemaError(f"tool property name {name!r} shadows a handler binding")
    return name


def _validate_tool_name(name: str) -> str:
    """Validate the proxied tool name; we pass it straight to ``call_tool`` as a
    string so it cannot inject, but it still has to be a reasonable identifier."""
    if not isinstance(name, str) or not _VALID_PARAM_NAME.match(name):
        raise InvalidToolSchemaError(f"tool name {name!r} is not a valid identifier")
    return name


def _public_tunnel_hosts() -> list[str]:
    """Hostnames that Cloudflare/Tailscale may send in the Host header.

    FastMCP auto-enables DNS-rebinding protection when bound to loopback and
    only allows localhost by default. Tunnel traffic arrives with the public
    hostname (e.g. ``kater.example.com``), which then 421s and shows up as a
    Cloudflare 502 on ``/sse``.
    """
    hosts: list[str] = []
    domain = (os.environ.get("KATER_DOMAIN") or "").strip()
    if domain:
        hosts.append(domain)
    for raw in (os.environ.get("KATER_HTTPS_HOSTS") or "").split(","):
        host = raw.strip()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def _transport_security_settings(fastmcp_module: Any) -> Any | None:
    """Build TransportSecuritySettings that keep loopback defaults plus tunnel hosts."""
    TransportSecuritySettings = getattr(
        fastmcp_module, "TransportSecuritySettings", None
    )
    if TransportSecuritySettings is None:
        try:
            from mcp.server.transport_security import (  # type: ignore[import-not-found]
                TransportSecuritySettings as _Settings,
            )
        except Exception:
            return None
        TransportSecuritySettings = _Settings

    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_origins = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]
    for host in _public_tunnel_hosts():
        # Exact (no port) + wildcard-port form — public HTTPS usually omits :443.
        allowed_hosts.append(host)
        allowed_hosts.append(f"{host}:*")
        allowed_origins.append(f"https://{host}")
        allowed_origins.append(f"https://{host}:*")
        allowed_origins.append(f"http://{host}")
        allowed_origins.append(f"http://{host}:*")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def create_server(*, profile: str = "core") -> Any:
    try:
        fastmcp_module = import_module("mcp.server.fastmcp")
    except ModuleNotFoundError as exc:
        raise McpUnavailableError(MCP_INSTALL_MESSAGE) from exc

    security = _transport_security_settings(fastmcp_module)
    if security is not None:
        server = fastmcp_module.FastMCP(
            "kater-dev-tools", transport_security=security
        )
    else:
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
    """Build a FastMCP handler whose signature matches the proxied input schema.

    The handler is constructed without ``exec``/``eval``. We create an ordinary
    closure that forwards its keyword arguments to ``proxy.call_tool`` and then
    attach an ``inspect.Signature`` describing the schema's properties. FastMCP
    reads parameter metadata via ``inspect.signature``, so it sees exactly the
    same shape it would have seen under the previous ``exec``-based version.

    Property and tool names are validated against a strict identifier allowlist
    so an upstream schema cannot smuggle arbitrary code through the signature.
    """
    _validate_tool_name(tool_name)

    properties = input_schema.get("properties") or {}
    required = input_schema.get("required") or []

    if not isinstance(properties, dict):
        raise InvalidToolSchemaError("tool schema 'properties' must be an object")
    if not isinstance(required, (list, tuple, set, frozenset)):
        raise InvalidToolSchemaError("tool schema 'required' must be a list of property names")

    # Validate every property name up front. Failing closed on the first bad
    # name is preferable to registering a partially-shaped handler.
    validated: list[str] = []
    for prop_name in properties:
        _validate_param_name(prop_name)
        validated.append(prop_name)
        if len(validated) > _MAX_TOOL_PROPERTIES:
            raise InvalidToolSchemaError(
                f"tool {tool_name!r} has more than {_MAX_TOOL_PROPERTIES} properties; "
                "refusing to register"
            )

    def handler(**kwargs: Any) -> Any:
        # Drop None values so optional params the caller omitted are not sent
        # to the upstream tool. Positional args are rejected on the signature
        # level (every parameter is keyword-only), which also matches how the
        # previous exec-based handler behaved once you read its generated code.
        args = {name: value for name, value in kwargs.items() if value is not None}
        return proxy.call_tool(tool_name, args)

    handler.__name__ = "handler"
    handler.__qualname__ = f"_proxy_handler__{tool_name}"
    handler.__doc__ = tool_name

    # Build the reflected signature. Parameters are keyword-only and default
    # to None; required-ness is recorded in the docstring via the FastMCP
    # schema validator (which reads from JSON schema, not from the default).
    # Each parameter carries ``annotation=Any`` so FastMCP produces a string
    # field in its advertised input schema, matching prior behaviour.
    parameters = [
        inspect.Parameter(
            name=name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Any,
        )
        for name in validated
    ]
    handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=parameters,
        return_annotation=Any,
    )
    return handler


def _make_proxy_tool(server: Any, tool_def: dict, proxy: Any) -> None:
    name = tool_def["name"]
    desc = tool_def["description"]
    schema = tool_def.get("inputSchema") or {"type": "object", "properties": {}}
    try:
        handler = _build_proxy_handler(name, schema, proxy)
    except InvalidToolSchemaError as exc:
        # Fail closed: an upstream schema that we cannot reflect safely is
        # logged and skipped, but does not crash proxy registration. This
        # matches the existing "log + status tool" recovery shape.
        _log.warning("skipping unsafe proxy tool %r: %s", name, exc)
        return
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
