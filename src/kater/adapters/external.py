from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from kater.profiles import ToolSource, all_tool_sources

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _substitute_env_vars(value: str, *, include_secrets: bool) -> str:
    """Replace every ${VAR} in a string. Keep the placeholder unless
    include_secrets is set and the variable is present in the environment."""

    def repl(match: re.Match[str]) -> str:
        real = os.environ.get(match.group(1))
        if include_secrets and real:
            return real
        return match.group(0)

    return _ENV_VAR_RE.sub(repl, value)


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


def scan_adapters(
    profiles: set[str] | None = None,
    *,
    include_secrets: bool = True,
) -> AdapterInventory:
    from kater.settings import load_settings

    settings = load_settings()
    inventory = AdapterInventory()
    env = dict(os.environ)
    for source in all_tool_sources():
        if source.transport == "native":
            continue
        if profiles and not source.profiles.intersection(profiles):
            continue
        if not settings.is_server_enabled(source.name, default=True):
            continue
        missing = [var for var in source.env if not env.get(var)]
        configured = len(missing) == 0
        launch = (
            _build_launch_hint(source, include_secrets=include_secrets)
            if source.mcp
            else None
        )
        inventory.sources.append(
            McpAdapter(
                source=source,
                configured=configured,
                missing_env=missing,
                launch_hint=launch,
            )
        )
    return inventory


def _build_launch_hint(
    source: ToolSource, *, include_secrets: bool = True
) -> dict[str, Any] | None:
    if not source.mcp:
        return None
    if source.transport == "stdio":
        return {
            "type": "stdio",
            "command": source.mcp.command,
            "args": source.mcp.args,
            "env": _resolve_env(source.mcp.env_template, include_secrets=include_secrets),
        }
    if source.transport in ("sse", "http"):
        url = _substitute_env_vars(source.mcp.url or "", include_secrets=include_secrets)
        hint: dict[str, Any] = {
            "type": _remote_launch_type(url),
            "url": url,
        }
        headers = resolve_remote_headers(source, include_secrets=include_secrets)
        if headers:
            hint["headers"] = headers
        env = _resolve_env(source.mcp.env_template, include_secrets=include_secrets)
        if env:
            hint["env"] = env
        return hint
    return None


def resolve_remote_headers(
    source: ToolSource, *, include_secrets: bool = True
) -> dict[str, str]:
    if not source.mcp:
        return {}
    return _resolve_env(source.mcp.headers_template, include_secrets=include_secrets)


def _remote_launch_type(url: str) -> str:
    if url.rstrip("/").endswith("/mcp"):
        return "http"
    return "sse"


def _resolve_env(
    template: dict[str, str], *, include_secrets: bool = True
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, val in template.items():
        match = _ENV_VAR_RE.fullmatch(val)
        if match:
            if include_secrets:
                real = os.environ.get(match.group(1))
                if real:
                    resolved[key] = real
            else:
                resolved[key] = val
        elif "${" in val:
            resolved[key] = _substitute_env_vars(val, include_secrets=include_secrets)
        else:
            resolved[key] = val
    return resolved


def render_profile_config(
    profile: str, *, include_secrets: bool = True
) -> dict[str, Any]:
    inventory = scan_adapters({profile} | {"core"}, include_secrets=include_secrets)
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
