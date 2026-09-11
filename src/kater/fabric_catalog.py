"""Unified Kater catalog for toolkits, integrations, plugins, and MCP surfaces.

This module is a product-facing compatibility layer over the existing connector,
profile, capability, and extension subsystems. It deliberately does not replace
them: Kater can converge its public model without a flag-day rewrite.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from kater.connect import source_is_configured
from kater.connectors.auth import binding_is_satisfied
from kater.connectors.models import ConnectorRecord, ConnectorType
from kater.connectors.store import list_connectors
from kater.profiles import TOOL_SOURCES, ToolSource, visible_tool_sources
from kater.settings import load_settings


class CatalogKind(StrEnum):
    TOOLKIT = "toolkit"
    INTEGRATION = "integration"
    PLUGIN = "plugin"
    MCP = "mcp"


@dataclass(frozen=True, slots=True)
class CatalogItem:
    id: str
    name: str
    kind: CatalogKind
    description: str = ""
    plugin_id: str = "kater-core"
    transport: str = ""
    profiles: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    enabled: bool | None = None
    configured: bool | None = None
    status: str = "available"
    origin: str = "builtin"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "description": self.description,
            "plugin_id": self.plugin_id,
            "transport": self.transport,
            "profiles": list(self.profiles),
            "capabilities": list(self.capabilities),
            "enabled": self.enabled,
            "configured": self.configured,
            "status": self.status,
            "origin": self.origin,
            "metadata": dict(self.metadata),
        }


def _plugin_id_for_source(source: ToolSource) -> str:
    builtin_names = {item.name for item in TOOL_SOURCES}
    if source.name in builtin_names:
        return "kater-core"
    module = os.environ.get("KATER_EXTENSIONS_MODULE", "").strip()
    return module or "kater-extension"


def _connector_map() -> dict[str, ConnectorRecord]:
    try:
        return {record.id: record for record in list_connectors()}
    except Exception:
        # Catalog reads should remain available when persistence is unavailable.
        return {}


def _source_capabilities(
    source: ToolSource,
    connectors: dict[str, ConnectorRecord],
) -> tuple[str, ...]:
    record = connectors.get(source.name)
    if record is None:
        return ()
    return tuple(sorted(capability.id for capability in record.capabilities))


def _source_status(source: ToolSource, connectors: dict[str, ConnectorRecord]) -> str:
    record = connectors.get(source.name)
    return record.status.value if record is not None else "available"


def toolkit_items() -> list[CatalogItem]:
    settings = load_settings()
    connectors = _connector_map()
    items: list[CatalogItem] = []
    for source in visible_tool_sources():
        if source.transport.value == "native":
            continue
        items.append(
            CatalogItem(
                id=f"toolkit:{source.name}",
                name=source.name,
                kind=CatalogKind.TOOLKIT,
                description=source.description,
                plugin_id=_plugin_id_for_source(source),
                transport=source.transport.value,
                profiles=tuple(sorted(source.profiles)),
                capabilities=_source_capabilities(source, connectors),
                enabled=settings.is_server_enabled(source.name, default=True),
                configured=source_is_configured(source, settings),
                status=_source_status(source, connectors),
                origin="builtin" if _plugin_id_for_source(source) == "kater-core" else "extension",
                metadata={
                    "homepage": source.homepage,
                    "risk": source.risk.value,
                    "context_cost": source.context_cost,
                    "has_mcp_surface": source.mcp is not None,
                },
            )
        )
    return items


def integration_items() -> list[CatalogItem]:
    settings = load_settings()
    connectors = _connector_map()
    sources = {source.name: source for source in visible_tool_sources()}
    items: list[CatalogItem] = []
    for connector_id, record in sorted(connectors.items()):
        source = sources.get(connector_id)
        items.append(
            CatalogItem(
                id=f"integration:{connector_id}",
                name=record.display_name,
                kind=CatalogKind.INTEGRATION,
                description=(
                    source.description if source else str(record.metadata.get("description") or "")
                ),
                plugin_id=_plugin_id_for_source(source) if source else "dynamic",
                transport=record.transport.kind,
                profiles=tuple(sorted(record.profiles)),
                capabilities=tuple(sorted(cap.id for cap in record.capabilities)),
                enabled=record.status.value == "enabled",
                configured=binding_is_satisfied(
                    record.auth_binding,
                    connector_id=record.id,
                ),
                status=record.status.value,
                origin=record.origin,
                metadata={
                    "connector_type": record.type.value,
                    "auth_binding_kind": record.auth_binding.kind.value,
                    "auth_binding_ref": record.auth_binding.ref,
                },
            )
        )

    # A provider can be available as a toolkit before it has a persisted connector row.
    for name, source in sorted(sources.items()):
        if source.transport.value == "native" or name in connectors:
            continue
        items.append(
            CatalogItem(
                id=f"integration:{name}",
                name=name,
                kind=CatalogKind.INTEGRATION,
                description=source.description,
                plugin_id=_plugin_id_for_source(source),
                transport=source.transport.value,
                profiles=tuple(sorted(source.profiles)),
                enabled=settings.is_server_enabled(source.name, default=True),
                configured=source_is_configured(source, settings),
                status="available",
                origin="builtin" if _plugin_id_for_source(source) == "kater-core" else "extension",
            )
        )
    return items


def mcp_items() -> list[CatalogItem]:
    settings = load_settings()
    connectors = _connector_map()
    items: list[CatalogItem] = []
    seen: set[str] = set()
    for source in visible_tool_sources():
        if source.mcp is None:
            continue
        seen.add(source.name)
        mcp = source.mcp.model_dump()
        items.append(
            CatalogItem(
                id=f"mcp:{source.name}",
                name=source.name,
                kind=CatalogKind.MCP,
                description=source.description,
                plugin_id=_plugin_id_for_source(source),
                transport=source.transport.value,
                profiles=tuple(sorted(source.profiles)),
                enabled=settings.is_server_enabled(source.name, default=True),
                configured=source_is_configured(source, settings),
                status=_source_status(source, connectors),
                origin="builtin" if _plugin_id_for_source(source) == "kater-core" else "extension",
                metadata={"mcp": mcp},
            )
        )
    for record in connectors.values():
        if record.id in seen or record.type not in {ConnectorType.MCP, ConnectorType.BRIDGE}:
            continue
        items.append(
            CatalogItem(
                id=f"mcp:{record.id}",
                name=record.display_name,
                kind=CatalogKind.MCP,
                transport=record.transport.kind,
                profiles=tuple(sorted(record.profiles)),
                capabilities=tuple(sorted(cap.id for cap in record.capabilities)),
                enabled=record.status.value == "enabled",
                configured=binding_is_satisfied(
                    record.auth_binding,
                    connector_id=record.id,
                ),
                status=record.status.value,
                origin=record.origin,
                metadata={
                    "endpoint": record.transport.endpoint,
                    "connector_type": record.type.value,
                },
            )
        )
    return items


def plugin_items() -> list[CatalogItem]:
    from kater.plugins import list_plugin_manifests

    items: list[CatalogItem] = []
    for manifest in list_plugin_manifests():
        items.append(
            CatalogItem(
                id=f"plugin:{manifest.id}",
                name=manifest.name,
                kind=CatalogKind.PLUGIN,
                description=manifest.description,
                plugin_id=manifest.id,
                profiles=manifest.profiles,
                capabilities=manifest.toolkits,
                status=manifest.status,
                origin=manifest.origin,
                metadata={
                    "version": manifest.version,
                    "publisher": manifest.publisher,
                    "homepage": manifest.homepage,
                    "toolkits": list(manifest.toolkits),
                },
            )
        )
    return items


def _matches(item: CatalogItem, *, query: str, profile: str) -> bool:
    if profile and profile != "core" and profile not in item.profiles:
        return False
    if not query:
        return True
    haystack = " ".join(
        [item.id, item.name, item.description, item.transport, " ".join(item.capabilities)]
    ).lower()
    return query in haystack


def catalog_items(kind: CatalogKind | None = None) -> list[CatalogItem]:
    providers = {
        CatalogKind.TOOLKIT: toolkit_items,
        CatalogKind.INTEGRATION: integration_items,
        CatalogKind.PLUGIN: plugin_items,
        CatalogKind.MCP: mcp_items,
    }
    if kind is not None:
        return providers[kind]()
    items: list[CatalogItem] = []
    for provider in providers.values():
        items.extend(provider())
    return items


def catalog_payload(
    *,
    query: str = "",
    profile: str = "",
    kind: CatalogKind | None = None,
) -> dict[str, Any]:
    query = query.strip().lower()
    profile = profile.strip()
    items = [item for item in catalog_items(kind) if _matches(item, query=query, profile=profile)]
    grouped: dict[str, list[dict[str, Any]]] = {member.value: [] for member in CatalogKind}
    for item in items:
        grouped[item.kind.value].append(item.as_dict())
    return {
        "total": len(items),
        "counts": {name: len(rows) for name, rows in grouped.items()},
        "items": [item.as_dict() for item in items],
        "toolkits": grouped[CatalogKind.TOOLKIT.value],
        "integrations": grouped[CatalogKind.INTEGRATION.value],
        "plugins": grouped[CatalogKind.PLUGIN.value],
        "mcp": grouped[CatalogKind.MCP.value],
    }
