from __future__ import annotations

from kater.ansi import Table, banner, bar, colorize, dim, error, info, kv_grid, success, warning


def test_colorize():
    result = colorize("hello", "\033[31m")
    assert "hello" in result


def test_success():
    result = success("ok")
    assert "ok" in result


def test_error():
    result = error("fail")
    assert "fail" in result


def test_warning():
    result = warning("warn")
    assert "warn" in result


def test_info():
    result = info("note")
    assert "note" in result


def test_dim():
    result = dim("quiet")
    assert "quiet" in result


def test_table_render():
    table = Table(["Name", "Status"], "Test Table")
    table.add_row("github", "ok")
    table.add_row("sentry", "fail")
    result = table.render()
    assert "Name" in result
    assert "github" in result
    assert "sentry" in result
    assert "Test Table" in result
    assert "\u2502" in result  # Unicode box-drawing vertical


def test_table_no_title():
    table = Table(["A", "B"])
    table.add_row("1", "2")
    result = table.render()
    assert "A" in result
    assert "1" in result


def test_table_empty():
    table = Table(["Col1", "Col2"], "Empty")
    result = table.render()
    assert "Col1" in result


def test_banner():
    result = banner("Kater v1.0", "Subtitle")
    assert "Kater v1.0" in result
    assert "Subtitle" in result


def test_banner_no_subtitle():
    result = banner("Just Title")
    assert "Just Title" in result


def test_kv_grid():
    result = kv_grid([("Key1", "val1"), ("Key2", "val2")])
    assert "Key1" in result
    assert "val1" in result
    assert "Key2" in result


def test_bar():
    result = bar(6, 10)
    assert "%" in result


def test_bar_full():
    result = bar(10, 10)
    assert "100%" in result


def test_bar_zero():
    result = bar(0, 10)
    assert "0%" in result


def test_bar_zero_total():
    result = bar(5, 0)
    assert "%" in result
