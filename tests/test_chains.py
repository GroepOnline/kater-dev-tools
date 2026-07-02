from __future__ import annotations

from kater.chains import list_chains


def test_lists_all_chains() -> None:
    chains = list_chains()
    names = {chain.name for chain in chains}

    assert "research_brief" in names
    assert "pr_health" in names
    assert "demo_private_chain" in names
    assert len(chains) == 3


def test_lists_profile_chains() -> None:
    chains = list_chains("research")

    assert [chain.name for chain in chains] == ["research_brief"]


def test_unknown_profile_has_no_chains() -> None:
    assert list_chains("unknown") == []


def test_chain_has_steps() -> None:
    chains = list_chains("research")
    brief = chains[0]

    assert len(brief.steps) > 0
    assert brief.steps[0].tool is not None
    assert brief.steps[0].reason is not None


def test_demo_private_chain() -> None:
    chains = list_chains("demo_private")
    assert len(chains) == 1
    assert chains[0].name == "demo_private_chain"
    assert len(chains[0].steps) == 1
    assert chains[0].steps[0].tool == "demo_private_status"
