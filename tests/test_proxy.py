from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from kater.proxy.aggregator import Aggregator
from kater.proxy.base import BaseBackend, MockBackend
from kater.proxy.manager import ProxyManager
from kater.proxy.models import BackendStatus, ProxiedTool

KATER_DIR = Path.cwd() / ".kater"


@pytest.fixture(autouse=True)
def clean_storage():
    from kater.storage import reset_db_cache

    reset_db_cache()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)
    yield
    reset_db_cache()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)


class RecordingBackend(BaseBackend):
    name = "recording"

    def __init__(self, rpc_responses: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        self.rpc_calls: list[tuple[str, dict[str, Any] | None]] = []
        self._rpc_responses = rpc_responses or {}
        self.connected = False

    def _connect(self) -> None:
        self.connected = True

    def _disconnect(self) -> None:
        self.connected = False

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.rpc_calls.append((method, params))
        if method in self._rpc_responses:
            return self._rpc_responses[method]
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}}
        if method == "notifications/initialized":
            return {}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search code",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                },
            }
        return {"error": f"unexpected rpc: {method}"}


def test_recording_backend_start_runs_mcp_session():
    backend = RecordingBackend()
    backend.start()

    assert backend.connected is True
    assert backend.is_healthy()
    assert [method for method, _ in backend.rpc_calls] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]
    init_params = backend.rpc_calls[0][1]
    assert init_params is not None
    assert init_params["protocolVersion"] == "2024-11-05"
    assert init_params["clientInfo"]["name"] == "kater-proxy"

    tools = backend.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "search"
    assert tools[0].backend == "recording"
    assert tools[0].input_schema == {"type": "object"}


def test_recording_backend_call_tool_unwraps_result():
    backend = RecordingBackend(
        rpc_responses={
            "tools/call": {
                "jsonrpc": "2.0",
                "id": 3,
                "result": {"content": [{"type": "text", "text": "ok"}]},
            }
        }
    )
    backend.start()

    result = backend.call_tool("search", {"query": "test"})
    assert result == {"content": [{"type": "text", "text": "ok"}]}
    assert backend.rpc_calls[-1] == (
        "tools/call",
        {"name": "search", "arguments": {"query": "test"}},
    )


def test_recording_backend_call_tool_passes_through_error():
    backend = RecordingBackend(
        rpc_responses={"tools/call": {"error": "tool failed"}}
    )
    backend.start()

    result = backend.call_tool("search", {})
    assert result == {"error": "tool failed"}


def test_recording_backend_start_failure():
    class FailingBackend(RecordingBackend):
        def _connect(self) -> None:
            raise OSError("connection refused")

    backend = FailingBackend()
    backend.start()

    assert not backend.is_healthy()
    assert backend.status.error == "connection refused"
    assert backend.rpc_calls == []


def test_proxied_tool_prefix():
    tool = ProxiedTool(
        name="create_issue",
        description="Create issue",
        backend="github",
        original_name="create_issue",
    )
    assert tool.prefixed_name == "github__create_issue"


def test_backend_status_to_dict():
    status = BackendStatus(name="github", healthy=True, tool_count=5, breaker_state="closed")
    d = status.to_dict()
    assert d["name"] == "github"
    assert d["healthy"] is True
    assert d["tool_count"] == 5
    assert d["breaker_state"] == "closed"


def test_stdio_backend_env_whitelist(monkeypatch):
    from kater.proxy.stdio_backend import StdioBackend

    monkeypatch.setenv("SECRET_TOKEN_XYZ", "super-secret")
    monkeypatch.setenv("PATH", "/usr/bin")

    backend = StdioBackend(name="test", command="echo", env={"CUSTOM": "value"})
    assert "SECRET_TOKEN_XYZ" not in backend._env
    assert backend._env.get("PATH") == "/usr/bin"
    assert backend._env["CUSTOM"] == "value"

    override = StdioBackend(name="test2", command="echo", env={"PATH": "/custom/path"})
    assert override._env["PATH"] == "/custom/path"


def test_mock_backend_start_and_list():
    backend = MockBackend(
        tools=[
            {"name": "search", "description": "Search code"},
            {"name": "create_pr", "description": "Create PR"},
        ]
    )
    backend.start()
    tools = backend.list_tools()
    assert len(tools) == 2
    assert tools[0].name == "search"
    assert tools[0].backend == "mock"
    assert backend.is_healthy()


def test_mock_backend_call():
    backend = MockBackend(
        tools=[{"name": "ping"}],
        responses={"ping": {"content": [{"type": "text", "text": "pong"}]}},
    )
    backend.start()
    result = backend.call_tool("ping", {})
    assert "pong" in result["content"][0]["text"]


def test_mock_backend_stop():
    backend = MockBackend(tools=[])
    backend.start()
    assert backend.is_healthy()
    backend.stop()
    assert not backend.is_healthy()


def test_aggregator_add_and_list():
    agg = Aggregator()
    tools = [
        ProxiedTool(name="search", description="Search", backend="github", original_name="search"),
        ProxiedTool(name="create", description="Create", backend="github", original_name="create"),
    ]
    agg.add_backend_tools("github", tools)
    assert agg.count() == 2
    names = agg.tool_names()
    assert "github__search" in names
    assert "github__create" in names


def test_aggregator_remove_backend():
    agg = Aggregator()
    gh_tools = [
        ProxiedTool(name="search", description="S", backend="github", original_name="search"),
    ]
    sentry_tools = [
        ProxiedTool(name="errors", description="E", backend="sentry", original_name="errors"),
    ]
    agg.add_backend_tools("github", gh_tools)
    agg.add_backend_tools("sentry", sentry_tools)
    assert agg.count() == 2
    agg.remove_backend("github")
    assert agg.count() == 1
    assert "sentry__errors" in agg.tool_names()


def test_aggregator_for_mcp():
    agg = Aggregator()
    agg.add_backend_tools("github", [
        ProxiedTool(
            name="search", description="Search code",
            backend="github", original_name="search",
            input_schema={"type": "object", "properties": {}},
        ),
    ])
    mcp_tools = agg.for_mcp()
    assert len(mcp_tools) == 1
    assert mcp_tools[0]["name"] == "github__search"
    assert "[github]" in mcp_tools[0]["description"]
    assert "inputSchema" in mcp_tools[0]


def test_proxy_manager_call_tool_with_mock():
    backend = MockBackend(
        tools=[{"name": "ping"}],
        responses={"ping": {"result": "pong"}},
    )
    manager = ProxyManager()
    manager.register_backend("mock", backend)

    result = manager.call_tool("mock__ping", {})
    assert result.get("result") == "pong"


def test_proxy_manager_call_tool_unknown_backend():
    manager = ProxyManager()
    result = manager.call_tool("unknown__tool", {})
    assert "error" in result


def test_proxy_manager_call_tool_backend_down():
    backend = MockBackend(tools=[{"name": "ping"}])
    manager = ProxyManager()
    manager.register_backend("mock", backend)
    backend.stop()

    result = manager.call_tool("mock__ping", {})
    assert "error" in result


def test_proxy_manager_call_tool_unknown_tool():
    backend = MockBackend(tools=[{"name": "ping"}])
    manager = ProxyManager()
    manager.register_backend("mock", backend)

    result = manager.call_tool("noprefix", {})
    assert result == {"error": "Unknown tool: noprefix"}


def test_proxy_manager_register_backend_lists_tools():
    backend = MockBackend(
        tools=[
            {"name": "search", "description": "Search code"},
            {"name": "create_pr", "description": "Create PR"},
        ],
    )
    manager = ProxyManager()
    manager.register_backend("mock", backend)

    tools = manager.list_tools()
    assert len(tools) == 2
    assert tools[0]["name"] == "mock__search"
    assert tools[1]["name"] == "mock__create_pr"


def test_proxy_manager_mock_profile():
    manager = ProxyManager()
    assert not manager.started
    assert manager.tool_count() == 0
    manager.stop()
    assert not manager.started
