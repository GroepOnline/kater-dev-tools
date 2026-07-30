"""Usage / cost events ledger: store, API, and telemetry emit hook."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from kater import migrations
from kater.control_plane import usage as usage_ledger
from kater.telemetry import TelemetryEvent, record_event
from tests._rest import call as _call


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """
    Provide an isolated working directory and migrated usage ledger database for a test.

    Parameters:
        tmp_path: Temporary directory used as the test's working directory.
        monkeypatch: Pytest fixture used to change the working directory.

    Yields:
        None
    """
    monkeypatch.chdir(tmp_path)
    usage_ledger.reset_cache()
    migrations.ensure_migrated(tmp_path / ".kater" / "kater.db")
    yield
    usage_ledger.reset_cache()


def test_migration_creates_usage_events_table(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    migrations.run_migrations(db)
    conn = sqlite3.connect(db)
    try:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(usage_events)").fetchall()
        }
    finally:
        conn.close()
    assert {
        "id",
        "timestamp",
        "capability",
        "backend",
        "tool_name",
        "account_id",
        "context_id",
        "principal_id",
        "success",
        "duration_ms",
        "cost_units",
        "metadata",
    } <= cols
    assert any(m.name == "usage_events" and m.version == 5 for m in migrations.MIGRATIONS)


def test_record_and_list_usage_events() -> None:
    first = usage_ledger.record_usage_event(
        capability="browser.navigate",
        backend="browser",
        tool_name="navigate",
        account_id="acct_a",
        context_id="ctx_1",
        success=True,
        duration_ms=12.5,
        cost_units=2.0,
        metadata={"outcome": "success"},
    )
    usage_ledger.record_usage_event(
        capability="browser.navigate",
        backend="browser",
        tool_name="navigate",
        success=False,
        duration_ms=40.0,
        cost_units=1.0,
    )
    usage_ledger.record_usage_event(
        capability="computer.screenshot",
        backend="computer",
        success=True,
        duration_ms=5.0,
        cost_units=3.0,
    )

    all_events = usage_ledger.list_usage_events(limit=10)
    assert len(all_events) == 3
    assert all_events[0]["capability"] in {"browser.navigate", "computer.screenshot"}
    assert first["capability"] == "browser.navigate"
    assert first["metadata"]["outcome"] == "success"

    filtered = usage_ledger.list_usage_events(capability="browser.navigate")
    assert len(filtered) == 2
    assert all(e["capability"] == "browser.navigate" for e in filtered)


def test_usage_summary_aggregates_by_capability() -> None:
    for i, ok in enumerate([True, True, False]):
        usage_ledger.record_usage_event(
            capability="cap.a",
            success=ok,
            duration_ms=10.0 * (i + 1),
            cost_units=1.5,
        )
    usage_ledger.record_usage_event(
        capability="cap.b",
        success=True,
        duration_ms=100.0,
        cost_units=4.0,
    )

    summary = usage_ledger.usage_summary()
    assert summary["total_events"] == 4
    assert summary["total_cost_units"] == 8.5
    by_name = {row["capability"]: row for row in summary["capabilities"]}
    assert by_name["cap.a"]["count"] == 3
    assert by_name["cap.a"]["success"] == 2
    assert by_name["cap.a"]["success_rate"] == pytest.approx(66.7, abs=0.1)
    assert by_name["cap.a"]["duration_p50_ms"] > 0
    assert by_name["cap.a"]["duration_p95_ms"] >= by_name["cap.a"]["duration_p50_ms"]
    assert by_name["cap.b"]["total_cost_units"] == 4.0

    only_b = usage_ledger.usage_summary(capability="cap.b")
    assert only_b["total_events"] == 1
    assert [row["capability"] for row in only_b["capabilities"]] == ["cap.b"]


def test_api_usage_list_and_summary() -> None:
    usage_ledger.record_usage_event(
        capability="api.cap",
        backend="proxy",
        tool_name="do",
        success=True,
        duration_ms=8.0,
        cost_units=2.0,
    )
    listed = _call("GET", "/api/usage", query={"limit": ["50"]})
    assert listed.status == 200
    assert listed.payload is not None
    assert listed.payload["total"] >= 1
    assert listed.payload["events"][0]["capability"] == "api.cap"

    filtered = _call("GET", "/api/usage", query={"capability": ["api.cap"]})
    assert filtered.status == 200
    assert filtered.payload is not None
    assert filtered.payload["total"] >= 1

    summary = _call("GET", "/api/usage/summary")
    assert summary.status == 200
    assert summary.payload is not None
    assert "capabilities" in summary.payload
    assert summary.payload["total_events"] >= 1


def test_route_decision_telemetry_emits_usage_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kater.telemetry.insert_event", lambda _event: None)
    record_event(
        TelemetryEvent(
            type="route_decision",
            name="routed.tool",
            success=True,
            duration_ms=15.0,
            metadata={
                "context_id": "ctx_route",
                "account_id": "acct_1",
                "provider": "github",
                "backend": "stdio",
                "tool_name": "search",
                "estimated_units": 7,
                "outcome": "success",
                "error": None,
            },
        )
    )
    events = usage_ledger.list_usage_events(capability="routed.tool")
    assert len(events) == 1
    event: dict[str, Any] = events[0]
    assert event["backend"] == "stdio"
    assert event["tool_name"] == "search"
    assert event["account_id"] == "acct_1"
    assert event["context_id"] == "ctx_route"
    assert event["success"] is True
    assert event["cost_units"] == 7.0
    assert event["metadata"]["outcome"] == "success"


def test_openapi_includes_usage_paths() -> None:
    from kater.openapi_spec import generate_spec

    spec = generate_spec()
    assert "/api/usage" in spec["paths"]
    assert "/api/usage/summary" in spec["paths"]


class TestParseLimit:
    def test_default_when_absent(self) -> None:
        from kater.api.usage_routes import _parse_limit

        req = Request(
            method="GET",
            path="/api/usage",
            query={},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://127.0.0.1",
        )
        assert _parse_limit(req) == 100

    def test_clamps_below_minimum_to_one(self) -> None:
        from kater.api.usage_routes import _parse_limit

        req = Request(
            method="GET",
            path="/api/usage",
            query={"limit": ["0"]},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://127.0.0.1",
        )
        assert _parse_limit(req) == 1

        req.query = {"limit": ["-5"]}
        assert _parse_limit(req) == 1

    def test_clamps_above_maximum(self) -> None:
        from kater.api.usage_routes import _parse_limit

        req = Request(
            method="GET",
            path="/api/usage",
            query={"limit": ["5000"]},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://127.0.0.1",
        )
        assert _parse_limit(req) == 1000

    def test_non_integer_raises_value_error(self) -> None:
        from kater.api.usage_routes import _parse_limit

        req = Request(
            method="GET",
            path="/api/usage",
            query={"limit": ["not-an-int"]},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://127.0.0.1",
        )
        with pytest.raises(ValueError):
            _parse_limit(req)


def test_api_usage_list_rejects_non_integer_limit() -> None:
    resp = _call("GET", "/api/usage", query={"limit": ["not-an-int"]})
    assert resp.status == 400
    assert resp.payload is not None
    assert "limit" in resp.payload["error"].lower()


def test_api_usage_list_clamps_out_of_range_limit() -> None:
    usage_ledger.record_usage_event(
        capability="clamp.cap",
        success=True,
        duration_ms=1.0,
        cost_units=1.0,
    )
    # A limit of 0 is clamped up to 1 rather than rejected.
    resp = _call("GET", "/api/usage", query={"limit": ["0"]})
    assert resp.status == 200
    assert resp.payload is not None
    assert len(resp.payload["events"]) <= 1
