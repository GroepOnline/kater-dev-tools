from __future__ import annotations

import logging

import kater.api as api
import kater.profiles as profiles
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


def test_dashboard_javascript_helpers_and_oauth_route_are_valid():
    html = render_dashboard()
    assert "function trackedTimeout(fn, ms)" in html
    assert "const url = '/authorize'" in html
    assert "/oauth/authorize" not in html
    assert "data.backends || data.servers || []" in html


def test_dashboard_confirm_action_uses_specific_labels():
    html = render_dashboard()
    assert "enable: 'Enable server'" in html
    assert "disable: 'Disable server'" in html
    assert "'save-credentials': 'Save credentials'" in html
    assert "confirmCtx.ok.textContent = labels[action]" in html
    assert 'onclick="runConfirmed()">Confirm</button>' not in html


def test_dashboard_primary_copy_is_sentence_case():
    html = render_dashboard()
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
        {"type": "tool_call", "name": "one", "timestamp": 1.0, "success": True},
        {"type": "tool_call", "name": "two", "timestamp": 2.0, "success": True},
        {"type": "tool_call", "name": "three", "timestamp": 3.0, "success": True},
    ]
    monkeypatch.setattr(storage, "query_events", lambda **_: rows)
    response = api._events(_request({"limit": ["2"]}))
    assert response.status == 200
    assert [event["name"] for event in response.payload["events"]] == ["three", "two"]


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
    class FailingProxy:
        def statuses(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(profiles, "all_tool_sources", lambda: [])
    monkeypatch.setattr(telemetry, "status_overview", lambda: {"servers": {}})
    with caplog.at_level(logging.ERROR):
        response = api._backends(_request(), proxy_factory=lambda: FailingProxy())
    assert response.status == 503
    assert response.payload["error"] == "backend_status_unavailable"
    assert "failed to collect backend statuses" in caplog.text
