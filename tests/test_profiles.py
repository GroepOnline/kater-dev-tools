from __future__ import annotations

from kater.profiles import list_profiles, sources_for_profiles


def test_core_profile_is_minimal() -> None:
    sources = sources_for_profiles({"core"})

    assert [source.name for source in sources] == ["kater"]


def test_dev_tools_are_profile_gated() -> None:
    sources = sources_for_profiles({"research"})
    names = {source.name for source in sources}

    assert "kater" in names
    assert "firecrawl" in names
    assert "exa" in names
    assert "resend" not in names


def test_lists_known_profiles() -> None:
    profiles = list_profiles()

    assert "core" in profiles
    assert "ops" in profiles
    assert "demo_private" in profiles
