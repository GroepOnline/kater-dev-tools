import json
import os
from pathlib import Path

from kater.envfile import (
    ensure_cursor_mcp,
    load_project_env,
    parse_env_file,
    resolve_use_proxy,
)
from kater.init import init_project


def test_parse_env_file_supports_export_and_quotes(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            [
                "# comment",
                "FOO=bar",
                'export BAR="baz qux"',
                "EMPTY=",
                "invalid line",
                "",
            ]
        ),
        encoding="utf-8",
    )
    assert parse_env_file(path) == {
        "FOO": "bar",
        "BAR": "baz qux",
        "EMPTY": "",
    }


def test_load_project_env_prefers_kater_over_root_and_keeps_process(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    (tmp_path / ".kater" / ".env").write_text(
        "LINEAR_API_KEY=from-kater\nSHARED=kater\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "LINEAR_API_KEY=from-root\nSHARED=root\nROOT_ONLY=1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SHARED", "process")
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.delenv("ROOT_ONLY", raising=False)

    loaded = load_project_env(tmp_path)
    assert any(p.endswith(".kater/.env") or p.endswith(".kater\\.env") for p in loaded)
    assert os.environ["LINEAR_API_KEY"] == "from-kater"
    assert os.environ["SHARED"] == "process"
    assert os.environ["ROOT_ONLY"] == "1"


def test_resolve_use_proxy_explicit_and_auto(monkeypatch) -> None:
    monkeypatch.setenv("KATER_PROXY", "0")
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    assert resolve_use_proxy(profile="ops") is False

    monkeypatch.setenv("KATER_PROXY", "1")
    assert resolve_use_proxy(profile="ops") is True

    monkeypatch.delenv("KATER_PROXY")
    assert resolve_use_proxy(profile="ops") is True

    monkeypatch.delenv("LINEAR_API_KEY")
    assert resolve_use_proxy(profile="ops") is False
    assert resolve_use_proxy(profile="core") is False


def test_init_writes_cursor_mcp_and_env_notes(tmp_path: Path) -> None:
    result = init_project(tmp_path, profile="ops")
    env_text = (tmp_path / ".kater" / ".env").read_text(encoding="utf-8")
    assert "KATER_PROFILE=ops" in env_text
    assert "loaded automatically" in env_text
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    assert cursor_path.is_file()
    payload = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["kater"] == {
        "type": "sse",
        "url": "http://127.0.0.1:9090/sse",
    }
    assert any(str(cursor_path) in str(p) for p in result["created"])


def test_ensure_cursor_mcp_merges_existing(tmp_path: Path) -> None:
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()
    existing = {
        "mcpServers": {
            "other": {"command": "npx", "args": ["x"]},
            "kater": {"type": "sse", "url": "http://old"},
        }
    }
    (cursor_dir / "mcp.json").write_text(json.dumps(existing), encoding="utf-8")
    result = ensure_cursor_mcp(tmp_path)
    assert result["updated"] is True
    payload = json.loads((cursor_dir / "mcp.json").read_text(encoding="utf-8"))
    assert payload["mcpServers"]["other"]["command"] == "npx"
    assert payload["mcpServers"]["kater"]["url"] == "http://127.0.0.1:9090/sse"
