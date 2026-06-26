from __future__ import annotations

import json
from pathlib import Path

from kater.autofix import apply_fix_actions, render_cursor_snippet, render_env_example
from kater.doctor import FixAction


def test_render_cursor_snippet_default() -> None:
    snippet = render_cursor_snippet()
    servers = snippet["mcpServers"]
    assert "kater" in servers
    assert servers["kater"]["type"] == "sse"
    assert servers["kater"]["url"] == "http://127.0.0.1:9090/sse"


def test_render_cursor_snippet_custom_profile() -> None:
    snippet = render_cursor_snippet(profile="ops")
    assert snippet["mcpServers"]["kater"]["env"]["KATER_PROFILE"] == "ops"


def test_render_env_example_core() -> None:
    content = render_env_example({"core"})
    assert "KATER_PROFILE=core" in content


def test_render_env_example_research() -> None:
    content = render_env_example({"research"})
    assert "EXA_API_KEY" in content
    assert "FIRECRAWL_API_KEY" in content
    assert "HF_TOKEN" in content


def test_apply_render_cursor_snippet(tmp_path: Path) -> None:
    actions = [
        FixAction(
            action="render_cursor_snippet",
            target=".cursor/mcp.kater.json",
            description="Test snippet",
        )
    ]
    result = apply_fix_actions(actions, output_dir=tmp_path, profile="ops")
    target_file = tmp_path / ".cursor" / "mcp.kater.json"
    assert target_file.exists()
    assert len(result["applied"]) == 1
    snippet = json.loads(target_file.read_text(encoding="utf-8"))
    assert snippet["mcpServers"]["kater"]["env"]["KATER_PROFILE"] == "ops"


def test_apply_render_env_example(tmp_path: Path) -> None:
    actions = [
        FixAction(
            action="render_env_example",
            target=".env.kater.example",
            description="Test env example",
        )
    ]
    result = apply_fix_actions(actions, output_dir=tmp_path, profile="research")
    target_file = tmp_path / ".env.kater.example"
    assert target_file.exists()
    assert len(result["applied"]) == 1
    content = target_file.read_text(encoding="utf-8")
    assert "EXA_API_KEY" in content


def test_apply_skips_unknown_action(tmp_path: Path) -> None:
    actions = [
        FixAction(
            action="unknown_action",
            target="some/file",
            description="Should be skipped",
        )
    ]
    result = apply_fix_actions(actions, output_dir=tmp_path)
    assert len(result["skipped"]) == 1


def test_apply_is_idempotent(tmp_path: Path) -> None:
    actions = [
        FixAction(
            action="render_cursor_snippet",
            target=".cursor/mcp.kater.json",
            description="Test snippet",
        )
    ]
    result1 = apply_fix_actions(actions, output_dir=tmp_path)
    result2 = apply_fix_actions(actions, output_dir=tmp_path)
    assert len(result1["applied"]) == 1
    assert len(result2["applied"]) == 1
    target = tmp_path / ".cursor" / "mcp.kater.json"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == target.read_text(encoding="utf-8")
