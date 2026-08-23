from __future__ import annotations

from unittest.mock import patch

import pytest

from kater.connectors import mcp_lifecycle
from kater.connectors.errors import ConnectorUnavailableError
from kater.connectors.models import (
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
)
from kater.proxy.base import MockBackend
from kater.registry import build_native_tools


def _mcp_record(**overrides) -> ConnectorRecord:
    base = ConnectorRecord(
        id="testmcp",
        display_name="Test MCP",
        type=ConnectorType.MCP,
        version="1.0.0",
        transport=ConnectorTransport(kind="stdio", command="echo", args=("mcp",)),
        status=ConnectorStatus.REGISTERED,
    )
    data = base.as_dict()
    data.update(overrides)
    return ConnectorRecord.from_mapping(data)


def test_mcp_discovery_success_with_fake_backend():
    tools = [{"name": "search_issues", "description": "Search issues"}]
    backend = MockBackend(tools=tools)
    record = _mcp_record()

    with patch.object(mcp_lifecycle, "_create_backend", return_value=backend):
        caps = mcp_lifecycle.discover(record)

    assert len(caps) == 1
    assert caps[0].id == "testmcp.search_issues"
    assert caps[0].discovered is True


def test_mcp_discovery_failure_raises_unavailable():
    backend = MockBackend()
    backend.start = lambda: None  # type: ignore[method-assign]
    backend.is_healthy = lambda: False  # type: ignore[method-assign]
    backend.status.error = "connect refused"
    record = _mcp_record()

    with patch.object(mcp_lifecycle, "_create_backend", return_value=backend):
        with pytest.raises(ConnectorUnavailableError):
            mcp_lifecycle.discover(record)


def test_invoke_does_not_add_native_tools(monkeypatch):
    monkeypatch.delenv("KATER_EXTENSIONS_MODULE", raising=False)
    before = [tool.name for tool in build_native_tools()]
    record = _mcp_record(
        capabilities=[
            ConnectorCapability(id="testmcp.echo", description="echo", discovered=True).as_dict()
        ]
    )
    backend = MockBackend(
        tools=[{"name": "echo", "description": "echo"}],
        responses={"echo": {"content": [{"type": "text", "text": "ok"}]}},
    )

    with patch.object(mcp_lifecycle, "_create_backend", return_value=backend):
        result = mcp_lifecycle.invoke(
            record,
            "testmcp.echo",
            {"message": "hi", "_kater_route": "x"},
        )

    after = [tool.name for tool in build_native_tools()]
    assert before == after
    assert len(before) == 17
    assert "kater_profiles" in before
    assert "kater_github" not in before
    assert result["content"][0]["text"] == "ok"
