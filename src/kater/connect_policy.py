"""Catalog Connect origin policy, plus the shared secret-sink re-export.

Secret persist lives in ``kater.secret_persist`` so manual
``POST /credentials`` and outbound OAuth share one deny-default gate.
This module keeps public Connect origin rules: HTTPS base is configured,
never taken from ``Host`` / ``X-Forwarded-Host``.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from kater.secret_persist import (
    ConnectSecretDecision as ConnectSecretDecision,
)
from kater.secret_persist import (
    connect_secret_decision as connect_secret_decision,
)
from kater.settings import KaterSettings, is_public_settings, load_settings

PUBLIC_BASE_URL_ENV = "KATER_CONNECT_PUBLIC_BASE_URL"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ConnectOriginError(ValueError):
    """Configured or request origin is not safe for OAuth redirects."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def origin_of(url: str, *, allow_path: bool = False) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ConnectOriginError("invalid_connect_base_url")
    if parsed.username or parsed.password:
        raise ConnectOriginError("invalid_connect_base_url")
    if parsed.params or parsed.query or parsed.fragment:
        raise ConnectOriginError("invalid_connect_base_url")
    if parsed.path not in {"", "/"} and not allow_path:
        raise ConnectOriginError("invalid_connect_base_url")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ConnectOriginError("invalid_connect_base_url")
    return f"{parsed.scheme}://{parsed.netloc}"


def validate_public_https_base(url: str) -> str:
    origin = origin_of(url)
    if urlparse(origin).scheme != "https":
        raise ConnectOriginError("public_base_url_must_be_https")
    return origin


def validate_dev_base(url: str) -> str:
    origin = origin_of(url)
    host = (urlparse(origin).hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        raise ConnectOriginError("dev_base_url_must_be_loopback")
    return origin


def assert_safe_oauth_base(base_url: str) -> str:
    """Absolute OAuth base: HTTPS anywhere, or HTTP on loopback only."""
    origin = origin_of(base_url)
    parsed = urlparse(origin)
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in LOOPBACK_HOSTS:
        raise ConnectOriginError("invalid_connect_base_url")
    return origin


def resolve_connect_base_url(
    request_base: str,
    settings: KaterSettings | None = None,
    *,
    pending_redirect: str | None = None,
) -> str:
    """Canonical Connect origin. Public mode never trusts the request Host."""
    settings = settings or load_settings()
    configured = os.environ.get(PUBLIC_BASE_URL_ENV, "").strip()
    if is_public_settings(settings):
        if not configured:
            raise ConnectOriginError("public_base_url_required")
        return validate_public_https_base(configured)
    if configured:
        return validate_dev_base(configured)
    try:
        return validate_dev_base(request_base)
    except ConnectOriginError:
        if pending_redirect:
            return validate_dev_base(origin_of(pending_redirect, allow_path=True))
        raise


def safe_catalog_url(
    request_base: str,
    settings: KaterSettings | None = None,
    *,
    pending_redirect: str | None = None,
    query: str = "view=catalog",
) -> str:
    """Catalog return URL, or a same-origin relative path if origin is unsafe."""
    try:
        base = resolve_connect_base_url(request_base, settings, pending_redirect=pending_redirect)
    except ConnectOriginError:
        return "/?" + query
    return base.rstrip("/") + "/?" + query
