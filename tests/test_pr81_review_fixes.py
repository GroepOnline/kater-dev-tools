from __future__ import annotations

import importlib.util
import logging
import re

import kater.api as api
import kater.profiles as profiles
from kater.web import dashboard as dashboard_module
from kater.web import render_dashboard


def _request(query: dict[str, list[str]] | None = None) -> api.Request:
    return api.Request(
        method="GET",
        path="/api/events",
        query=query or {},
        headers={},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://localhost",
    )


def test_dashboard_is_native_and_has_no_review_fix_layer():
    assert render_dashboard is dashboard_module.render_dashboard
    assert not hasattr(dashboard_module, "_PR81_REVIEW_FIXES_APPLIED")
    assert importlib.util.find_spec("kater.web.review_fixes") is None


def test_dashboard_javascript_helpers_and_oauth_route_are_valid():
    html = render_dashboard()
    assert "setTimeout" in html
    assert re.search(r"function\s+sleep\s*\(", html)
    assert "/authorize" in html
    assert "/oauth/authorize" not in html


def test_dashboard_confirm_actions_are_specific():
    html = render_dashboard()
    for label in ("Enable", "Disable", "Save &amp; connect"):
        assert label in html


def test_dashboard_primary_copy_is_sentence_case():
    html = render_dashboard()
    # These were the old shouting labels patched at import time. The native
    # dashboard may change wording, but must not regress to that copy.
    for label in (
        "CONTROL PLANE",
        "KEY METRICS",
        "SERVER CATALOG",
        "TOOL PERFORMANCE",
        "DEPLOYMENT CONFIGS",
        "GATEWAY CONFIG",
        "Save Settings",
    ):
        assert label not in html


def test_events_returns_newest_matching_rows_first(monkeypatch):
    import kater.storage as storage

    rows = [
        {"type": "tool_call", "name": "three", "timestamp": 3.0, "success": True},
        {"type": "tool_call", "name": "two", "timestamp": 2.0, "success": True},
    ]
    query_args = {}

    def query_events(**kwargs):
        query_args.update(kwargs)
        return rows

    monkeypatch.setattr(storage, "query_events", query_events)
    response = api._events(
        _request(
            {
                "limit": ["5000"],
                "name": ["github"],
                "since": ["1.5"],
                "success": ["TRUE"],
            }
        )
    )
    assert response.status == 200
    assert [event["name"] for event in response.payload["events"]] == ["three", "two"]
    assert query_args == {
        "limit": 1000,
        "name": "github",
        "since": 1.5,
        "success": True,
        "newest_first": True,
    }


class _Status:
    def to_dict(self):
        return {
            "name": "github",
            "healthy": True,
            "tool_count": 4,
            "latency_ms": 12,
            "breaker_state": "closed",
        }


class _Proxy:
    def statuses(self):
        return [_Status()]


def test_backends_accepts_injected_proxy_and_returns_compatible_shape(monkeypatch):
    import kater.telemetry as telemetry

    monkeypatch.setattr(profiles, "all_tool_sources", lambda: [])
    monkeypatch.setattr(telemetry, "status_overview", lambda: {"servers": {"enabled": 1}})
    response = api._backends(_request(), proxy_factory=lambda: _Proxy())
    assert response.status == 200
    assert response.payload["backends"] == response.payload["servers"]
    assert response.payload["backends"][0]["name"] == "github"


def test_backends_failure_is_observable(monkeypatch, caplog):
    import kater.telemetry as telemetry

    secret = "sensitive internal provider response: tenant=private-example"

    class FailingProxy:
        def statuses(self):
            raise RuntimeError(secret)

    monkeypatch.setattr(profiles, "all_tool_sources", lambda: [])
    monkeypatch.setattr(telemetry, "status_overview", lambda: {"servers": {}})
    with caplog.at_level(logging.ERROR):
        response = api._backends(_request(), proxy_factory=lambda: FailingProxy())
    assert response.status == 503
    assert response.payload["error"] == "backend_status_unavailable"
    assert response.payload["message"] == (
        "Backend status collection failed; check gateway logs and retry."
    )
    assert response.payload["backends"] == []
    assert response.payload["servers"] == []
    assert set(response.payload) == {
        "error",
        "message",
        "backends",
        "servers",
        "totals",
    }
    assert secret not in repr(response.payload)
    assert "failed to collect backend statuses" in caplog.text
    assert secret in caplog.text
