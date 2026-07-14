"""Dashboard rendering + dashboard<->API path coupling.

The dashboard is a deep module behind one interface (`render_dashboard`).
These tests guard two things the design review flagged:
  1. The internal per-view seams still compose into the full document.
  2. Every REST path the dashboard's JS calls actually exists in the API
     RouteTable (catches drift like the previously-missing /api/tunnel route).
"""

from __future__ import annotations

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


def test_overview_has_situational_awareness_seams():
    # The 2026 redesign leads with triage, not vanity numbers: an exception
    # strip, live KPI sparklines, a 5-state routing table, and a latency strip.
    html = render_dashboard()
    assert 'id="exc-strip"' in html  # triage-first exception strip
    assert 'id="spark-success"' in html and 'id="spark-latency"' in html
    assert 'id="latency-strip"' in html  # canvas latency oscilloscope
    assert "Routing table" in html
    assert 'id="telemetry-stream"' in html


def test_command_palette_is_present():
    # ⌘K command palette is the discoverable entry point for navigation/actions.
    html = render_dashboard()
    assert 'id="cmd-palette"' in html
    assert 'id="palette-input"' in html
    assert 'id="palette-results"' in html


def test_catalog_has_status_facets():
    html = render_dashboard()
    assert 'id="catalog-facets"' in html
    assert 'data-cfilter="needs"' in html
    assert "clearTelemetryStream" in html  # activity clear control
    assert "writeUrlState" in html  # shareable URL state
    assert "context_cost" in html  # routing table uses catalog cost


def test_zero_result_states_have_recovery_actions():
    # Empty states must offer a one-click way out instead of a dead-end note
    # (PR #103): the Catalog and Overview render semantic <button> recovery
    # links that reset the search or the status/route filter.
    html = render_dashboard()
    # Handlers wired to the recovery buttons.
    assert "function clearCatalogSearch" in html
    assert "function resetCatalogFilter" in html
    assert "function resetRouteFilter" in html
    # Labels shown in the empty state, plus the shared styling hook.
    assert "Clear search" in html
    assert "Switch filter to all" in html
    assert "view-empty-link" in html
    # Buttons are defensively typed so they never submit a surrounding form.
    assert "type = 'button'" in html
    # A newer search/filter load invalidates stale in-flight catalog responses.
    assert "catalogLoadSeq" in html


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


# (method, concrete-path) pairs that the dashboard JS fetches. Sample values
# stand in for the {name}/{fmt}/{provider}/{action} params.
DASHBOARD_ENDPOINTS = [
    ("GET", "/api/status"),
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
    ("POST", "/api/settings"),
]


@pytest.mark.parametrize("method,path", DASHBOARD_ENDPOINTS)
def test_dashboard_endpoint_exists_in_router(method, path):
    assert ROUTER.match(method, path) is not None, f"{method} {path} has no route"
