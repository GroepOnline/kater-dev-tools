"""Deny-default secret persist policy for dashboard-supplied credentials.

Raw credential values must not land in ``.kater/settings.json`` on a
public or company-control deployment. Local 0600 settings persistence is an
explicit development opt-in. ChefVault is the referenced durable sink
(``docs/ops/chefvault.md``); this module does not write Vault items, mcp.json,
or git.

Catalog Connect (#21) reuses the same decision so OAuth tokens and manual
``POST /api/mcp/servers/{name}/credentials`` share one fail-closed gate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from kater.settings import KaterSettings, is_public_settings, load_settings

ALLOW_LOCAL_SETTINGS_ENV = "KATER_CONNECT_ALLOW_LOCAL_SETTINGS"
SINK_ENV = "KATER_CONNECT_SECRET_SINK"

SINK_LOCAL_SETTINGS = "local-settings"
SINK_CHEFVAULT = "chefvault"

CONNECT_SECRET_MESSAGES = {
    "secret_sink_required": (
        "Public/company-control cannot persist raw credential values "
        "to local settings. An approved durable secret sink is required; "
        "ChefVault is the referenced company-control broker "
        "(docs/ops/chefvault.md). This gateway does not write Vault items."
    ),
    "chefvault_persist_unavailable": (
        "KATER_CONNECT_SECRET_SINK=chefvault is referenced only. This "
        "gateway will not write credentials to ChefVault or settings.json. "
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
