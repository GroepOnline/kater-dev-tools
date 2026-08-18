from __future__ import annotations

import contextlib
import threading
import time
from typing import Any

from kater.proxy.models import BackendStatus, ProxiedTool

# Newest-first MCP protocol versions this gateway speaks. 2025-06-18 is the
# current stable MCP release (streamable HTTP transport, elicitation, form
# filling); older servers negotiate down from it in the initialize response.
# The gateway advertises the newest version and accepts any supported version
# the server answers with, instead of pinning the legacy 2024-11-05.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
NEWEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


class BackendOperationalError(Exception):
    """Transport/protocol failure distinct from a JSON-RPC business error.

    ``fallback_safe`` is True only when the request was never dispatched to
    the upstream (not started, circuit, pre-send connect failure). Timeouts,
    partial writes, and read failures after send default to False so logical
    routing will not retry on another account (avoids duplicate side effects).
    """

    def __init__(self, message: str, *, fallback_safe: bool = False) -> None:
        super().__init__(message)
        self.fallback_safe = fallback_safe


class BaseBackend:
    name: str = "base"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tools: list[ProxiedTool] = []
        self._status = BackendStatus(name=self.name)
        self._running = False
        self._protocol_version: str | None = None

    def start(self) -> None:
        connected = False
        try:
            self._connect()
            connected = True
            self._running = True
            self._initialize()
            self._refresh_tools()
            self._status.healthy = True
        except Exception as exc:
            if connected:
                with contextlib.suppress(Exception):
                    self._disconnect()
            self._status.error = str(exc)
            self._status.healthy = False
            self._running = False

    def stop(self) -> None:
        self._disconnect()
        self._running = False

    def list_tools(self) -> list[ProxiedTool]:
        return list(self._tools)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # Measure wall-clock latency so BackendStatus.latency_ms reflects reality
        # (it was previously declared but never populated — always 0.0).
        start = time.monotonic()
        result = self._rpc(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        self._status.latency_ms = (time.monotonic() - start) * 1000.0
        if "error" in result:
            return result
        return result.get("result", result)

    @property
    def status(self) -> BackendStatus:
        self._status.running = self._running
        self._status.tool_count = len(self._tools)
        return self._status

    def is_healthy(self) -> bool:
        return self._running and self._status.healthy

    def _connect(self) -> None:
        raise NotImplementedError

    def _disconnect(self) -> None:
        raise NotImplementedError

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def _initialize(self) -> None:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": NEWEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "kater-proxy", "version": "1.0"},
            },
        )
        if "error" in result:
            raise BackendOperationalError(
                f"MCP initialize failed: {result['error']}",
                fallback_safe=False,
            )
        negotiated = (result.get("result") or {}).get("protocolVersion")
        if not isinstance(negotiated, str) or not negotiated:
            raise BackendOperationalError(
                "MCP initialize response missing a valid protocol version",
                fallback_safe=False,
            )
        if negotiated not in SUPPORTED_PROTOCOL_VERSIONS:
            raise BackendOperationalError(
                f"unsupported MCP protocol version from server: {negotiated}",
                fallback_safe=False,
            )
        self._protocol_version = negotiated
        self._rpc("notifications/initialized")

    def _refresh_tools(self) -> None:
        result = self._rpc("tools/list")
        tools_data = result.get("result", {}).get("tools", [])
        self._tools = [
            ProxiedTool(
                name=t["name"],
                description=t.get("description", ""),
                backend=self.name,
                original_name=t["name"],
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]


class MockBackend(BaseBackend):
    name: str = "mock"

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        responses: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self._raw_tools = tools or []
        self._responses = responses or {}

    def start(self) -> None:
        self._tools = [
            ProxiedTool(
                name=t["name"],
                description=t.get("description", ""),
                backend=self.name,
                original_name=t["name"],
                input_schema=t.get("inputSchema", {}),
            )
            for t in self._raw_tools
        ]
        self._running = True
        self._status.healthy = True

    def stop(self) -> None:
        self._running = False

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name in self._responses:
            return self._responses[tool_name]
        return {"content": [{"type": "text", "text": f"mock result for {tool_name}"}]}
