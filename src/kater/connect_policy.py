"""Fail-closed Catalog Connect policy: secret storage + request origin.

OAuth access/refresh tokens must not land in ``.kater/settings.json`` on a
public or company-control deployment. Local 0600 settings persistence is an
explicit development opt-in. ChefVault is the referenced durable sink
(``docs/ops/chefvault.md``); this module does not write Vault items, mcp.json,
or git.

Public OAuth redirect/callback URLs must come from a configured HTTPS base,
never from ``Host`` / ``X-Forwarded-Host``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from kater.settings import KaterSettings, is_public_settings, load_settings

ALLOW_LOCAL_SETTINGS_ENV = "KATER_CONNECT_ALLOW_LOCAL_SETTINGS"
SINK_ENV = "KATER_CONNECT_SECRET_SINK"
PUBLIC_BASE_URL_ENV = "KATER_CONNECT_PUBLIC_BASE_URL"

SINK_LOCAL_SETTINGS = "local-settings"
SINK_CHEFVAULT = "chefvault"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

CONNECT_SECRET_MESSAGES = {
    "secret_sink_required": (
        "Public/company-control Catalog Connect cannot persist OAuth tokens "
        "to local settings. An approved durable secret sink is required; "
        "ChefVault is the referenced company-control broker "
        "(docs/ops/chefvault.md). This gateway does not write Vault items."
    ),
    "chefvault_persist_unavailable": (
        "KATER_CONNECT_SECRET_SINK=chefvault is referenced only. Catalog "
        "Connect will not write OAuth tokens to ChefVault or settings.json. "
        "Materialize provider tokens through the ChefVault broker instead."
    ),
    "local_settings_opt_in_required": (
        "Local 0600 .kater/settings.json persistence is disabled unless "
        "KATER_CONNECT_ALLOW_LOCAL_SETTINGS=1 (local development only)."
    ),
    "unknown_secret_sink": (
        "KATER_CONNECT_SECRET_SINK is not an approved value. Allowed names: "
        "local-settings (local opt-in only), chefvault (reference only)."
    ),
}


@dataclass(frozen=True)
class ConnectSecretDecision:
    allowed: bool
    sink: str
    reason: str
    persist_local_settings: bool

    def as_error(self) -> dict[str, str]:
        return {
            "error": self.reason,
            "message": CONNECT_SECRET_MESSAGES.get(self.reason, self.reason),
        }


class ConnectOriginError(ValueError):
    """Configured or request origin is not safe for OAuth redirects."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _configured_sink() -> str:
    raw = os.environ.get(SINK_ENV, "").strip().lower().replace("_", "-")
    if raw in {"chef-vault", "chefvault"}:
        return SINK_CHEFVAULT
    if raw in {"local-settings", "settings", "local"}:
        return SINK_LOCAL_SETTINGS
    return raw


def connect_secret_decision(settings: KaterSettings | None = None) -> ConnectSecretDecision:
    settings = settings or load_settings()
    public = is_public_settings(settings)
    sink = _configured_sink()

    if sink and sink not in {SINK_LOCAL_SETTINGS, SINK_CHEFVAULT}:
        return ConnectSecretDecision(False, sink, "unknown_secret_sink", False)

    if public:
        # Local settings opt-in is ignored on public/company-control hosts.
        if sink == SINK_CHEFVAULT:
            return ConnectSecretDecision(
                False, SINK_CHEFVAULT, "chefvault_persist_unavailable", False
            )
        return ConnectSecretDecision(False, sink or "none", "secret_sink_required", False)

    if sink == SINK_CHEFVAULT:
        return ConnectSecretDecision(False, SINK_CHEFVAULT, "chefvault_persist_unavailable", False)

    if _env_truthy(ALLOW_LOCAL_SETTINGS_ENV) and sink in {"", SINK_LOCAL_SETTINGS}:
        return ConnectSecretDecision(True, SINK_LOCAL_SETTINGS, "ok", True)

    return ConnectSecretDecision(False, sink or "none", "local_settings_opt_in_required", False)


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
        base = resolve_connect_base_url(
            request_base, settings, pending_redirect=pending_redirect
        )
    except ConnectOriginError:
        return "/?" + query
    return base.rstrip("/") + "/?" + query
