from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kater.proxy.aggregator import Aggregator
from kater.proxy.base import MockBackend
from kater.proxy.models import BackendStatus, ProxiedTool
from kater.proxy.router import Router

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


def test_proxied_tool_prefix():
    tool = ProxiedTool(
        name="create_issue",
        description="Create issue",
        backend="github",
        original_name="create_issue",
    )
    assert tool.prefixed_name == "github__create_issue"


def test_backend_status_to_dict():
    status = BackendStatus(name="github", healthy=True, tool_count=5)
    d = status.to_dict()
    assert d["name"] == "github"
    assert d["healthy"] is True
    assert d["tool_count"] == 5


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


def test_router_route_by_prefix():
    agg = Aggregator()
    agg.add_backend_tools("github", [
        ProxiedTool(name="search", description="S", backend="github", original_name="search"),
    ])
    router = Router(agg)
    assert router.route("github__search") == ("github", "search")
    assert router.route("unknown__tool") == ("unknown", "tool")
    assert router.route("noprefix") is None


def test_router_call_with_mock():
    agg = Aggregator()
    backend = MockBackend(
        tools=[{"name": "ping"}],
        responses={"ping": {"result": "pong"}},
    )
    backend.start()
    agg.add_backend_tools("mock", backend.list_tools())
    router = Router(agg)
    result = router.call("mock__ping", {}, {"mock": backend})
    assert result.get("result") == "pong"


def test_router_call_unknown():
    agg = Aggregator()
    router = Router(agg)
    result = router.call("unknown__tool", {}, {})
    assert "error" in result


def test_router_call_backend_down():
    agg = Aggregator()
    backend = MockBackend(tools=[{"name": "ping"}])
    backend.start()
    agg.add_backend_tools("mock", backend.list_tools())
    router = Router(agg)
    backend.stop()
    result = router.call("mock__ping", {}, {"mock": backend})
    assert "error" in result


def test_proxy_manager_mock_profile():
    from kater.proxy.manager import ProxyManager

    manager = ProxyManager()
    assert not manager.started
    assert manager.tool_count() == 0
    manager.stop()
    assert not manager.started
