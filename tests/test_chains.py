from __future__ import annotations

from kater.chains import list_chains


def test_lists_profile_chains() -> None:
    chains = list_chains("research")

    assert [chain.name for chain in chains] == ["research_brief"]


def test_unknown_profile_has_no_chains() -> None:
    assert list_chains("unknown") == []
