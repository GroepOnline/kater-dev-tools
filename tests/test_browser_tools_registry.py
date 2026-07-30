from __future__ import annotations

from collections.abc import Iterator

import pytest

from kater.browser import reset_manager
from kater.browser.tools import BROWSER_TOOL_SPECS
from kater.registry import (
    build_native_tools,
    kater_browser_providers,
    kater_browser_sessions,
    tools_for_profile,
)

_BROWSER_NAMES = {spec["name"] for spec in BROWSER_TOOL_SPECS}
_EXPECTED_BROWSER_NAMES = {
    "kater_browser_open",
    "kater_browser_act",
    "kater_browser_screenshot",
    "kater_browser_sessions",
    "kater_browser_close",
    "kater_browser_providers",
}


@pytest.fixture(autouse=True)
def _isolate_browser_manager() -> Iterator[None]:
    reset_manager()
    yield
    reset_manager()


def test_browser_tools_registered_in_build_native_tools() -> None:
    names = {tool.name for tool in build_native_tools()}
    assert _EXPECTED_BROWSER_NAMES == _BROWSER_NAMES
    assert _EXPECTED_BROWSER_NAMES <= names


def test_browser_tools_available_on_core_profile() -> None:
    names = {tool.name for tool in tools_for_profile("core")}
    assert _EXPECTED_BROWSER_NAMES <= names


def test_browser_tool_risks_match_specs() -> None:
    by_name = {tool.name: tool for tool in build_native_tools()}
    for spec in BROWSER_TOOL_SPECS:
        tool = by_name[spec["name"]]
        assert tool.risk == spec["risk"]
        assert tool.profile == "core"
        assert tool.description == spec["description"]


def test_kater_browser_providers_reports_backends() -> None:
    payload = kater_browser_providers()
    assert "providers" in payload
    assert isinstance(payload["providers"], list)
    assert payload["providers"]


def test_kater_browser_sessions_lists_empty_when_reset() -> None:
    payload = kater_browser_sessions()
    assert payload["sessions"] == []
    assert "stats" in payload
