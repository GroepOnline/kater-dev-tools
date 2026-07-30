"""Env-driven Computer connector registration without import cycles."""

from __future__ import annotations

import os
import threading
from typing import Any
from urllib.parse import urlsplit

from kater.capabilities.computer import (
    VENDORED_CONTRACT,
    ComputerConnector,
    register_computer_contract,
)
from kater.capabilities.registry import get_default_registry

_ENV_URL = "KATER_COMPUTER_URL"
_ENV_TOKEN = "KATER_COMPUTER_TOKEN"  # noqa: S105 — env var name, not a credential
_ENV_PROFILE = "KATER_COMPUTER_PROFILE"

_lock = threading.RLock()
_active_connector: ComputerConnector | None = None


def computer_configured() -> bool:
    """Return True when guest URL and bearer token are both set."""
    url = os.environ.get(_ENV_URL, "").strip()
    token = os.environ.get(_ENV_TOKEN, "").strip()
    return bool(url and token)


def get_computer_connector() -> ComputerConnector | None:
    """Return the process-wide Computer connector, if any."""
    with _lock:
        return _active_connector


def set_computer_connector(connector: ComputerConnector | None) -> None:
    """Install or clear the process-wide Computer connector singleton."""
    global _active_connector
    with _lock:
        _active_connector = connector


def reset_computer_connector() -> None:
    """
    Clear the process-wide computer connector.
    """
    set_computer_connector(None)


def _redacted_host(url: str) -> str:
    """
    Extract a sanitized hostname from a URL.
    
    Parameters:
        url (str): URL from which to extract the hostname.
    
    Returns:
        str: Lowercase hostname without a trailing period, or an empty string if the URL is blank, invalid, or has no hostname.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    return (parts.hostname or "").strip().lower().rstrip(".")


def build_computer_connector(profile: str = "core") -> ComputerConnector | None:
    """
    Build a computer connector from the configured environment variables.
    
    Parameters:
        profile (str): Fallback profile used when no profile is configured in the environment.
    
    Returns:
        ComputerConnector | None: A configured connector, or `None` when the required computer URL or token is missing.
    """
    if not computer_configured():
        return None
    url = os.environ.get(_ENV_URL, "").strip()
    token = os.environ.get(_ENV_TOKEN, "").strip()
    env_profile = os.environ.get(_ENV_PROFILE, "").strip()
    effective_profile = env_profile or profile or "core"
    registry = get_default_registry()
    manifests = register_computer_contract(VENDORED_CONTRACT, registry)
    return ComputerConnector(
        manifests,
        registry,
        profile=effective_profile,
        base_url=url,
        auth_token=token,
    )


def ensure_computer_connector(profile: str = "core") -> ComputerConnector | None:
    """Return the active connector, building and installing one from env when needed."""
    global _active_connector
    with _lock:
        if _active_connector is not None:
            return _active_connector
        connector = build_computer_connector(profile)
        _active_connector = connector
        return connector


def computer_status() -> dict[str, Any]:
    """Build a REST- and CLI-friendly status payload for the computer connector.
    
    Returns:
    	dict[str, Any]: Status fields describing configuration, activation, redacted host, profile, and available capability identifiers.
    """
    configured = computer_configured()
    url = os.environ.get(_ENV_URL, "").strip()
    connector = get_computer_connector()
    capability_ids: list[str] = []
    if connector is not None:
        capability_ids = [str(tool["name"]) for tool in connector.list_tools()]
    return {
        "configured": configured,
        "active": connector is not None,
        "base_url_host": _redacted_host(url) if configured else "",
        "profile": (
            os.environ.get(_ENV_PROFILE, "").strip()
            or (connector.profile if connector is not None else "")
            or "core"
        ),
        "capability_count": len(capability_ids),
        "capability_ids": capability_ids,
    }
