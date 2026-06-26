from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProxiedTool:
    name: str
    description: str
    backend: str
    original_name: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def prefixed_name(self) -> str:
        return f"{self.backend}__{self.original_name}"


@dataclass
class BackendStatus:
    name: str
    healthy: bool = False
    running: bool = False
    tool_count: int = 0
    error: str | None = None
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "running": self.running,
            "tool_count": self.tool_count,
            "error": self.error,
            "latency_ms": round(self.latency_ms, 1),
        }
