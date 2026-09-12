"""Dedicated, stateless Streamable HTTP MCP for the ChefGroep product surface."""

from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from http.client import HTTPConnection, HTTPException
from typing import Any
from urllib.parse import urlsplit

from mcp.server.auth.routes import build_resource_metadata_url
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import Server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from pydantic import AnyHttpUrl, Field, SerializeAsAny, UrlConstraints

from kater.mcp.tool_exports import ProductExportError, ProductToolRegistry
from kater.resource_auth import (
    InsufficientScope,
    IntrospectionClient,
    InvalidToken,
    ResourceAuthConfig,
    ResourceAuthError,
    ResourcePrincipal,
)

_request_principal: ContextVar[ResourcePrincipal | None] = ContextVar(
    "chefgroep_product_principal", default=None
)


class _ExactIssuerUrl(AnyHttpUrl):
    # The Auth issuer is an exact origin. Pydantic's default trailing slash would
    # change the discovery contract and fail comparison with Auth's own metadata.
    _constraints = UrlConstraints(allowed_schemes=["https"], preserve_empty_path=True)


class ProductMCPTool(Tool):
    """MCP tool descriptor with the current OpenAI security extension."""

    security_schemes: list[dict[str, object]] = Field(alias="securitySchemes")


class ProductListToolsResult(ListToolsResult):
    """Preserve extension fields when serialized through the MCP result model."""

    tools: list[SerializeAsAny[Tool]]


def _principal_from_request() -> ResourcePrincipal:
    principal = _request_principal.get()
    if principal is None:
        raise InvalidToken()
    return principal


class ProductAuthMiddleware:
    """Authenticate every MCP request through Auth without positive caching."""

    def __init__(self, app: Any, config: ResourceAuthConfig) -> None:
        self._app = app
        self._client = IntrospectionClient(config)
        self._metadata_url = str(build_resource_metadata_url(AnyHttpUrl(config.resource)))

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        from kater.api import check_transport_rate_limit
        from kater.settings import resolve_client_ip

        # Reuse the REST/private MCP quota and forwarding trust policy before
        # spending an Auth request. A caller cannot rotate a forged XFF header
        # to evade its peer-IP quota.
        client = scope.get("client")
        peer_ip = client[0] if client else "unknown"
        client_ip = resolve_client_ip(headers.get("x-forwarded-for"), peer_ip)
        if not check_transport_rate_limit(client_ip):
            await self._error(send, 429, "rate_limit_exceeded", include_challenge=False)
            return
        if scope.get("method") == "GET" and scope.get("path") == urlsplit(self._metadata_url).path:
            await self._app(scope, receive, send)
            return
        authorization = headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            await self._error(send, 401, "invalid_token")
            return
        try:
            principal = await asyncio.to_thread(
                self._client.introspect,
                authorization[7:],
            )
        except InvalidToken:
            await self._error(send, 401, "invalid_token")
            return
        except ResourceAuthError:
            await self._error(send, 503, "auth_unavailable", include_challenge=False)
            return
        marker = _request_principal.set(principal)
        try:
            await self._app(scope, receive, send)
        finally:
            _request_principal.reset(marker)

    async def _error(
        self,
        send: Any,
        status: int,
        code: str,
        *,
        include_challenge: bool = True,
    ) -> None:
        body = json.dumps({"error": code}, separators=(",", ":")).encode()
        headers = [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]
        if include_challenge:
            challenge = (
                f'Bearer resource_metadata="{self._metadata_url}", error="{code}", '
                f'error_description="{code}"'
            )
            headers.append((b"www-authenticate", challenge.encode("ascii")))
        headers.append((b"content-length", str(len(body)).encode("ascii")))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


class OpenAIToolSecurityMiddleware:
    """Mirror tool security metadata into the current OpenAI wire extension.

    The Python MCP SDK currently retains ``_meta.securitySchemes`` but drops the
    documented top-level ``securitySchemes`` extension while serializing
    ``tools/list``. Keep both forms on the actual wire until the SDK model owns
    the extension directly.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        start: dict[str, Any] | None = None
        chunks: list[bytes] = []

        async def capture(message: dict[str, Any]) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                content_type = next(
                    (
                        value.decode("latin-1")
                        for key, value in message.get("headers", [])
                        if key.lower() == b"content-type"
                    ),
                    "",
                )
                if content_type.split(";", 1)[0].strip().lower() != "application/json":
                    await send(message)
                    return
                start = message
                return
            if message["type"] != "http.response.body" or start is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return
            body = b"".join(chunks)
            headers = list(start.get("headers", []))
            content_type = next(
                (
                    value.decode("latin-1")
                    for key, value in headers
                    if key.lower() == b"content-type"
                ),
                "",
            )
            if content_type.split(";", 1)[0].strip().lower() == "application/json":
                try:
                    payload = json.loads(body)
                    tools = payload.get("result", {}).get("tools", [])
                    if isinstance(tools, list):
                        for tool in tools:
                            security = tool.get("_meta", {}).get("securitySchemes")
                            if security is not None:
                                tool["securitySchemes"] = security
                        body = json.dumps(payload, separators=(",", ":")).encode()
                except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                    pass
            headers = [item for item in headers if item[0].lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode("ascii")))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self._app(scope, receive, capture)


def _wire_tool(descriptor: Any) -> ProductMCPTool:
    payload = descriptor.model_dump(mode="json", by_alias=True, exclude_none=True)
    return ProductMCPTool.model_validate(payload)


def _error_result(
    error: ProductExportError | ResourceAuthError, metadata_url: str
) -> CallToolResult:
    payload = {"error": error.code}
    meta: dict[str, Any] | None = None
    if isinstance(error, (InvalidToken, InsufficientScope)):
        oauth_error = "invalid_token" if isinstance(error, InvalidToken) else "insufficient_scope"
        challenge = (
            f'Bearer resource_metadata="{metadata_url}", error="{oauth_error}", '
            f'error_description="{error.code}"'
        )
        meta = {"mcp/www_authenticate": [challenge]}
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structured_content=payload,
        is_error=True,
        _meta=meta,
    )


def create_product_server(config: ResourceAuthConfig) -> Server[Any]:
    """Create the fixed six-tool product server; no native/proxy registry is consulted."""
    registry = ProductToolRegistry(auth=config, enabled=True)
    metadata_url = str(build_resource_metadata_url(AnyHttpUrl(config.resource)))

    async def list_tools(_ctx: Any, _params: Any) -> ProductListToolsResult:
        principal = _principal_from_request()
        return ProductListToolsResult(
            tools=[_wire_tool(item) for item in registry.list_tools(principal=principal)]
        )

    async def call_tool(_ctx: Any, params: Any) -> CallToolResult:
        try:
            return await asyncio.to_thread(
                registry.call_tool,
                params.name,
                params.arguments or {},
                principal=_principal_from_request(),
            )
        except (ProductExportError, ResourceAuthError) as error:
            return _error_result(error, metadata_url)

    return Server(
        "chefgroep-workspace",
        version="1",
        instructions="Read-only ChefGroep workspace tools for Kater, Brain and ChefShare.",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def build_product_mcp_app(config: ResourceAuthConfig) -> Any:
    """Build the public `/mcp` app with OAuth metadata and per-request introspection."""
    if not config.enabled or urlsplit(config.resource).path != "/mcp":
        raise ValueError("Enabled product resource must use the exact /mcp path")
    if (
        str(AnyHttpUrl(config.resource)) != config.resource
        or str(_ExactIssuerUrl(config.issuer)) != config.issuer
    ):
        raise ValueError("Product OAuth URLs must match their canonical wire representation")
    server = create_product_server(config)
    auth = AuthSettings(
        issuer_url=_ExactIssuerUrl(config.issuer),
        resource_server_url=AnyHttpUrl(config.resource),
        required_scopes=list(config.allowed_scopes),
    )
    host = urlsplit(config.resource).hostname
    if host is None:
        raise ValueError("resource hostname is required")
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[host, f"{host}:*", "127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=[f"https://{host}", f"https://{host}:*"],
    )
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        auth=auth,
        transport_security=security,
    )
    return ProductAuthMiddleware(OpenAIToolSecurityMiddleware(app), config)


def product_mcp_ready(config: ResourceAuthConfig, host: str, port: int) -> bool:
    """Probe metadata, bearer enforcement and Auth using a deliberately invalid token."""
    if host in {"0.0.0.0", "::", ""}:  # noqa: S104 — normalize wildcard for local probe
        host = "::1" if host == "::" else "127.0.0.1"
    connection = HTTPConnection(host, port, timeout=1.0)
    try:
        connection.request("GET", "/.well-known/oauth-protected-resource/mcp")
        response = connection.getresponse()
        payload = json.loads(response.read(16385))
        if (
            response.status != 200
            or not isinstance(payload, dict)
            or (
                payload.get("resource") != config.resource
                or payload.get("authorization_servers") != [config.issuer]
                or payload.get("scopes_supported") != list(config.allowed_scopes)
            )
        ):
            return False
        connection.request("POST", "/mcp", body=b"{}", headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        response.read(16385)
        if response.status != 401 or str(
            build_resource_metadata_url(AnyHttpUrl(config.resource))
        ) not in (response.getheader("WWW-Authenticate", "")):
            return False
        return IntrospectionClient(config).check_readiness()
    except (OSError, HTTPException, ValueError, ResourceAuthError):
        return False
    finally:
        connection.close()
