"""Runtime wiring for schema migrate + browser session janitor hooks."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

from kater import migrations
from kater.runtime import KaterRuntime
from kater.settings import ListenConfig


def test_ensure_migrated_records_browser_and_automations_versions(tmp_path) -> None:
    db_path = tmp_path / "kater.db"
    migrations.ensure_migrated(db_path)

    conn = sqlite3.connect(db_path)
    try:
        versions = [
            row[0]
            for row in conn.execute(
                f"SELECT version FROM {migrations.SCHEMA_TABLE} ORDER BY version"  # noqa: S608
            )
        ]
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        conn.close()

    assert versions == [1, 2, 3, 4, 5, 6]
    assert {
        "browser_sessions",
        "browser_actions",
        "automations",
        "remote_contexts",
        "usage_events",
        "capability_audit",
    } <= tables
    assert migrations.latest_version() == 6


def test_runtime_start_calls_ensure_migrated(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    called: list[bool] = []

    def _fake_ensure_migrated(*_args, **_kwargs) -> None:
        called.append(True)

    monkeypatch.setattr("kater.migrations.ensure_migrated", _fake_ensure_migrated)
    monkeypatch.setattr(
        "kater.api.create_api_server",
        lambda *_a, **_k: MagicMock(),
    )
    monkeypatch.setattr(
        "kater.websocket.create_ws_server",
        lambda *_a, **_k: MagicMock(),
    )
    monkeypatch.setattr(
        "kater.mcp_server.build_sse_app",
        lambda *_a, **_k: MagicMock(),
    )

    class _FakeUvicornServer:
        def __init__(self, _config) -> None:
            self.should_exit = False

        def run(self) -> None:
            return None

    monkeypatch.setattr("uvicorn.Server", _FakeUvicornServer)
    monkeypatch.setattr("uvicorn.Config", lambda *_a, **_k: MagicMock())

    runtime = KaterRuntime(
        profile="core",
        listen=ListenConfig(host="127.0.0.1", api_port=29191, mcp_port=29190, ws_port=29192),
    )
    try:
        runtime.start()
        assert called == [True]
    finally:
        runtime.stop()


def test_runtime_stop_resets_browser_manager(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    reset_calls: list[bool] = []

    monkeypatch.setattr("kater.migrations.ensure_migrated", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "kater.api.create_api_server",
        lambda *_a, **_k: MagicMock(),
    )
    monkeypatch.setattr(
        "kater.websocket.create_ws_server",
        lambda *_a, **_k: MagicMock(),
    )
    monkeypatch.setattr(
        "kater.mcp_server.build_sse_app",
        lambda *_a, **_k: MagicMock(),
    )

    class _FakeUvicornServer:
        def __init__(self, _config) -> None:
            self.should_exit = False

        def run(self) -> None:
            return None

    monkeypatch.setattr("uvicorn.Server", _FakeUvicornServer)
    monkeypatch.setattr("uvicorn.Config", lambda *_a, **_k: MagicMock())

    def _fake_reset() -> None:
        reset_calls.append(True)

    monkeypatch.setattr("kater.browser.session.reset_manager", _fake_reset)

    runtime = KaterRuntime(
        profile="core",
        listen=ListenConfig(host="127.0.0.1", api_port=29291, mcp_port=29290, ws_port=29292),
    )
    runtime.start()
    runtime.stop()
    assert reset_calls == [True]
