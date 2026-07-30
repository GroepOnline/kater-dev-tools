"""Cheap availability checks for the browser backends.

Probing never launches a browser, never imports playwright and never makes a
network call: the dashboard and ``kater doctor`` poll it.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from kater.browser.base import (
    DEFAULT_STEEL_URL,
    ENV_CDP_URL,
    ENV_STEEL_KEY,
    ENV_STEEL_URL,
    ProviderInfo,
    browsers_root,
    redact_endpoint,
)
from kater.browser.models import ProviderKind


def probe_providers() -> list[ProviderInfo]:
    """
    Report backend availability without launching browsers or making network calls.

    Returns:
        list[ProviderInfo]: Availability results for the local, CDP, and Steel backends, in that
            order.
    """
    return [probe_local(), probe_cdp(), probe_steel()]


def probe_local() -> ProviderInfo:
    """
    Determine whether the local Playwright backend has an installed Chromium build.

    Returns:
        ProviderInfo: Local backend availability, including the installed Playwright version when
            available and a status message.
    """
    if importlib.util.find_spec("playwright") is None:
        return ProviderInfo(ProviderKind.LOCAL, False, "playwright is not installed")
    version = _playwright_version()
    root = browsers_root()
    if not _has_chromium_build(root):
        return ProviderInfo(
            ProviderKind.LOCAL,
            False,
            f"no chromium build under {root}; run 'playwright install chromium'",
            version,
        )
    return ProviderInfo(ProviderKind.LOCAL, True, f"chromium available in {root}", version)


def probe_cdp() -> ProviderInfo:
    """
    Check whether a CDP endpoint is configured.

    Returns:
        ProviderInfo: CDP availability status with a redacted endpoint when configured.
    """
    endpoint = os.environ.get(ENV_CDP_URL, "").strip()
    if not endpoint:
        return ProviderInfo(ProviderKind.CDP, False, f"{ENV_CDP_URL} is not set")
    return ProviderInfo(ProviderKind.CDP, True, f"endpoint {redact_endpoint(endpoint)}")


def probe_steel() -> ProviderInfo:
    """
    Determine whether the Steel remote backend is configured.

    Returns:
        ProviderInfo: Availability status for the Steel backend, including a redacted
        base URL and whether an API key is configured.
    """
    base_url = os.environ.get(ENV_STEEL_URL, "").strip()
    if not base_url:
        return ProviderInfo(
            ProviderKind.REMOTE,
            False,
            f"{ENV_STEEL_URL} is not set (default {DEFAULT_STEEL_URL})",
        )
    keyed = "with api key" if os.environ.get(ENV_STEEL_KEY, "").strip() else "no api key"
    return ProviderInfo(
        ProviderKind.REMOTE, True, f"steel api {redact_endpoint(base_url)} ({keyed})"
    )


def _has_chromium_build(root: Path) -> bool:
    """Determine whether the directory contains a Chromium build.

    Parameters:
        root (Path): Directory to scan for a Chromium build.

    Returns:
        bool: `true` if a child name starts with "chromium", `false` otherwise.
    """
    try:
        return any(child.name.startswith("chromium") for child in root.iterdir())
    except OSError:
        return False


def _playwright_version() -> str | None:
    """Return the installed Playwright package version, if available.

    Returns:
        str | None: The installed Playwright version, or `None` if the package is not installed.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("playwright")
    except PackageNotFoundError:
        return None
