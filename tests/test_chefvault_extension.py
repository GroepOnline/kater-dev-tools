from kater.chefvault_extension import PRIVATE_PROFILES, TOOL_SOURCES
from kater.profiles import RiskLevel, Transport


def test_chefvault_extension_is_private_and_scoped() -> None:
    assert PRIVATE_PROFILES == {"chef-vault"}
    assert len(TOOL_SOURCES) == 1
    source = TOOL_SOURCES[0]
    assert source.name == "chefvault"
    assert source.transport == Transport.STDIO
    assert source.risk == RiskLevel.HIGH
    assert source.profiles == {"chef-vault"}
    assert source.mcp is not None
    assert source.mcp.command == "chefvault-profile-mcp"
    assert set(source.env) == {"CHEF_VAULT_BROKER_URL", "CHEF_VAULT_BROKER_TOKEN"}
