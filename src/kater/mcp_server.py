from __future__ import annotations

from importlib import import_module
from typing import Any

from kater.registry import tools_for_profile

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


def serve(*, profile: str = "core") -> None:
    create_server(profile=profile).run()
