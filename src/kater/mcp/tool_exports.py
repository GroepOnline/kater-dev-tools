"""Disabled ChefGroep product MCP contract, separate from generic native/proxy tools.

No server, settings loader or extension discovery enables this registry. A future
transport must opt in explicitly and supply a ResourcePrincipal obtained from
IntrospectionClient for this resource. Principals are trusted server context, never
tool arguments. This module does not authenticate caller-supplied claim objects.

Only descriptor search is implemented locally. Backend operations return typed
unavailable errors until resource-scoped, read-only adapters have been reviewed.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeVar

from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kater.resource_auth import (
    AuthUnavailable,
    InsufficientScope,
    InvalidToken,
    ResourceAuthConfig,
    ResourceAuthDisabled,
    ResourcePrincipal,
)


class ProductExportError(Exception):
    """Stable public error without arguments, credentials or principal claims."""

    status_code = 400
    code = "product_export_error"

    def __init__(self) -> None:
        super().__init__(self.code)


class ProductExportsDisabled(ProductExportError):
    status_code = 503
    code = "product_exports_disabled"


class ToolNotExported(ProductExportError):
    status_code = 404
    code = "tool_not_exported"


class InvalidToolArguments(ProductExportError):
    code = "invalid_tool_arguments"


class _Input(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class _SearchInput(_Input):
    query: str = Field(min_length=1, max_length=256, pattern=r"\S")
    limit: int = Field(default=10, ge=1, le=25)


class _BrainQueryInput(_Input):
    query: str = Field(min_length=1, max_length=4096, pattern=r"\S")
    limit: int = Field(default=10, ge=1, le=25)


class _ShareListInput(_Input):
    limit: int = Field(default=25, ge=1, le=100)


class _ShareMetaInput(_Input):
    item_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class _OAuthSecurityScheme(BaseModel):
    type: Literal["oauth2"] = "oauth2"
    scopes: list[str]


class ProductToolDescriptor(BaseModel):
    """Wire descriptor preserving OAuth fields absent from the base MCP Tool type."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    description: str
    input_schema: dict[str, object] = Field(alias="inputSchema")
    annotations: ToolAnnotations
    security_schemes: list[_OAuthSecurityScheme] = Field(alias="securitySchemes")
    meta: dict[str, object] = Field(alias="_meta")


class BackendUnavailable(BaseModel):
    """An adapter is absent; this is never a successful empty backend response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["unavailable"] = "unavailable"
    code: Literal["backend_unavailable"] = "backend_unavailable"
    tool: str


@dataclass(frozen=True, slots=True)
class _Export:
    name: str
    description: str
    scope: str
    inputs: type[_Input]

    def descriptor(self) -> ProductToolDescriptor:
        # Build fresh schemas and metadata so caller mutations cannot alter policy.
        security = [{"type": "oauth2", "scopes": [self.scope]}]
        return ProductToolDescriptor.model_validate(
            {
                "name": self.name,
                "description": self.description,
                "inputSchema": self.inputs.model_json_schema(),
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
                "securitySchemes": security,
                "_meta": {"securitySchemes": security},
            }
        )


# This is the whole product allowlist. Never merge native tools, extension tools,
# profile catalogs or proxy-discovered backend names into it.
_EXPORTS = MappingProxyType(
    {
        export.name: export
        for export in (
            _Export(
                "kater_status",
                "Read Kater product status. Backend adapter unavailable.",
                "kater:read",
                _Input,
            ),
            _Export(
                "kater_tool_search",
                "Search the read-only product tools authorized for this request.",
                "kater:read",
                _SearchInput,
            ),
            _Export(
                "brain_query",
                "Read matching Brain knowledge. Backend adapter unavailable.",
                "brain:read",
                _BrainQueryInput,
            ),
            _Export(
                "brain_doctor",
                "Read Brain health without repairs. Backend adapter unavailable.",
                "brain:read",
                _Input,
            ),
            _Export(
                "chefshare_list",
                "Read the ChefShare item list. Backend adapter unavailable.",
                "chefshare:read",
                _ShareListInput,
            ),
            _Export(
                "chefshare_meta",
                "Read metadata for a ChefShare item. Backend adapter unavailable.",
                "chefshare:read",
                _ShareMetaInput,
            ),
        )
    }
)


_InputT = TypeVar("_InputT", bound=_Input)


def _validate_arguments(model: type[_InputT], arguments: object) -> _InputT:
    # Do not let Pydantic accept an already constructed model from a caller.
    if not isinstance(arguments, dict):
        raise InvalidToolArguments()
    try:
        return model.model_validate(arguments)
    except ValidationError:
        raise InvalidToolArguments() from None


def _result(payload: dict[str, object], *, is_error: bool) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structured_content=payload,
        is_error=is_error,
    )


class ProductToolRegistry:
    """Explicit opt-in seam for list, search and call; no live transport binding.

    `auth` is operator configuration. `principal` on each method is authenticated
    server context. The caller cannot choose a profile, principal, URL or token
    through any exported input schema. Neither environment variables nor native
    extension modules can expand the fixed allowlist.
    """

    def __init__(self, *, auth: ResourceAuthConfig | None = None, enabled: bool = False) -> None:
        self._auth = auth if auth is not None else ResourceAuthConfig()
        self._enabled = enabled is True

    def _require_principal(self, principal: ResourcePrincipal | None) -> ResourcePrincipal:
        if not self._enabled:
            raise ProductExportsDisabled()
        if not self._auth.enabled:
            raise ResourceAuthDisabled()
        if not isinstance(principal, ResourcePrincipal):
            raise InvalidToken()
        now = time.time()
        if not math.isfinite(now):
            raise AuthUnavailable()
        if (
            principal.issuer != self._auth.issuer
            or principal.audience != self._auth.resource
            or principal.plane != "internal"
            or principal.expires_at <= now
            or not principal.scopes.issubset(self._auth.allowed_scopes)
        ):
            raise InvalidToken()
        return principal

    def _authorize(self, name: str, principal: ResourcePrincipal | None) -> _Export:
        verified = self._require_principal(principal)
        export = _EXPORTS.get(name)
        if export is None:
            # Exact lookup only: no backend__tool, native or profile fallback.
            raise ToolNotExported()
        if export.scope not in verified.scopes:
            raise InsufficientScope()
        return export

    def list_tools(self, *, principal: ResourcePrincipal | None) -> list[ProductToolDescriptor]:
        self._require_principal(principal)
        visible: list[ProductToolDescriptor] = []
        for name in _EXPORTS:
            try:
                export = self._authorize(name, principal)
            except InsufficientScope:
                continue
            visible.append(export.descriptor())
        return visible

    def search_tools(
        self, arguments: object, *, principal: ResourcePrincipal | None
    ) -> list[ProductToolDescriptor]:
        # Auth precedes input validation, including on empty and unknown queries.
        descriptors = self.list_tools(principal=principal)
        query = _validate_arguments(_SearchInput, arguments)
        needle = query.query.casefold()
        return [
            tool for tool in descriptors if needle in f"{tool.name} {tool.description}".casefold()
        ][: query.limit]

    def call_tool(
        self,
        name: str,
        arguments: object,
        *,
        principal: ResourcePrincipal | None,
    ) -> CallToolResult:
        export = self._authorize(name, principal)
        _validate_arguments(export.inputs, arguments)
        if export.name == "kater_tool_search":
            tools = self.search_tools(arguments, principal=principal)
            return _result(
                {
                    "tools": [
                        tool.model_dump(mode="json", by_alias=True, exclude_none=True)
                        for tool in tools
                    ]
                },
                is_error=False,
            )
        unavailable = BackendUnavailable(tool=export.name)
        return _result(unavailable.model_dump(mode="json"), is_error=True)
