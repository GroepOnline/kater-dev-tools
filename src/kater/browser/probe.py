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
    """Report backend availability without launching or dialling anything."""
    return [probe_local(), probe_cdp(), probe_steel()]


def probe_local() -> ProviderInfo:
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
    endpoint = os.environ.get(ENV_CDP_URL, "").strip()
    if not endpoint:
        return ProviderInfo(ProviderKind.CDP, False, f"{ENV_CDP_URL} is not set")
    return ProviderInfo(ProviderKind.CDP, True, f"endpoint {redact_endpoint(endpoint)}")


def probe_steel() -> ProviderInfo:
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


def _is_launchable(path: Path) -> bool:
    """True when ``path`` looks like a Chromium binary this host can exec."""
    try:
        if not path.is_file():
            return False
        # Windows builds ship ``.exe``; execute bit is not meaningful there.
        if path.suffix.lower() == ".exe":
            return True
        return os.access(path, os.X_OK)
    except OSError:
        return False


def _has_chromium_build(root: Path) -> bool:
    """True only when a chromium* tree contains a launchable binary.

    A bare ``chromium_*`` directory (stale / partial Playwright cache) must
    not count as available — otherwise ``requires_chromium`` tests run and
    fail with ``Executable doesn't exist``.
    """
    try:
        children = list(root.iterdir())
    except OSError:
        return False
    for child in children:
        if not child.name.startswith("chromium"):
            continue
        if not child.is_dir():
            continue
        for candidate in (
            "chrome-linux/chrome",
            "chrome-linux64/chrome",
            "chrome-headless-shell-linux64/chrome-headless-shell",
            "chrome-headless-shell-linux/chrome-headless-shell",
            "chrome-mac/Chromium",
            "chrome-mac-arm64/Google Chrome for Testing",
            "chrome-win/chrome.exe",
            "chrome-win64/chrome.exe",
        ):
            if _is_launchable(child / candidate):
                return True
        # Fallback: any nested launchable named chrome / chrome-headless-shell
        try:
            for path in child.rglob("*"):
                name = path.name.lower()
                if name in {"chrome", "chrome.exe", "chrome-headless-shell", "chromium"}:
                    if _is_launchable(path):
                        return True
        except OSError:
            continue
    return False


def _playwright_version() -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("playwright")
    except PackageNotFoundError:
        return None
