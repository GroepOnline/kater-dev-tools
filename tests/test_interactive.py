"""Tests for the interactive TUI loop (previously had zero coverage).

The interactive module reads commands from stdin and renders to stdout. We
exercise the command dispatch and the helper functions directly rather than
spawning a real TTY: stdin is monkeypatched to a canned sequence and stdout
is captured.
"""

from __future__ import annotations

import io

import pytest

from kater import interactive


@pytest.fixture
def patch_streams(monkeypatch):
    """Capture stdout and feed canned stdin lines to the interactive loop."""
    out = io.StringIO()
    monkeypatch.setattr(interactive.sys, "stdout", out)
    return out, monkeypatch


def _run_loop(monkeypatch, lines: list[str]):
    """Run interactive_loop with canned stdin; return captured stdout."""
    out = io.StringIO()
    monkeypatch.setattr(interactive.sys, "stdout", out)
    monkeypatch.setattr(interactive.sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
    interactive.interactive_loop(profile="core", refresh_interval=999)
    return out.getvalue()


def test_quit_exits_cleanly(monkeypatch):
    out = _run_loop(monkeypatch, ["quit"])
    assert "stopped" in out.lower()


def test_exit_alias_works(monkeypatch):
    out = _run_loop(monkeypatch, ["exit"])
    assert "stopped" in out.lower()


def test_eof_exits_cleanly(monkeypatch):
    # An empty stdin yields EOF on readline -> loop breaks.
    out = _run_loop(monkeypatch, [])
    assert "stopped" in out.lower()


def test_unknown_command_reports_error(monkeypatch):
    out = _run_loop(monkeypatch, ["bogus-command", "quit"])
    assert "unknown" in out.lower()


def test_help_renders_commands(monkeypatch):
    out = _run_loop(monkeypatch, ["help", "quit"])
    assert "toggle" in out
    assert "profile" in out


def test_status_refreshes(monkeypatch):
    out = _run_loop(monkeypatch, ["status", "quit"])
    # The render should show the KATER header.
    assert "KATER" in out


def test_invalid_profile_reports_error(monkeypatch):
    out = _run_loop(monkeypatch, ["profile not-a-real-profile", "quit"])
    assert "unknown profile" in out.lower()


def test_handle_toggle_unknown_server(capsys):
    interactive._handle_toggle("toggle", "not-a-real-server")
    captured = capsys.readouterr()
    assert "unknown server" in captured.out.lower()


def test_handle_toggle_enable_disable():
    from kater.profiles import get_source
    from kater.settings import KaterSettings, load_settings, save_settings

    save_settings(KaterSettings())
    # Find a real server name to toggle.
    src = get_source("github")
    assert src is not None

    interactive._handle_toggle("disable", "github")
    assert load_settings().is_server_enabled("github", default=True) is False

    interactive._handle_toggle("enable", "github")
    assert load_settings().is_server_enabled("github", default=True) is True

    interactive._handle_toggle("toggle", "github")
    assert load_settings().is_server_enabled("github", default=True) is False


def test_print_helpers_emit_ansi(capsys):
    interactive._print_ok("done")
    interactive._print_err("boom")
    captured = capsys.readouterr()
    assert "done" in captured.out
    assert "boom" in captured.out


def test_print_help_lists_all_commands(capsys):
    interactive._print_help()
    captured = capsys.readouterr()
    for cmd in ("toggle", "enable", "disable", "profile", "status", "clear", "quit"):
        assert cmd in captured.out


def test_render_produces_output(capsys):
    interactive._render("core")
    captured = capsys.readouterr()
    assert "KATER" in captured.out
    assert "SERVER STATUS" in captured.out
