"""Dashboard rendering + dashboard<->API path coupling.

The dashboard is a deep module behind one interface (`render_dashboard`).
These tests guard two things the design review flagged:
  1. The internal per-view seams still compose into the full document.
  2. Every REST path the dashboard's JS calls actually exists in the API
     RouteTable (catches drift like the previously-missing /api/tunnel route).
"""

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
    assert "client_id: 'kater-dashboard'" in html
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

    assert 'role="tablist" aria-label="Dashboard views"' in html
    assert "function initTabNavigation()" in html
    assert "ArrowRight" in html
    assert "ArrowLeft" in html
    assert "Home" in html
    assert "End" in html

    for index, view in enumerate(views):
        expected_selected = "true" if index == 0 else "false"
        expected_tabindex = "0" if index == 0 else "-1"
        expected_hidden = "" if index == 0 else " hidden"

        assert f'id="tab-{view}" role="tab"' in html
        assert f'aria-selected="{expected_selected}"' in html
        assert f'aria-controls="view-{view}" tabindex="{expected_tabindex}"' in html
        assert re.search(
            rf'id="view-{view}"[^>]*role="tabpanel"'
            rf'[^>]*aria-labelledby="tab-{view}"'
            rf'[^>]*tabindex="0"[^>]*{expected_hidden}>',
            html,
        )


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
    ("GET", "/api/mcp/servers/github"),
    ("POST", "/api/mcp/servers/github/enable"),
    ("POST", "/api/mcp/servers/github/disable"),
    ("POST", "/api/mcp/servers/github/toggle"),
    ("POST", "/api/tunnel/cloudflare/start"),
    ("POST", "/api/tunnel/tailscale/start"),
    ("POST", "/api/ws-ticket"),
    ("POST", "/api/settings"),
]


@pytest.mark.parametrize("method,path", DASHBOARD_ENDPOINTS)
def test_dashboard_endpoint_exists_in_router(method, path):
    assert ROUTER.match(method, path) is not None, f"{method} {path} has no route"


def test_dashboard_delegates_confirm_and_clears_timeouts():
    html = render_dashboard()
    assert (
        "onEl(document, 'click'" in html
        or "document.addEventListener('click'" in html
    )
    assert (
        "e.target.closest('[data-confirm]')" in html
        or "target.closest('[data-confirm]')" in html
    )
    assert "clearTimeout(" in html
    assert "._hideTimer" in html
