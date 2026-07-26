"""Shared contracts for browser backends.

Kept apart from the concrete providers so probing and configuration can be
imported without pulling in any driver code.
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from kater.browser.models import ActionResult, BrowserAction, BrowserSession, ProviderKind
from kater.browser.policy import BrowserPolicy

ENV_PROVIDER = "KATER_BROWSER_PROVIDER"
ENV_CDP_URL = "KATER_BROWSER_CDP_URL"
ENV_STEEL_URL = "KATER_BROWSER_STEEL_URL"
ENV_STEEL_KEY = "KATER_BROWSER_STEEL_KEY"
ENV_NO_SANDBOX = "KATER_BROWSER_NO_SANDBOX"
ENV_ALLOW_EVALUATE = "KATER_BROWSER_ALLOW_EVALUATE"

DEFAULT_STEEL_URL = "http://localhost:3000"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class BrowserUnavailableError(RuntimeError):
    """Raised when the configured browser backend cannot be reached or started."""


@dataclass(frozen=True)
class ProviderInfo:
    kind: ProviderKind
    available: bool
    detail: str
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "available": self.available,
            "detail": self.detail,
            "version": self.version,
        }


@dataclass
class PageHandle:
    """Opaque per-session page handle returned by ``new_page``."""

    session_id: str
    context: Any
    page: Any


class BrowserProvider(ABC):
    """Minimal surface every browser backend implements."""

    kind: ProviderKind = ProviderKind.LOCAL

    @abstractmethod
    def start(self) -> None:
        """Bring the backend up (idempotent)."""

    @abstractmethod
    def stop(self) -> None:
        """Tear the backend down (idempotent)."""

    @abstractmethod
    def new_page(self, session: BrowserSession) -> Any:
        """Return an opaque handle for a fresh isolated page."""

    @abstractmethod
    def act(self, handle: Any, action: BrowserAction, policy: BrowserPolicy) -> ActionResult:
        """Run one action against a handle and report the outcome."""

    @abstractmethod
    def close_page(self, handle: Any) -> None:
        """Dispose of one handle."""

    @abstractmethod
    def info(self) -> ProviderInfo:
        """Describe this backend's availability."""


def launch_args() -> list[str]:
    """Chromium flags. ``--no-sandbox`` stays opt-in: it is only safe in a container."""
    args = ["--disable-dev-shm-usage"]
    if env_truthy(ENV_NO_SANDBOX):
        args.append("--no-sandbox")
    return args


def browsers_root() -> Path:
    """Where Playwright keeps its downloaded browser builds."""
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if override and override != "0":
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def redact_endpoint(url: str) -> str:
    """Strip credentials, query string and fragment from a CDP/API endpoint URL."""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return "<redacted>"
    host = parts.hostname or ""
    if not host and not parts.scheme:
        # Opaque or unparseable value — never echo secrets.
        return "<redacted>"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    if parts.port is not None:
        netloc = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
