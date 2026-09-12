"""Typed plugin manifests contributed by core or extension modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Installable bundle that contributes toolkits or provider wiring."""

    id: str
    name: str
    version: str = ""
    description: str = ""
    toolkits: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ()
    status: str = "installed"
    origin: str = "extension"

    def __post_init__(self) -> None:
        plugin_id = (self.id or "").strip()
        if not plugin_id:
            raise ValueError("plugin id is required")
        object.__setattr__(self, "id", plugin_id)
        object.__setattr__(self, "name", (self.name or plugin_id).strip() or plugin_id)
        object.__setattr__(
            self, "toolkits", tuple(str(item) for item in self.toolkits if str(item))
        )
        object.__setattr__(
            self, "profiles", tuple(str(item) for item in self.profiles if str(item))
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "toolkits": list(self.toolkits),
            "profiles": list(self.profiles),
            "status": self.status,
            "origin": self.origin,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> PluginManifest:
        payload = dict(data or {})
        return cls(
            id=str(payload.get("id") or payload.get("name") or ""),
            name=str(payload.get("name") or payload.get("id") or ""),
            version=str(payload.get("version") or ""),
            description=str(payload.get("description") or ""),
            toolkits=tuple(str(item) for item in list(payload.get("toolkits") or ())),
            profiles=tuple(str(item) for item in list(payload.get("profiles") or ())),
            status=str(payload.get("status") or "installed"),
            origin=str(payload.get("origin") or "extension"),
        )

    @classmethod
    def coerce(cls, raw: Any) -> PluginManifest | None:
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, dict):
            manifest = cls.from_mapping(raw)
            return manifest if manifest.id else None
        if hasattr(raw, "as_dict"):
            return cls.coerce(raw.as_dict())
        if hasattr(raw, "__dataclass_fields__") and not isinstance(raw, type):
            return cls.coerce({name: getattr(raw, name) for name in raw.__dataclass_fields__})
        data = getattr(raw, "__dict__", None)
        if isinstance(data, dict):
            return cls.coerce(data)
        return None
