"""Packaged static resources for the optional Kater Studio client."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

_RESOURCES = {
    "index.html": "text/html; charset=utf-8",
    "assets/studio.js": "text/javascript; charset=utf-8",
    "assets/studio.css": "text/css; charset=utf-8",
}


@lru_cache(maxsize=8)
def read_studio_resource(name: str) -> tuple[bytes, str]:
    """Return one explicitly-owned Studio resource and its content type."""
    content_type = _RESOURCES.get(name)
    if content_type is None:
        raise KeyError(name)
    resource = files("kater.web").joinpath("studio_dist")
    for part in name.split("/"):
        resource = resource.joinpath(part)
    return resource.read_bytes(), content_type
