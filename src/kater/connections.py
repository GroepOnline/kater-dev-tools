"""Secret-free provider connection inventory for Kater integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from kater.connect import list_connections, source_is_configured
from kater.profiles import TOOL_SOURCES, ToolSource, visible_tool_sources
from kater.settings import KaterSettings, ServerConnection, load_settings


@dataclass(frozen=True, slots=True)
class ConnectionView:
    id: str
    integration: str
    toolkit: str
    plugin_id: str
    label: str
    auth_kind: str
    storage: str
    profiles: tuple[str, ...]
    configured: bool
    enabled: bool
    created_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "integration": self.integration,
            "toolkit": self.toolkit,
            "plugin_id": self.plugin_id,
            "label": self.label,
            "auth_kind": self.auth_kind,
            "storage": self.storage,
            "profiles": list(self.profiles),
            "configured": self.configured,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


_BUILTIN_NAMES = frozenset(item.name for item in TOOL_SOURCES)


def _plugin_id(source: ToolSource) -> str:
    if source.name in _BUILTIN_NAMES:
        return "kater-core"
    module = os.environ.get("KATER_EXTENSIONS_MODULE", "").strip()
    return module or "extension"


def _auth_kind(source: ToolSource) -> str:
    if source.oauth:
        return "oauth"
    if source.env:
        return "credential"
    return "none"


def _connection_configured(source: ToolSource, conn: ServerConnection) -> bool:
    if source.oauth:
        return bool(conn.env.get(source.oauth.token_env))
    if source.env:
        return all(bool(conn.env.get(key)) for key in source.env)
    return True


def _stored_views(
    source: ToolSource,
    settings: KaterSettings,
) -> list[ConnectionView]:
    views: list[ConnectionView] = []
    for conn in list_connections(source, settings):
        views.append(
            ConnectionView(
                id=f"{source.name}:{conn.id}",
                integration=source.name,
                toolkit=source.name,
                plugin_id=_plugin_id(source),
                label=conn.label or conn.id,
                auth_kind=_auth_kind(source),
                storage="settings",
                profiles=tuple(sorted(source.profiles)),
                configured=_connection_configured(source, conn),
                enabled=settings.is_server_enabled(source.name, default=True),
                created_at=conn.created_at,
            )
        )
    return views


def _runtime_view(source: ToolSource, settings: KaterSettings) -> ConnectionView | None:
    if _auth_kind(source) == "none" or not source_is_configured(source, settings):
        return None
    return ConnectionView(
        id=f"{source.name}:env",
        integration=source.name,
        toolkit=source.name,
        plugin_id=_plugin_id(source),
        label="runtime environment",
        auth_kind=_auth_kind(source),
        storage="environment",
        profiles=tuple(sorted(source.profiles)),
        configured=True,
        enabled=settings.is_server_enabled(source.name, default=True),
        created_at=0.0,
    )


def list_connection_views(
    *,
    query: str = "",
    profile: str = "",
    integration: str = "",
    settings: KaterSettings | None = None,
) -> list[ConnectionView]:
    settings = settings or load_settings()
    wanted = query.strip().lower()
    rows: list[ConnectionView] = []
    for source in visible_tool_sources():
        if integration and source.name != integration:
            continue
        if profile and profile != "core" and profile not in source.profiles:
            continue
        stored = _stored_views(source, settings)
        if stored:
            candidates = stored
        else:
            # Stored connections take precedence over the synthetic env row.
            runtime = _runtime_view(source, settings)
            candidates = [runtime] if runtime is not None else []
        for row in candidates:
            if wanted:
                haystack = f"{row.id} {row.integration} {row.label} {row.auth_kind}".lower()
                if wanted not in haystack:
                    continue
            rows.append(row)
    rows.sort(key=lambda row: (row.integration, row.created_at, row.id))
    return rows


def get_connection_view(connection_id: str) -> ConnectionView | None:
    for row in list_connection_views():
        if row.id == connection_id:
            return row
    return None
