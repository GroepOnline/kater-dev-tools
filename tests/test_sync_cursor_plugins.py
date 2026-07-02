from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_cursor_plugins import SETTINGS_PATH, load_settings


def test_settings_file_exists() -> None:
    assert SETTINGS_PATH.is_file()


def test_settings_plugins_disabled_by_default() -> None:
    settings = load_settings()
    enabled = settings.get("enabledPlugins", {})
    assert enabled, "expected enabledPlugins map in SSOT"
    assert all(value is False for value in enabled.values()), (
        "external plugins must be opt-in; set enabledPlugins values to false"
    )


def test_settings_json_valid() -> None:
    json.loads(Path(SETTINGS_PATH).read_text(encoding="utf-8"))
