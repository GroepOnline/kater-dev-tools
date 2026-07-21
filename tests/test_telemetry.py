from __future__ import annotations

from kater.storage import (
    clear_all_events,
    count_events,
    insert_event,
    query_events,
    reset_db_cache,
)
from kater.telemetry import (
    clear_events,
    eval_summary,
    record_chain_run,
    record_error,
    record_server_toggle,
    record_tool_call,
    status_overview,
)


def test_insert_and_query():
    insert_event(
        {
            "type": "tool_call",
            "name": "test_tool",
            "timestamp": 1000.0,
            "duration_ms": 50.0,
            "success": True,
            "profile": "core",
            "metadata": {"key": "val"},
        }
    )
    events = query_events()
    assert len(events) == 1
    assert events[0]["name"] == "test_tool"
    assert events[0]["metadata"] == {"key": "val"}


def test_query_by_type():
    insert_event({"type": "tool_call", "name": "a", "timestamp": 1.0, "success": True})
    insert_event({"type": "chain_run", "name": "b", "timestamp": 2.0, "success": True})
    assert len(query_events(event_type="tool_call")) == 1
    assert len(query_events(event_type="chain_run")) == 1
    assert len(query_events()) == 2


def test_query_by_name():
    insert_event({"type": "tool_call", "name": "github", "timestamp": 1.0, "success": True})
    insert_event({"type": "tool_call", "name": "sentry", "timestamp": 2.0, "success": True})
    assert len(query_events(name="github")) == 1
    assert query_events(name="github")[0]["name"] == "github"


def test_count_events():
    insert_event({"type": "tool_call", "name": "a", "timestamp": 1.0, "success": True})
    insert_event({"type": "error", "name": "b", "timestamp": 2.0, "success": False})
    assert count_events() == 2
    assert count_events(event_type="tool_call") == 1
    assert count_events(event_type="error") == 1


def test_clear_events():
    insert_event({"type": "tool_call", "name": "a", "timestamp": 1.0, "success": True})
    insert_event({"type": "error", "name": "b", "timestamp": 2.0, "success": False})
    cleared = clear_all_events()
    assert cleared == 2
    assert count_events() == 0


def test_record_tool_call():
    record_tool_call("github", success=True, duration_ms=42.5, profile="ops")
    events = query_events(event_type="tool_call")
    assert len(events) == 1
    assert events[0]["name"] == "github"
    assert events[0]["success"] is True
    assert events[0]["duration_ms"] == 42.5


def test_record_chain_run():
    record_chain_run("research_brief", steps=3, success=True, profile="research")
    events = query_events(event_type="chain_run")
    assert len(events) == 1
    assert events[0]["metadata"]["steps"] == 3


def test_record_error():
    record_error("api", "connection refused")
    events = query_events(event_type="error")
    assert len(events) == 1
    assert events[0]["success"] is False
    assert "connection refused" in events[0]["metadata"]["message"]


def test_record_server_toggle():
    record_server_toggle("github", "disable", False)
    events = query_events(event_type="server_toggle")
    assert len(events) == 1
    assert events[0]["metadata"]["enabled"] is False


def test_eval_summary_empty():
    data = eval_summary()
    assert data["total_events"] == 0


def test_eval_summary_with_data():
    record_tool_call("github", success=True, duration_ms=10, profile="ops")
    record_tool_call("github", success=True, duration_ms=30, profile="ops")
    record_tool_call("github", success=False, duration_ms=5, profile="ops")
    record_tool_call("sentry", success=True, duration_ms=20, profile="ops")
    record_chain_run("pr_health", steps=3, success=True, profile="ops")
    record_error("api", "timeout")

    data = eval_summary()
    assert data["total_events"] == 6
    assert data["tool_calls"]["total"] == 4
    assert data["chain_runs"]["total"] == 1
    assert data["errors"]["total"] == 1

    github = data["tool_calls"]["per_tool"]["github"]
    assert github["total"] == 3
    assert github["success"] == 2
    assert github["failed"] == 1
    assert github["success_rate"] == 66.7

    pr = data["chain_runs"]["per_chain"]["pr_health"]
    assert pr["success"] == 1


def test_status_overview():
    data = status_overview()
    assert "version" in data
    assert "servers" in data
    assert data["servers"]["total"] > 0
    assert "telemetry" in data
    assert data["storage_backend"] in ("sqlite", "jsonl")


def test_clear_events_returns_count():
    record_tool_call("a", success=True)
    record_tool_call("b", success=True)
    count = clear_events()
    assert count == 2


def test_jsonl_backend(monkeypatch):
    from kater.settings import load_settings

    settings = load_settings()
    settings.storage_backend = "jsonl"
    from kater.settings import save_settings

    save_settings(settings)
    reset_db_cache()

    record_tool_call("test_jsonl", success=True)
    events = query_events()
    assert len(events) == 1
    assert events[0]["name"] == "test_jsonl"

    settings.storage_backend = "sqlite"
    save_settings(settings)
    reset_db_cache()
