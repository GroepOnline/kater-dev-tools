"""Private ChefVault integration for Kater.

Loaded through ``KATER_EXTENSIONS_MODULE=kater.chefvault_extension``. The gateway
proxies a dedicated profile-only MCP process; that process never returns secret
values in MCP responses and materializes only broker-token-scoped profiles.
"""

from __future__ import annotations

from kater.profiles import McpServerConfig, RiskLevel, ToolSource, Transport

PRIVATE_PROFILES = {"chef-vault"}

TOOL_SOURCES = (
    ToolSource(
        name="chefvault",
        description=(
            "ChefVault project-profile catalog and mode-0600 runtime materialization. "
            "Backed by the collection-scoped Vaultwarden broker."
        ),
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"chef-vault"},
        env=["CHEF_VAULT_BROKER_URL", "CHEF_VAULT_BROKER_TOKEN", "CHEF_VAULT_RUNTIME_DIR"],
        default_enabled=False,
        context_cost=2,
        mcp=McpServerConfig(
            command="chefvault-profile-mcp",
            env_template={
                "CHEF_VAULT_BROKER_URL": "${CHEF_VAULT_BROKER_URL}",
                "CHEF_VAULT_BROKER_TOKEN": "${CHEF_VAULT_BROKER_TOKEN}",
                "CHEF_VAULT_RUNTIME_DIR": "${CHEF_VAULT_RUNTIME_DIR}",
            },
        ),
    ),
)
