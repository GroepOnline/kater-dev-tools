"""Unified Kater catalog for toolkits, integrations, plugins, and MCP surfaces.

This module is a product-facing compatibility layer over the existing connector,
profile, capability, and extension subsystems. It deliberately does not replace
them: Kater can converge its public model without a flag-day rewrite.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from kater.connect import source_is_configured
from kater.connections import list_connection_views
from kater.connectors.auth import binding_is_satisfied
from kater.connectors.models import ConnectorRecord, ConnectorType
from kater.connectors.store import list_connectors
from kater.execution import action_is_dangerous
from kater.extensions import extension_attr
from kater.plugins import PluginManifest
from kater.profiles import (
    TOOL_SOURCES,
    ToolSource,
    all_tool_sources,
    is_private_profile,
    is_private_source,
    is_public_mode,
    visible_tool_sources,
)
from kater.settings import load_settings
from kater.toolkits import toolkit_manifests


class CatalogKind(StrEnum):
    TOOLKIT = "toolkit"
    INTEGRATION = "integration"
    CONNECTION = "connection"
    ACTION = "action"
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


def _visible_profiles(profiles: Iterable[str]) -> tuple[str, ...]:
    public = is_public_mode()
    return tuple(
        sorted(profile for profile in profiles if not public or not is_private_profile(profile))
    )


def _hidden_source_names() -> set[str]:
    if not is_public_mode():
        return set()
    return {source.name for source in all_tool_sources() if is_private_source(source)}


def _connector_map() -> dict[str, ConnectorRecord]:
    try:
        records = list_connectors()
    except Exception:
        # Catalog reads should remain available when persistence is unavailable.
        return {}
    hidden_sources = _hidden_source_names()
    return {
        record.id: record
        for record in records
        if record.id not in hidden_sources
        and (not record.profiles or _visible_profiles(record.profiles))
    }


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


def _catalog_url_metadata(key: str, value: str | None) -> dict[str, str]:
    """Expose only HTTP origins, never credential-bearing endpoint configuration."""
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        return {}
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not hostname:
            return {}
        host = hostname.encode("idna").decode("ascii")
        if not re.fullmatch(r"[a-zA-Z0-9.:-]+", host):
            return {}
        port = parsed.port
    except (ValueError, UnicodeError):
        return {}
    authority = f"[{host}]" if ":" in host else host
    if port is not None:
        authority = f"{authority}:{port}"
    return {key: f"{parsed.scheme}://{authority}"}


def toolkit_items() -> list[CatalogItem]:
    settings = load_settings()
    connectors = _connector_map()
    items: list[CatalogItem] = []
    manifests = {item.id: item for item in toolkit_manifests()}
    for source in visible_tool_sources():
        if source.transport.value == "native":
            continue
        capabilities = _source_capabilities(source, connectors)
        manifest = manifests.get(source.name)
        if manifest is not None:
            capabilities = tuple(dict.fromkeys([*capabilities, *manifest.actions]))
        items.append(
            CatalogItem(
                id=f"toolkit:{source.name}",
                name=source.name,
                kind=CatalogKind.TOOLKIT,
                description=source.description,
                plugin_id=_plugin_id_for_source(source),
                transport=source.transport.value,
                profiles=_visible_profiles(source.profiles),
                capabilities=capabilities,
                enabled=settings.is_server_enabled(source.name, default=True),
                configured=source_is_configured(source, settings),
                status=_source_status(source, connectors),
                origin="builtin" if _plugin_id_for_source(source) == "kater-core" else "extension",
                metadata={
                    **_catalog_url_metadata("homepage", source.homepage),
                    "risk": source.risk.value,
                    "context_cost": source.context_cost,
                    "has_mcp_surface": source.mcp is not None,
                    **(
                        {
                            "integrations": list(manifest.integrations),
                            "native_actions": list(manifest.actions),
                        }
                        if manifest is not None
                        else {}
                    ),
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
                profiles=_visible_profiles(record.profiles),
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
                    "toolkit": connector_id,
                    "actions": sorted(cap.id for cap in record.capabilities),
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
                profiles=_visible_profiles(source.profiles),
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
        items.append(
            CatalogItem(
                id=f"mcp:{source.name}",
                name=source.name,
                kind=CatalogKind.MCP,
                description=source.description,
                plugin_id=_plugin_id_for_source(source),
                transport=source.transport.value,
                profiles=_visible_profiles(source.profiles),
                enabled=settings.is_server_enabled(source.name, default=True),
                configured=source_is_configured(source, settings),
                status=_source_status(source, connectors),
                origin="builtin" if _plugin_id_for_source(source) == "kater-core" else "extension",
                metadata=_catalog_url_metadata("endpoint", source.mcp.url),
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
                profiles=_visible_profiles(record.profiles),
                capabilities=tuple(sorted(cap.id for cap in record.capabilities)),
                enabled=record.status.value == "enabled",
                configured=binding_is_satisfied(
                    record.auth_binding,
                    connector_id=record.id,
                ),
                status=record.status.value,
                origin=record.origin,
                metadata={
                    **_catalog_url_metadata("endpoint", record.transport.endpoint),
                    "connector_type": record.type.value,
                },
            )
        )
    return items


def _extension_plugin_items() -> list[CatalogItem]:
    raw_plugins = tuple(extension_attr("PLUGINS", ()))
    hidden_sources = _hidden_source_names()
    items: list[CatalogItem] = []
    for raw in raw_plugins:
        manifest = PluginManifest.coerce(raw)
        if manifest is None:
            continue
        visible_profiles = _visible_profiles(manifest.profiles)
        if manifest.profiles and not visible_profiles:
            continue
        toolkits = tuple(sorted(item for item in manifest.toolkits if item not in hidden_sources))
        if manifest.toolkits and not toolkits:
            continue
        items.append(
            CatalogItem(
                id=f"plugin:{manifest.id}",
                name=manifest.name,
                kind=CatalogKind.PLUGIN,
                description=manifest.description,
                plugin_id=manifest.id,
                profiles=visible_profiles,
                capabilities=toolkits,
                status=manifest.status,
                origin=manifest.origin,
                metadata={
                    "version": manifest.version,
                    "toolkits": list(toolkits),
                },
            )
        )
    return items


def plugin_items() -> list[CatalogItem]:
    from kater import __version__

    hidden_sources = _hidden_source_names()
    builtin_sources = tuple(
        source
        for source in TOOL_SOURCES
        if source.transport.value != "native" and source.name not in hidden_sources
    )
    builtin_toolkits = tuple(sorted(source.name for source in builtin_sources))
    builtin_profiles = _visible_profiles(
        {profile for source in builtin_sources for profile in source.profiles}
    )
    items = [
        CatalogItem(
            id="plugin:kater-core",
            name="Kater Core",
            kind=CatalogKind.PLUGIN,
            description="Built-in Kater toolkit, integration, and MCP providers.",
            plugin_id="kater-core",
            profiles=builtin_profiles,
            capabilities=builtin_toolkits,
            status="installed",
            origin="builtin",
            metadata={"version": __version__, "toolkits": list(builtin_toolkits)},
        )
    ]
    extension_plugins = _extension_plugin_items()
    items.extend(extension_plugins)
    if not extension_plugins:
        module = os.environ.get("KATER_EXTENSIONS_MODULE", "").strip()
        if module:
            builtin_names = {source.name for source in TOOL_SOURCES}
            extension_toolkits = tuple(
                sorted(
                    source.name
                    for source in visible_tool_sources()
                    if source.name not in builtin_names and source.transport.value != "native"
                )
            )
            if is_public_mode() and not extension_toolkits:
                return items
            items.append(
                CatalogItem(
                    id=f"plugin:{module}",
                    name=module,
                    kind=CatalogKind.PLUGIN,
                    description="Implicit Kater extension plugin.",
                    plugin_id=module,
                    capabilities=extension_toolkits,
                    status="installed",
                    origin="extension",
                    metadata={"toolkits": list(extension_toolkits)},
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


def connection_items() -> list[CatalogItem]:
    items: list[CatalogItem] = []
    records = _connector_map()
    sources = {source.name: source for source in visible_tool_sources()}
    for view in list_connection_views(records=records):
        record = records.get(view.integration)
        source = sources.get(view.integration)
        if record is not None:
            item_profiles = _visible_profiles(record.profiles)
        elif source is not None:
            item_profiles = _visible_profiles(source.profiles)
        else:
            item_profiles = ()
        items.append(
            CatalogItem(
                id=f"connection:{view.id}",
                name=view.label or view.id,
                kind=CatalogKind.CONNECTION,
                description=f"{view.integration} connection ({view.origin})",
                plugin_id="kater-core",
                transport=view.auth_kind,
                profiles=item_profiles,
                capabilities=(),
                enabled=view.configured,
                configured=view.configured,
                status=view.status,
                origin=view.origin,
                metadata={
                    "toolkit": view.toolkit,
                    "integration": view.integration,
                    "connection_id": view.id,
                    "auth_kind": view.auth_kind,
                },
            )
        )
    return items


def action_items() -> list[CatalogItem]:
    items: list[CatalogItem] = []
    seen: set[str] = set()
    records = _connector_map()
    sources = {source.name: source for source in visible_tool_sources()}
    settings = load_settings()
    for record in records.values():
        for capability in record.capabilities:
            if capability.id in seen:
                continue
            seen.add(capability.id)
            source = sources.get(record.id)
            if source is not None:
                configured = source_is_configured(source, settings)
            else:
                configured = binding_is_satisfied(record.auth_binding, connector_id=record.id)
            items.append(
                CatalogItem(
                    id=f"action:{capability.id}",
                    name=capability.id,
                    kind=CatalogKind.ACTION,
                    description=capability.description,
                    plugin_id="kater-core",
                    transport=record.transport.kind,
                    profiles=_visible_profiles(record.profiles),
                    capabilities=(capability.id,),
                    enabled=record.status.value == "enabled",
                    configured=configured,
                    status=record.status.value,
                    origin=record.origin,
                    metadata={
                        "toolkit": record.id,
                        "integration": record.id,
                        "connection_id": f"{record.id}:default",
                        "mutation": capability.mutation,
                        "dangerous": action_is_dangerous(
                            capability.id, mutation=capability.mutation
                        ),
                    },
                )
            )
    for toolkit in toolkit_manifests():
        integration = toolkit.integrations[0] if toolkit.integrations else toolkit.id
        owner = records.get(integration)
        source = sources.get(integration)
        if source is not None:
            configured = source_is_configured(source, settings)
            item_profiles = _visible_profiles(source.profiles)
        elif owner is not None:
            configured = binding_is_satisfied(owner.auth_binding, connector_id=owner.id)
            item_profiles = _visible_profiles(owner.profiles)
        else:
            configured = False
            item_profiles = ()
        for action_id in toolkit.actions:
            if action_id in seen:
                continue
            seen.add(action_id)
            items.append(
                CatalogItem(
                    id=f"action:{action_id}",
                    name=action_id,
                    kind=CatalogKind.ACTION,
                    description=f"{toolkit.name} native action",
                    plugin_id="kater-core",
                    transport="native",
                    profiles=item_profiles,
                    capabilities=(action_id,),
                    enabled=True,
                    configured=configured,
                    status="available",
                    origin="builtin",
                    metadata={
                        "toolkit": toolkit.id,
                        "integration": integration,
                        "connection_id": f"{integration}:default",
                        "mutation": action_is_dangerous(action_id),
                        "dangerous": action_is_dangerous(action_id),
                    },
                )
            )
    return items


def catalog_items(kind: CatalogKind | None = None) -> list[CatalogItem]:
    providers = {
        CatalogKind.TOOLKIT: toolkit_items,
        CatalogKind.INTEGRATION: integration_items,
        CatalogKind.CONNECTION: connection_items,
        CatalogKind.ACTION: action_items,
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
        "connections": grouped[CatalogKind.CONNECTION.value],
        "actions": grouped[CatalogKind.ACTION.value],
        "plugins": grouped[CatalogKind.PLUGIN.value],
        "mcp": grouped[CatalogKind.MCP.value],
    }
