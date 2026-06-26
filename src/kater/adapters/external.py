from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from kater.profiles import TOOL_SOURCES, ToolSource


@dataclass
class McpAdapter:
    source: ToolSource
    configured: bool
    missing_env: list[str]
    launch_hint: dict[str, Any] | None = None


@dataclass
class AdapterInventory:
    sources: list[McpAdapter] = field(default_factory=list)

    def for_profile(self, profile: str) -> list[McpAdapter]:
        return [a for a in self.sources if profile in a.source.profiles]


def scan_adapters(profiles: set[str] | None = None) -> AdapterInventory:
    from kater.settings import load_settings

    settings = load_settings()
    inventory = AdapterInventory()
    for source in TOOL_SOURCES:
        if source.transport == "native":
            continue
        if profiles and not source.profiles.intersection(profiles):
            continue
        if not settings.is_server_enabled(source.name, default=True):
            continue
        missing = [var for var in source.env if not os.environ.get(var)]
        configured = len(missing) == 0
        launch = _build_launch_hint(source) if source.mcp else None
        inventory.sources.append(
            McpAdapter(
                source=source,
                configured=configured,
                missing_env=missing,
                launch_hint=launch,
            )
        )
    return inventory


def _build_launch_hint(source: ToolSource) -> dict[str, Any] | None:
    if not source.mcp:
        return None
    if source.transport == "stdio":
        return {
            "type": "stdio",
            "command": source.mcp.command,
            "args": source.mcp.args,
            "env": _resolve_env(source.mcp.env_template),
        }
    if source.transport in ("sse", "http"):
        url = source.mcp.url or ""
        for var in source.env:
            val = os.environ.get(var)
            if val:
                url = url.replace(f"${{{var}}}", val)
        if not url or url.startswith("${") and "}" not in url:
            if not source.env:
                url = source.mcp.url or ""
        return {
            "type": "sse",
            "url": url,
            "env": _resolve_env(source.mcp.env_template),
        }
    return None


def _resolve_env(template: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, val in template.items():
        if val.startswith("${") and val.endswith("}"):
            env_var = val[2:-1]
            real = os.environ.get(env_var)
            if real:
                resolved[key] = real
        else:
            resolved[key] = val
    return resolved


def render_profile_config(profile: str) -> dict[str, Any]:
    inventory = scan_adapters({profile} | {"core"})
    mcp_servers: dict[str, Any] = {}
    for adapter in inventory.sources:
        if not adapter.configured:
            continue
        if adapter.launch_hint:
            mcp_servers[adapter.source.name] = adapter.launch_hint

    mcp_servers["kater"] = {
        "type": "sse",
        "url": os.environ.get("KATER_URL", "http://127.0.0.1:9090/sse"),
        "env": {"KATER_PROFILE": profile},
    }

    return {
        "profile": profile,
        "mcpServers": mcp_servers,
    }
