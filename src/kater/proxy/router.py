from __future__ import annotations

from typing import Any

from kater.proxy.aggregator import Aggregator


class Router:
    def __init__(self, aggregator: Aggregator) -> None:
        self._aggregator = aggregator

    def route(self, tool_name: str) -> tuple[str, str] | None:
        tool = self._aggregator.get_tool(tool_name)
        if tool:
            return (tool.backend, tool.original_name)
        parts = tool_name.split("__", 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
        return None

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        backends: dict[str, Any],
    ) -> dict[str, Any]:
        route = self.route(tool_name)
        if not route:
            return {"error": f"Unknown tool: {tool_name}"}
        backend_name, original_name = route
        backend = backends.get(backend_name)
        if not backend:
            return {"error": f"Backend not available: {backend_name}"}
        if not backend.is_healthy():
            return {"error": f"Backend unhealthy: {backend_name}"}
        try:
            return backend.call_tool(original_name, arguments)
        except Exception as exc:
            return {"error": f"Backend error: {exc}"}
