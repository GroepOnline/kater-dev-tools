from __future__ import annotations

import threading
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
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def list_tools(self) -> list[ProxiedTool]:
        return list(self._tools)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def status(self) -> BackendStatus:
        self._status.running = self._running
        self._status.tool_count = len(self._tools)
        return self._status

    def is_healthy(self) -> bool:
        return self._running and self._status.healthy


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
