from __future__ import annotations

import os
from importlib import import_module
from typing import Any

from kater.registry import tools_for_profile

MCP_INSTALL_MESSAGE = "MCP support is required. Install with `uv sync` in the Kater repo."


class McpUnavailableError(RuntimeError):
    """Raised when the MCP package is unavailable."""


def create_server(*, profile: str = "core", use_proxy: bool = False) -> Any:
    try:
        fastmcp_module = import_module("mcp.server.fastmcp")
    except ModuleNotFoundError as exc:
        raise McpUnavailableError(MCP_INSTALL_MESSAGE) from exc

    server = fastmcp_module.FastMCP("kater-dev-tools")

    for tool in tools_for_profile(profile):
        server.tool(name=tool.name)(tool.handler)

    if use_proxy:
        _register_proxy_tools(server, profile)

    return server


def _register_proxy_tools(server: Any, profile: str) -> None:
    proxy_enabled = os.environ.get("KATER_PROXY", "0") == "1"
    if not proxy_enabled:
        _register_proxy_status_tool(server)
        return

    from kater.proxy import get_proxy

    proxy = get_proxy()
    try:
        proxy.start(profile)
    except Exception:
        _register_proxy_status_tool(server)
        return

    for tool_def in proxy.list_tools():
        _make_proxy_tool(server, tool_def, proxy)

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


def serve(*, profile: str = "core") -> None:
    create_server(profile=profile).run()
