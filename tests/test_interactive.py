"""Tests for the interactive TUI loop.

Exercises command dispatch and pure format helpers without a real TTY.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from kater import interactive


def _run_loop(monkeypatch: pytest.MonkeyPatch, lines: list[str]) -> str:
    """
    Run the interactive loop with canned input and capture its output.
    
    Parameters:
    	monkeypatch (pytest.MonkeyPatch): Fixture used to replace the loop's standard streams.
    	lines (list[str]): Input commands to provide to the interactive loop.
    
    Returns:
    	str: Text written to standard output.
    """
    out = io.StringIO()
    monkeypatch.setattr(interactive.sys, "stdout", out)
    monkeypatch.setattr(interactive.sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
    interactive.interactive_loop(profile="core", refresh_interval=999)
    return out.getvalue()


def test_quit_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["quit"])
    assert "stopped" in out.lower()


def test_exit_alias_works(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["exit"])
    assert "stopped" in out.lower()


def test_eof_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, [])
    assert "stopped" in out.lower()


def test_unknown_command_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["bogus-command", "quit"])
    assert "unknown" in out.lower()


def test_help_renders_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["help", "quit"])
    assert "toggle" in out
    assert "profile" in out
    assert "browser" in out
    assert "auto" in out


def test_status_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["status", "quit"])
    assert "KATER" in out


def test_invalid_profile_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["profile not-a-real-profile", "quit"])
    assert "unknown profile" in out.lower()


def test_browser_command_lists_or_soft_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["browser", "quit"])
    assert "BROWSER" in out or "browser lane unavailable" in out.lower()


def test_auto_command_lists_or_soft_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_loop(monkeypatch, ["auto", "quit"])
    assert "AUTOMATIONS" in out or "automations engine unavailable" in out.lower()


def test_handle_toggle_unknown_server(capsys: pytest.CaptureFixture[str]) -> None:
    interactive._handle_toggle("toggle", "not-a-real-server")
    captured = capsys.readouterr()
    assert "unknown server" in captured.out.lower()


def test_handle_toggle_enable_disable() -> None:
    from kater.profiles import get_source
    from kater.settings import KaterSettings, load_settings, save_settings

    save_settings(KaterSettings())
    src = get_source("github")
    assert src is not None

    interactive._handle_toggle("disable", "github")
    assert load_settings().is_server_enabled("github", default=True) is False

    interactive._handle_toggle("enable", "github")
    assert load_settings().is_server_enabled("github", default=True) is True

    interactive._handle_toggle("toggle", "github")
    assert load_settings().is_server_enabled("github", default=True) is False


def test_print_helpers_emit_ansi(capsys: pytest.CaptureFixture[str]) -> None:
    interactive._print_ok("done")
    interactive._print_err("boom")
    captured = capsys.readouterr()
    assert "done" in captured.out
    assert "boom" in captured.out


def test_print_help_lists_all_commands(capsys: pytest.CaptureFixture[str]) -> None:
    interactive._print_help()
    captured = capsys.readouterr()
    for cmd in (
        "toggle",
        "enable",
        "disable",
        "profile",
        "browser",
        "auto",
        "status",
        "clear",
        "quit",
    ):
        assert cmd in captured.out


def test_render_produces_output(capsys: pytest.CaptureFixture[str]) -> None:
    interactive._render("core")
    captured = capsys.readouterr()
    assert "KATER" in captured.out
    assert "SERVERS" in captured.out
    assert "browser" in captured.out.lower()
    assert "autos" in captured.out.lower()


def test_format_status_lines_includes_browser_and_autos() -> None:
    lines = interactive.format_status_lines(
        version="0.0.0",
        profile="core",
        auth_mode="none",
        servers_enabled=2,
        servers_total=3,
        servers_configured=1,
        servers_missing=2,
        browser_sessions=4,
        automations=1,
        events_total=10,
        tool_calls=8,
        errors=1,
        success_rate=87.5,
    )
    joined = "\n".join(lines)
    assert "profile" in joined
    assert "core" in joined
    assert "auth" in joined
    assert "2/3" in joined
    assert "browser 4" in joined
    assert "autos 1" in joined


def test_format_status_lines_soft_unavailable() -> None:
    lines = interactive.format_status_lines(
        version="1",
        profile="core",
        auth_mode="none",
        servers_enabled=0,
        servers_total=0,
        servers_configured=0,
        servers_missing=0,
        browser_sessions=None,
        automations=None,
        events_total=0,
        tool_calls=0,
        errors=0,
        success_rate=0.0,
    )
    joined = "\n".join(lines)
    assert "browser -" in joined
    assert "autos -" in joined


def test_format_server_mark() -> None:
    assert "*" in interactive.format_server_mark(True, True)
    assert "o" in interactive.format_server_mark(True, False)
    assert "-" in interactive.format_server_mark(False, True)


def test_format_session_row() -> None:
    row = interactive.format_session_row(
        {
            "session_id": "bsess_abcdefghijklmnopqrstuvwxyz",
            "state": "ready",
            "current_url": "https://user:hunter2@example.com/path?token=abc",
        }
    )
    assert row == "  bsess_abcdefghijklmn ready    https://example.com/path"
    assert "hunter2" not in row
    assert "token=" not in row


def test_format_session_row_prefers_label() -> None:
    row = interactive.format_session_row(
        {
            "session_id": "bsess_short",
            "state": "ready",
            "label": "checkout",
            "current_url": "https://example.com/secret",
        }
    )
    assert row == "  bsess_short          ready    checkout"


def test_format_automation_row() -> None:
    row = interactive.format_automation_row(
        {
            "name": "nightly-scrape",
            "enabled": True,
            "kind": "cron",
            "last_status": "ok",
        }
    )
    assert "nightly-scrape" in row
    assert "on" in row
    assert "cron" in row
    assert "ok" in row


def test_browser_stats_soft_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def stats(self) -> dict[str, Any]:
            raise RuntimeError("down")

    monkeypatch.setattr(
        "kater.browser.session.get_manager",
        lambda: Boom(),
    )
    assert interactive.browser_stats() is None


def test_automation_count_soft_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(interactive, "_automation_engine", lambda: None)
    assert interactive.automation_count() is None
    assert interactive.automation_list() is None


def test_automation_count_when_engine_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import collections
    FakeAutomation = collections.namedtuple("FakeAutomation", ["id"])
    fake_engine = type(
        "FakeEngine",
        (),
        {
            "count": lambda self: 2,
            "list": lambda self: [FakeAutomation("1"), FakeAutomation("2")],
        },
    )()
    monkeypatch.setattr(interactive, "_automation_engine", lambda: fake_engine)
    count = interactive.automation_count()
    items = interactive.automation_list()

    assert count == 2
    assert items is not None
    assert len(items) == count
    assert [item["id"] for item in items] == ["1", "2"]


def test_automation_items_from_objects() -> None:
    class Fake:
        def __init__(self) -> None:
            self.id = "a1"
            self.name = "demo"
            self.enabled = False
            self.kind = "once"
            self.last_status = "err"

    class Engine:
        def list(self) -> list[Fake]:
            return [Fake()]

    items = interactive._automation_items(Engine())
    assert items == [
        {
            "id": "a1",
            "name": "demo",
            "enabled": False,
            "kind": "once",
            "last_status": "err",
        }
    ]
