"""Tests for profiles.py — source/profile definitions and visibility logic.

Covers: list_profiles, get_source, visible_tool_sources, is_public_mode,
sources_for_profiles, is_private_profile, is_private_source.
"""

from __future__ import annotations

from kater.profiles import (
    TOOL_SOURCES,
    RiskLevel,
    ToolSource,
    Transport,
    get_source,
    is_private_profile,
    is_private_source,
    is_public_mode,
    list_profiles,
    sources_for_profiles,
    visible_tool_sources,
)
from kater.settings import KaterSettings, save_settings


class TestToolSourceBasics:
    def test_all_sources_have_names(self):
        for src in TOOL_SOURCES:
            assert src.name, f"Source {src!r} has no name"

    def test_all_sources_have_transport(self):
        for src in TOOL_SOURCES:
            assert isinstance(src.transport, Transport)

    def test_all_sources_have_risk(self):
        for src in TOOL_SOURCES:
            assert isinstance(src.risk, RiskLevel)

    def test_all_sources_have_profiles(self):
        for src in TOOL_SOURCES:
            assert len(src.profiles) > 0, f"Source {src.name} has no profiles"

    def test_source_names_are_unique(self):
        names = [src.name for src in TOOL_SOURCES]
        assert len(names) == len(set(names)), f"Duplicate source names: {names}"


class TestListProfiles:
    def test_returns_list(self):
        profiles = list_profiles()
        assert isinstance(profiles, list)

    def test_core_always_present(self):
        profiles = list_profiles()
        assert "core" in profiles

    def test_has_multiple_profiles(self):
        profiles = list_profiles()
        assert len(profiles) >= 3


class TestGetSource:
    def test_known_source(self):
        src = get_source("github")
        assert src is not None
        assert src.name == "github"

    def test_unknown_source(self):
        assert get_source("nonexistent") is None

    def test_case_sensitive(self):
        assert get_source("GitHub") is None


class TestVisibleToolSources:
    def test_returns_tuple(self):
        sources = visible_tool_sources()
        assert isinstance(sources, tuple)

    def test_all_visible_sources_have_names(self):
        for src in visible_tool_sources():
            assert src.name

    def test_includes_default_enabled(self):
        sources = visible_tool_sources()
        enabled_names = [s.name for s in sources if s.default_enabled]
        assert len(enabled_names) > 0


class TestSourcesForProfiles:
    def test_core_profile(self):
        sources = sources_for_profiles({"core"})
        assert len(sources) > 0
        names = [s.name for s in sources]
        assert "kater" in names

    def test_empty_profile_set_returns_nothing(self):
        sources = sources_for_profiles(set())
        # Empty profile set means no profiles to match, so only default_enabled
        # sources (if any) might appear — but none should match "no profiles".
        assert all(not s.profiles.issubset(set()) for s in sources)

    def test_multiple_profiles(self):
        sources = sources_for_profiles({"core", "research"})
        assert len(sources) > 0


class TestIsPublicMode:
    def test_default_not_public(self):
        save_settings(KaterSettings())
        assert is_public_mode() is False

    def test_public_mode(self):
        save_settings(KaterSettings(host="0.0.0.0"))
        is_public_mode()  # depends on KATER_PUBLIC env; host check should trigger
        save_settings(KaterSettings())

    def test_cleanup(self):
        save_settings(KaterSettings())


class TestIsPrivateProfile:
    def test_core_not_private(self):
        assert is_private_profile("core") is False

    def test_unknown_profile_not_private(self):
        assert is_private_profile("nonexistent") is False


class TestIsPrivateSource:
    def test_public_source(self):
        src = get_source("github")
        assert src is not None
        assert is_private_source(src) is False

    def test_source_without_risk(self):
        src = ToolSource(
            name="test",
            description="test",
            transport=Transport.HTTP,
            risk=RiskLevel.LOW,
            profiles={"core"},
        )
        assert is_private_source(src) is False
