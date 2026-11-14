"""Packaged static resources for the optional Kater Studio client."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

_RESOURCES = {
    "index.html": "text/html; charset=utf-8",
    "assets/studio.js": "text/javascript; charset=utf-8",
    "assets/studio.css": "text/css; charset=utf-8",
}
_LOGOS_DIR = "assets/logos"
_LOGO_CONTENT_TYPE = "image/svg+xml; charset=utf-8"


def _logo_content_type(name: str) -> str | None:
    return _LOGO_CONTENT_TYPE if name.endswith(".svg") else None


def _logo_resource(name: str) -> str | None:
    # Reject traversal and any path that escapes the logos directory.
    parts = name.split("/")
    if any(part in {"", ".."} for part in parts):
        return None
    if not name.startswith(f"{_LOGOS_DIR}/"):
        return None
    return name


def _resolve_resource(name: str) -> str | None:
    if name in _RESOURCES:
        return name
    return _logo_resource(name)


def _content_type_for(name: str) -> str | None:
    if name in _RESOURCES:
        return _RESOURCES[name]
    return _logo_content_type(name)


@lru_cache(maxsize=8)
def read_studio_resource(name: str) -> tuple[bytes, str]:
    """Return one explicitly-owned Studio resource and its content type."""
    resolved = _resolve_resource(name)
    if resolved is None:
        raise KeyError(name)
    content_type = _content_type_for(name)
    if content_type is None:
        raise KeyError(name)
    resource = files("kater.web").joinpath("studio_dist")
    for part in resolved.split("/"):
        resource = resource.joinpath(part)
    return resource.read_bytes(), content_type
