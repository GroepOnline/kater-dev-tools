from __future__ import annotations

import json
from pathlib import Path

from kater.storage import (
    _jsonl_prune,
    count_events,
    insert_event,
    prune_all,
    query_events,
    query_gate_audit,
    record_gate_audit,
    reset_db_cache,
)

# ── SQLite query filters ────────────────────────────────────────────


def test_query_events_with_success_filter() -> None:
    insert_event({"type": "tool_call", "name": "a", "timestamp": 1.0, "success": True})
    insert_event({"type": "tool_call", "name": "b", "timestamp": 2.0, "success": False})

    good = query_events(success=True)
    bad = query_events(success=False)

    assert len(good) == 1
    assert good[0]["name"] == "a"
    assert len(bad) == 1
    assert bad[0]["name"] == "b"


def test_query_events_with_since_filter() -> None:
    insert_event({"type": "tool_call", "name": "old", "timestamp": 1.0, "success": True})
    insert_event({"type": "tool_call", "name": "new", "timestamp": 100.0, "success": True})

    recent = query_events(since=50.0)
    assert len(recent) == 1
    assert recent[0]["name"] == "new"


def test_query_events_newest_first() -> None:
    insert_event({"type": "tool_call", "name": "first", "timestamp": 1.0, "success": True})
    insert_event({"type": "tool_call", "name": "second", "timestamp": 2.0, "success": True})

    results = query_events(newest_first=True, limit=10)
    assert len(results) == 2
    assert results[0]["name"] == "second"
    assert results[1]["name"] == "first"


def test_query_events_with_limit() -> None:
    for i in range(5):
        insert_event({"type": "tool_call", "name": f"t{i}", "timestamp": float(i), "success": True})

    results = query_events(limit=2)
    assert len(results) == 2  # limited output
    assert results[0]["name"] == "t0"
    assert results[1]["name"] == "t1"


# ── Prune ───────────────────────────────────────────────────────────


def test_prune_all_sqlite_no_op_when_under_cap() -> None:
    """prune_all returns 0 when events are below MAX_ROWS_ON_DISK."""
    dropped = prune_all()
    assert dropped == 0


def test_prune_all_sqlite_trims_excess(monkeypatch) -> None:
    """When rows exceed MAX_ROWS_ON_DISK, prune_all drops the oldest."""
    # Temporarily lower the cap so we can trigger pruning quickly.
    monkeypatch.setattr("kater.storage.MAX_ROWS_ON_DISK", 5)
    # Also lower the prune-check frequency so it fires on every insert.
    monkeypatch.setattr("kater.storage._PRUNE_EVERY", 1)
    for i in range(10):
        insert_event({"type": "tool_call", "name": f"e{i}", "timestamp": float(i), "success": True})
    count = count_events()
    assert count <= 5, f"expected ≤5 events after prune, got {count}"


def test_jsonl_prune_trims_excess_lines(tmp_path: Path, monkeypatch) -> None:
    """_jsonl_prune keeps only the most recent MAX_ROWS_ON_DISK lines."""
    from kater.settings import load_settings, save_settings

    settings = load_settings()
    settings.storage_backend = "jsonl"
    save_settings(settings)
    reset_db_cache()

    jsonl = tmp_path / ".kater" / "telemetry.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)

    # Write 10 lines, should keep only the last MAX_ROWS_ON_DISK
    monkeypatch.setattr("kater.storage._jsonl_path", lambda: jsonl)
    monkeypatch.setattr("kater.storage.MAX_ROWS_ON_DISK", 5)

    for i in range(10):
        line = json.dumps({"type": "tool_call", "name": f"e{i}", "timestamp": float(i)}) + "\n"
        jsonl.write_text(jsonl.read_text() + line if jsonl.exists() else line, encoding="utf-8")

    dropped = _jsonl_prune()
    assert dropped == 5

    lines = jsonl.read_text().strip().split("\n")
    assert len(lines) == 5

    # Cleanup
    settings.storage_backend = "sqlite"
    save_settings(settings)
    reset_db_cache()


# ── Gate audit trail ────────────────────────────────────────────────


def test_record_and_query_gate_audit() -> None:
    row_id = record_gate_audit(
        action="merge_applied",
        pr_number=42,
        verdict="PASS",
        reasons=["test"],
        expected_head_sha="abc123",
        applied_head_sha="abc123",
        actor="ci-bot",
        detail="squash merge",
    )
    assert row_id > 0

    rows = query_gate_audit(pr_number=42, limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "merge_applied"
    assert rows[0]["pr_number"] == 42


def test_query_gate_audit_without_pr_filter() -> None:
    """query_gate_audit without pr_number returns all rows."""
    record_gate_audit(
        action="merge_rejected", pr_number=1, verdict="BLOCK", reasons=["NO_REVIEWS"]
    )
    record_gate_audit(
        action="merge_applied", pr_number=2, verdict="PASS", reasons=[]
    )

    rows = query_gate_audit(limit=100)
    assert len(rows) >= 2


def test_query_gate_audit_respects_limit() -> None:
    for i in range(5):
        record_gate_audit(
            action="merge_rejected", pr_number=i, verdict="BLOCK", reasons=["test"]
        )

    rows = query_gate_audit(limit=2)
    assert len(rows) == 2


# ── JSONL backend query filters ─────────────────────────────────────


def test_jsonl_query_filters(monkeypatch, tmp_path: Path) -> None:
    """Exercise all JSONL query filter branches."""
    from kater.settings import load_settings, save_settings

    settings = load_settings()
    settings.storage_backend = "jsonl"
    save_settings(settings)
    reset_db_cache()

    jsonl = tmp_path / ".kater" / "telemetry.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kater.storage._jsonl_path", lambda: jsonl)

    # Insert a mix of events
    for i in range(10):
        insert_event({
            "type": "tool_call" if i % 2 == 0 else "error",
            "name": f"e{i}",
            "timestamp": float(i),
            "success": i % 3 != 0,
        })

    # Query with since filter
    recent = query_events(since=5.0)
    assert all(e["timestamp"] >= 5.0 for e in recent)

    # Query with success filter
    good = query_events(success=True)
    assert all(e["success"] for e in good)

    # Query newest_first
    newest = query_events(newest_first=True, limit=3)
    assert len(newest) <= 3

    # Query with name filter
    named = query_events(name="e5")
    assert len(named) == 1
    assert named[0]["name"] == "e5"

    # Cleanup
    settings.storage_backend = "sqlite"
    save_settings(settings)
    reset_db_cache()
