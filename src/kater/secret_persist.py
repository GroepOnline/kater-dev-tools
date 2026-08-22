"""Local-settings credential persist policy for dashboard-supplied credentials.

Dashboard credential saves (manual ``POST /credentials`` and outbound OAuth
token exchange) persist to the gitignored ``.kater/settings.json``, which
``save_settings`` writes 0600 with a 0700 directory. Values are masked in
every API response (``to_safe_dict``). ChefVault remains the referenced team
broker (``docs/ops/chefvault.md``); this module does not write Vault items,
mcp.json, or git.

Catalog Connect (#21) shares this decision so both flows stay one gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from kater.settings import KaterSettings

SINK_LOCAL_SETTINGS = "local-settings"


@dataclass(frozen=True)
class ConnectSecretDecision:
    allowed: bool
    sink: str
    reason: str
    persist_local_settings: bool

    def as_error(self) -> dict[str, str]:
        return {"error": self.reason, "message": self.reason}


def connect_secret_decision(settings: KaterSettings | None = None) -> ConnectSecretDecision:
    """Local 0600 settings persistence is always allowed."""
    return ConnectSecretDecision(True, SINK_LOCAL_SETTINGS, "ok", True)
