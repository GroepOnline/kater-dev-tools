"""Product-facing plugin manifests for the Kater capability fabric."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from kater.extensions import extension_attr
from kater.profiles import TOOL_SOURCES, ToolSource, Transport, visible_tool_sources

_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_VERSION = re.compile(r"^v?\d+(?:\.\d+){0,3}(?:-[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, slots=True)
class PluginManifest:
    id: str
    name: str
    version: str
    description: str = ""
    publisher: str = ""
    toolkits: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ()
    homepage: str = ""
    status: str = "installed"
    origin: str = "extension"

    def __post_init__(self) -> None:
        if not _PLUGIN_ID.match(self.id):
            raise ValueError(f"invalid plugin id: {self.id!r}")
        if not self.name.strip():
            raise ValueError("plugin name is required")
        if not _VERSION.match(self.version):
            raise ValueError(f"invalid plugin version: {self.version!r}")
        if self.status not in {"installed", "disabled", "available"}:
            raise ValueError(f"invalid plugin status: {self.status!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "publisher": self.publisher,
            "toolkits": list(self.toolkits),
            "profiles": list(self.profiles),
            "homepage": self.homepage,
            "status": self.status,
            "origin": self.origin,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> PluginManifest:
        plugin_id = str(data.get("id") or data.get("name") or "").strip()
        return cls(
            id=plugin_id,
            name=str(data.get("name") or plugin_id),
            version=str(data.get("version") or "0.0.0"),
            description=str(data.get("description") or ""),
            publisher=str(data.get("publisher") or ""),
            toolkits=tuple(sorted(str(item) for item in data.get("toolkits", ()))),
            profiles=tuple(sorted(str(item) for item in data.get("profiles", ()))),
            homepage=str(data.get("homepage") or ""),
            status=str(data.get("status") or "installed"),
            origin=str(data.get("origin") or "extension"),
        )


def _manifest_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if hasattr(raw, "as_dict"):
        return dict(raw.as_dict())
    if hasattr(raw, "__dataclass_fields__") and not isinstance(raw, type):
        return {name: getattr(raw, name) for name in raw.__dataclass_fields__}
    return dict(getattr(raw, "__dict__", {}))


def _toolkits_profiles(sources: tuple[ToolSource, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(sorted(source.name for source in sources)),
        tuple(sorted({p for source in sources for p in source.profiles})),
    )


def _core_manifest() -> PluginManifest:
    from kater import __version__

    sources = tuple(source for source in TOOL_SOURCES if source.transport is not Transport.NATIVE)
    toolkits, profiles = _toolkits_profiles(sources)
    return PluginManifest(
        id="kater-core",
        name="Kater Core",
        version=__version__,
        description="Built-in Kater toolkit, integration, and MCP providers.",
        publisher="GroepOnline",
        toolkits=toolkits,
        profiles=profiles,
        homepage="https://github.com/GroepOnline/kater-dev-tools",
        status="installed",
        origin="builtin",
    )


def list_plugin_manifests() -> list[PluginManifest]:
    manifests = [_core_manifest()]
    raw_plugins = tuple(extension_attr("PLUGINS", ()))
    manifests.extend(PluginManifest.from_mapping(_manifest_mapping(raw)) for raw in raw_plugins)
    if raw_plugins:
        # Explicit PLUGINS take precedence; the implicit module manifest is fallback only.
        return manifests
    module = os.environ.get("KATER_EXTENSIONS_MODULE", "").strip()
    if not module:
        return manifests
    builtin_names = {source.name for source in TOOL_SOURCES}
    extension_sources = [
        source
        for source in visible_tool_sources()
        if source.name not in builtin_names and source.transport is not Transport.NATIVE
    ]
    toolkits, profiles = _toolkits_profiles(tuple(extension_sources))
    manifests.append(
        PluginManifest(
            id=re.sub(r"[^a-z0-9._-]+", "-", module.lower()).strip("-") or "extension",
            name=module,
            version="0.0.0",
            description="Implicit Kater extension plugin.",
            publisher="extension",
            toolkits=toolkits,
            profiles=profiles,
            status="installed",
            origin="extension",
        )
    )
    return manifests


def get_plugin_manifest(plugin_id: str) -> PluginManifest | None:
    if plugin_id == "kater-core":
        return _core_manifest()
    for manifest in list_plugin_manifests():
        if manifest.id == plugin_id:
            return manifest
    return None
