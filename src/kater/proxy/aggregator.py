from __future__ import annotations

from typing import Any

from kater.proxy.models import ProxiedTool


class Aggregator:
    def __init__(self) -> None:
        self._tools: dict[str, ProxiedTool] = {}

    def add_backend_tools(self, backend_name: str, tools: list[ProxiedTool]) -> None:
        for tool in tools:
            if tool.backend != backend_name:
                tool.backend = backend_name
            key = tool.prefixed_name
            self._tools[key] = tool

    def remove_backend(self, backend_name: str) -> None:
        to_remove = [
            key for key, tool in self._tools.items()
            if tool.backend == backend_name
        ]
        for key in to_remove:
            del self._tools[key]

    def clear(self) -> None:
        self._tools.clear()

    def all_tools(self) -> list[ProxiedTool]:
        return list(self._tools.values())

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_tool(self, prefixed_name: str) -> ProxiedTool | None:
        return self._tools.get(prefixed_name)

    def count(self) -> int:
        return len(self._tools)

    def for_mcp(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.prefixed_name,
                "description": f"[{t.backend}] {t.description}",
                "inputSchema": t.input_schema,
            }
            for t in self._tools.values()
        ]
