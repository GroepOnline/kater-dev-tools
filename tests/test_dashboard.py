"""Native dashboard rendering and dashboard/API coupling."""

from __future__ import annotations

import re

import pytest

from kater.api import ROUTER
from kater.web import render_dashboard
from kater.web.dashboard import (
    _HTML,
    _VIEW_CATALOG,
    _VIEW_DASHBOARD,
    _VIEW_DEPLOY,
    _VIEW_EVALS,
    _VIEW_SETTINGS,
)


def test_render_dashboard_is_a_full_document():
    html = render_dashboard()
    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html and "</style>" in html
    assert "<script>" in html and "</script>" in html
    assert html.rstrip().endswith("</html>")
    assert 'id="catalog-search"' in html


def test_dashboard_injects_configured_ws_port():
    assert "window.KATER_CONFIG={wsPort:12345}" in render_dashboard(ws_port=12345)
    assert "wsPort:9092" in render_dashboard()


def test_dashboard_uses_first_party_oauth_client_without_runtime_registration():
    html = render_dashboard()
    assert re.search(r"client_id\s*:\s*['\"]kater-dashboard['\"]", html)
    assert re.search(r"['\"]/authorize['\"]", html)
    assert "fetch('/register'" not in html
    assert "params.get('api_key')" not in html
    assert "/api/ws-ticket" in html
    assert "ticket=" in html
    assert "token=" not in html


def test_dashboard_status_and_command_ui_are_operator_focused():
    html = render_dashboard()
    assert 'id="ws-status"' in html
    assert 'id="ws-dot"' in html
    assert 'placeholder="Command"' in html
    assert 'class="cmd-hint"' not in html


def test_dashboard_contains_only_real_api_route_families():
    html = render_dashboard()
    for path in (
        "/api/status",
        "/api/events",
        "/api/backends",
        "/api/profiles",
        "/api/catalog",
        "/api/evals",
        "/api/deploy",
        "/api/settings",
        "/api/mcp/servers/",
        "/api/tunnel",
        "/api/ws-ticket",
    ):
        assert path in html

    for fake_path in (
        "/api/command",
        "/api/servers/",
        "/api/tunnel/toggle",
        "/api/deploy/config",
        "/oauth/authorize",
    ):
        assert fake_path not in html


def test_dashboard_includes_mutation_route_actions():
    html = render_dashboard()
    # Concrete route/method compatibility is checked independently below;
    # helper wrappers are free to encapsulate the POST option.
    assert "/credentials" in html
    assert re.search(r"['\"]start['\"]", html)
    assert re.search(r"['\"]stop['\"]", html)


def test_each_view_is_present_via_its_own_seam():
    # The per-view constants must each own exactly their view and compose
    # into the single _HTML body (deletion test: drop one -> a view vanishes).
    for view_id, const in [
        ("view-dashboard", _VIEW_DASHBOARD),
        ("view-catalog", _VIEW_CATALOG),
        ("view-evals", _VIEW_EVALS),
        ("view-deploy", _VIEW_DEPLOY),
        ("view-settings", _VIEW_SETTINGS),
    ]:
        assert f'id="{view_id}"' in const, view_id
        assert const in _HTML, view_id
        assert f'id="{view_id}"' in render_dashboard(), view_id


def test_dashboard_tabs_have_complete_aria_contract():
    html = render_dashboard()
    views = ["dashboard", "catalog", "evals", "deploy", "settings"]

    tablist = re.search(r"<[^>]*role=['\"]tablist['\"][^>]*>", html)
    assert tablist and 'aria-label="Dashboard views"' in tablist.group()
    assert "ArrowRight" in html
    assert "ArrowLeft" in html
    assert "Home" in html
    assert "End" in html

    for index, view in enumerate(views):
        expected_selected = "true" if index == 0 else "false"
        expected_tabindex = "0" if index == 0 else "-1"
        tab = re.search(rf"<[^>]*id=['\"]tab-{view}['\"][^>]*>", html)
        panel = re.search(rf"<[^>]*id=['\"]view-{view}['\"][^>]*>", html)
        assert tab and panel

        tab_markup = tab.group()
        assert 'role="tab"' in tab_markup
        assert f'aria-selected="{expected_selected}"' in tab_markup
        assert f'aria-controls="view-{view}"' in tab_markup
        assert f'tabindex="{expected_tabindex}"' in tab_markup

        panel_markup = panel.group()
        assert 'role="tabpanel"' in panel_markup
        assert f'aria-labelledby="tab-{view}"' in panel_markup
        assert 'tabindex="0"' in panel_markup
        assert (" hidden" in panel_markup) is (index > 0)


# (method, concrete-path) pairs that the dashboard JS fetches. Sample values
# stand in for the {name}/{fmt}/{provider}/{action} params.
DASHBOARD_ENDPOINTS = [
    ("GET", "/api/status"),
    ("GET", "/api/events"),
    ("GET", "/api/backends"),
    ("GET", "/api/profiles"),
    ("GET", "/api/catalog"),
    ("GET", "/api/evals"),
    ("GET", "/api/deploy"),
    ("GET", "/api/deploy/json"),
    ("GET", "/api/settings"),
    ("GET", "/api/tunnel"),
    ("GET", "/api/mcp/servers/github"),
    ("POST", "/api/mcp/servers/github/enable"),
    ("POST", "/api/mcp/servers/github/disable"),
    ("POST", "/api/mcp/servers/github/credentials"),
    ("POST", "/api/tunnel/cloudflare/start"),
    ("POST", "/api/tunnel/cloudflare/stop"),
    ("POST", "/api/tunnel/tailscale/start"),
    ("POST", "/api/tunnel/tailscale/stop"),
    ("POST", "/api/ws-ticket"),
    ("POST", "/api/settings"),
]


@pytest.mark.parametrize("method,path", DASHBOARD_ENDPOINTS)
def test_dashboard_endpoint_exists_in_router(method, path):
    assert ROUTER.match(method, path) is not None, f"{method} {path} has no route"


def test_dashboard_delegates_confirm_and_clears_timeouts():
    html = render_dashboard()
    assert "function trackedTimeout(fn, ms)" in html
    assert (
        "onEl(document, 'click'" in html
        or "document.addEventListener('click'" in html
    )
    assert "clearTimeout(" in html


def test_dashboard_dialogs_trap_focus_and_restore_background():
    html = render_dashboard()
    assert "function openDialog(dialog, initialFocus, onEscape)" in html
    assert "function closeDialog(dialog)" in html
    assert "event.key !== 'Tab'" in html
    assert "event.shiftKey" in html
    assert "element.inert = true" in html
    assert "element.inert = inert" in html
    assert "element.setAttribute('aria-hidden', 'true')" in html
    assert "priorFocus.isConnected" in html
    assert "openDialog($('confirm'), confirmCtx.ok, closeConfirm)" in html
    assert "openDialog($('auth-gate'), $('auth-key'))" in html
    assert "closeDialog($('auth-gate'))" in html


def test_dashboard_websocket_tracks_connection_and_retry_lifecycle():
    html = render_dashboard()
    for marker in (
        "wsConnecting: false",
        "wsOpen: false",
        "wsRetry: null",
        "function clearWsRetry()",
        "function scheduleWsReconnect()",
        "state.destroyed || state.wsConnecting || state.wsOpen || state.ws",
        "generation !== state.wsGeneration",
        "state.wsGeneration++",
    ):
        assert marker in html
    assert html.count("clearWsRetry();") >= 4


def test_dashboard_feed_fallback_timestamp_uses_epoch_seconds():
    html = render_dashboard()
    assert "event.timestamp != null ? event.timestamp" in html
    assert "event.ts != null ? event.ts" in html
    assert "Date.now() / 1000" in html
    assert "event.timestamp || event.ts || Date.now()" not in html


def test_dashboard_topology_scales_in_both_dimensions():
    html = render_dashboard()
    assert "const radius = {x: width * .38, y: height * .34}" in html
    assert "Math.sin(angle) * radius.y" in html
    assert "Math.sin(angle) * 72" not in html
