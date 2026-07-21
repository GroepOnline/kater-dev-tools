from __future__ import annotations

import json
import sqlite3

import pytest

import kater.storage as storage


@pytest.fixture
def sqlite_db(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(storage._SCHEMA)
    db.executemany(
        """INSERT INTO events
           (type, name, timestamp, duration_ms, success, profile, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("tool_call", "github", 1.0, 10, 0, "core", "{}"),
            ("tool_call", "github", 2.0, 20, 1, "core", "{}"),
            ("tool_call", "github", 3.0, 30, 0, "core", "{}"),
            ("tool_call", "github", 4.0, 40, 0, "core", "{}"),
        ],
    )
    monkeypatch.setattr(storage, "_get_db", lambda: db)
    yield db
    db.close()


def test_sqlite_query_filters_and_bounds_newest_first(sqlite_db) -> None:
    rows = storage._sqlite_query(limit=2, success=False, newest_first=True)

    assert [row["timestamp"] for row in rows] == [4.0, 3.0]
    assert all(row["success"] is False for row in rows)


def test_sqlite_query_default_remains_chronological(sqlite_db) -> None:
    rows = storage._sqlite_query(limit=2)

    assert [row["timestamp"] for row in rows] == [1.0, 2.0]


def test_jsonl_query_filters_and_bounds_newest_first(tmp_path, monkeypatch) -> None:
    path = tmp_path / "telemetry.jsonl"
    events = [
        {"type": "tool_call", "name": "github", "timestamp": 1.0, "success": False},
        {"type": "tool_call", "name": "github", "timestamp": 4.0, "success": False},
        {"type": "tool_call", "name": "github", "timestamp": 2.0, "success": True},
        {"type": "tool_call", "name": "github", "timestamp": 3.0, "success": False},
    ]
    path.write_text(
        "".join(f"{json.dumps(event)}\n" for event in events),
        encoding="utf-8",
    )
    monkeypatch.setattr(storage, "_jsonl_path", lambda: path)

    rows = storage._jsonl_query(limit=2, success=False, newest_first=True)

    assert [row["timestamp"] for row in rows] == [4.0, 3.0]
    assert all(row["success"] is False for row in rows)


def test_jsonl_query_default_remains_chronological(tmp_path, monkeypatch) -> None:
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "".join(
            f'{{"name":"event-{timestamp}","timestamp":{timestamp}}}\n' for timestamp in range(3)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(storage, "_jsonl_path", lambda: path)

    rows = storage._jsonl_query(limit=2)

    assert [row["timestamp"] for row in rows] == [1, 2]
