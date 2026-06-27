from __future__ import annotations

import threading
import time
from typing import Any

from kater.proxy.models import BackendStatus, ProxiedTool


class BaseBackend:
    name: str = "base"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tools: list[ProxiedTool] = []
        self._status = BackendStatus(name=self.name)
        self._running = False

    def start(self) -> None:
        try:
            self._connect()
            self._running = True
            self._initialize()
            self._refresh_tools()
            self._status.healthy = True
        except Exception as exc:
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
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "kater-proxy", "version": "1.0"},
            },
        )
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
