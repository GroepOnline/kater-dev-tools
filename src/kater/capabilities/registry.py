from __future__ import annotations

import importlib
import logging
import re
import threading
from dataclasses import dataclass, replace

from kater.capabilities.models import CapabilityManifest, LifecycleState

_log = logging.getLogger("kater.capabilities.registry")

_INVOCABLE_STATES = frozenset({LifecycleState.ACTIVE, LifecycleState.CANARY})

_VERSION_SPLIT = re.compile(r"[.+-]")


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    version: int
    manifests: tuple[CapabilityManifest, ...]


def _version_key(version: str) -> tuple[object, ...]:
    """Sort key preferring numeric segments, then lexicographic fallback."""
    parts: list[object] = []
    for part in _VERSION_SPLIT.split(version.lstrip("vV")):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part))
    return tuple(parts)


def _lifecycle_preference(state: LifecycleState) -> int:
    # Lower is better for "active-preferring" latest selection.
    order = {
        LifecycleState.ACTIVE: 0,
        LifecycleState.CANARY: 1,
        LifecycleState.VERIFIED: 2,
        LifecycleState.CANDIDATE: 3,
        LifecycleState.DEPRECATED: 4,
        LifecycleState.REVOKED: 5,
    }
    return order.get(state, 99)


class CapabilityRegistry:
    """Thread-safe in-memory capability manifest registry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # (capability_id, version) -> manifest
        self._entries: dict[tuple[str, str], CapabilityManifest] = {}
        # capability_id -> set of versions
        self._versions: dict[str, set[str]] = {}
        self._version = 0

    def register(self, manifest: CapabilityManifest) -> None:
        key = (manifest.capability_id, manifest.version)
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                if existing.digest != manifest.digest:
                    raise ValueError(
                        "duplicate capability "
                        f"{manifest.capability_id!r}@{manifest.version!r} "
                        f"with different digest "
                        f"({existing.digest!r} vs {manifest.digest!r})"
                    )
                return
            self._entries[key] = manifest
            self._versions.setdefault(manifest.capability_id, set()).add(manifest.version)
            self._version += 1

    def get(
        self, capability_id: str, version: str | None = None
    ) -> CapabilityManifest | None:
        with self._lock:
            if version is not None:
                return self._entries.get((capability_id, version))
            versions = self._versions.get(capability_id)
            if not versions:
                return None
            candidates = [self._entries[(capability_id, ver)] for ver in versions]
            # Active-preferring: best lifecycle first, then highest version in that band.
            best_pref = min(_lifecycle_preference(m.lifecycle_state) for m in candidates)
            band = [
                m for m in candidates if _lifecycle_preference(m.lifecycle_state) == best_pref
            ]
            band.sort(key=lambda m: _version_key(m.version), reverse=True)
            return band[0]

    def list(self, *, include_non_active: bool = False) -> list[CapabilityManifest]:
        with self._lock:
            manifests = list(self._entries.values())
        if not include_non_active:
            manifests = [
                m
                for m in manifests
                if m.lifecycle_state in (LifecycleState.ACTIVE, LifecycleState.CANARY)
            ]
        manifests.sort(key=lambda m: (m.capability_id, _version_key(m.version)))
        return manifests

    def set_lifecycle(
        self, capability_id: str, version: str, state: LifecycleState
    ) -> CapabilityManifest:
        if not isinstance(state, LifecycleState):
            raise ValueError("state must be a LifecycleState")
        key = (capability_id, version)
        with self._lock:
            existing = self._entries.get(key)
            if existing is None:
                raise KeyError(f"capability not registered: {capability_id}@{version}")
            updated = replace(existing, lifecycle_state=state)
            self._entries[key] = updated
            self._version += 1
            return updated

    def snapshot(self) -> RegistrySnapshot:
        with self._lock:
            manifests = tuple(
                manifest
                for manifest in self._entries.values()
                if manifest.lifecycle_state in _INVOCABLE_STATES
            )
            return RegistrySnapshot(self._version, manifests)

    def is_managed(self, capability_id: str) -> bool:
        with self._lock:
            return capability_id in self._versions

    def is_invocable(
        self, capability_id: str, version: str | None = None
    ) -> tuple[bool, str]:
        with self._lock:
            if capability_id not in self._versions:
                return True, "unmanaged"
            manifest = self.get(capability_id, version)
            if manifest is None:
                return False, "version not found"
            if manifest.lifecycle_state in _INVOCABLE_STATES:
                return True, manifest.lifecycle_state.value
            return False, f"lifecycle is {manifest.lifecycle_state.value}"

    def invocable_manifest(self, capability_id: str) -> CapabilityManifest | None:
        """Return the selected manifest while holding the lifecycle lock."""
        with self._lock:
            manifest = self.get(capability_id)
            if manifest is None or manifest.lifecycle_state not in _INVOCABLE_STATES:
                return None
            return manifest

    def revoke(self, capability_id: str, version: str) -> None:
        self.set_lifecycle(capability_id, version, LifecycleState.REVOKED)


_default_registry: CapabilityRegistry | None = None
_default_lock = threading.RLock()


def _apply_extension_capabilities(registry: CapabilityRegistry) -> None:
    from kater.extensions import extension_attr

    extras = extension_attr("CAPABILITIES", ())
    for item in extras:
        if not isinstance(item, CapabilityManifest):
            _log.warning("ignoring non-CapabilityManifest extension entry: %r", type(item))
            continue
        try:
            registry.register(item)
        except ValueError as exc:
            _log.warning("failed to register extension capability: %s", exc)


def _apply_persisted_overlays(registry: CapabilityRegistry) -> None:
    """Merge lifecycle overrides from an optional persistence store."""
    try:
        capability_store = importlib.import_module("kater.capabilities.store")
    except ImportError:
        return

    loader = getattr(capability_store, "load_lifecycle_overlays", None)
    if loader is None:
        return
    try:
        overlays = loader()
    except Exception:
        _log.exception("failed loading capability lifecycle overlays")
        return

    for item in overlays or ():
        try:
            if isinstance(item, dict):
                capability_id = item["capability_id"]
                version = item["version"]
                state = item["lifecycle_state"]
            else:
                capability_id, version, state = item
            if not isinstance(state, LifecycleState):
                state = LifecycleState(state)
            registry.set_lifecycle(capability_id, version, state)
        except Exception:
            _log.warning("skipping invalid lifecycle overlay entry: %r", item, exc_info=True)


def _bootstrap(registry: CapabilityRegistry) -> None:
    from kater.capabilities.builtins import BUILTIN_CAPABILITIES

    for manifest in BUILTIN_CAPABILITIES:
        registry.register(manifest)
    _apply_extension_capabilities(registry)
    _apply_persisted_overlays(registry)


def get_default_registry() -> CapabilityRegistry:
    """Return the process-wide registry (builtins + extensions + overlays)."""
    global _default_registry
    with _default_lock:
        if _default_registry is None:
            registry = CapabilityRegistry()
            _bootstrap(registry)
            _default_registry = registry
        return _default_registry


def reset_default_registry() -> None:
    """Clear the singleton (tests / reloads)."""
    global _default_registry
    with _default_lock:
        _default_registry = None
