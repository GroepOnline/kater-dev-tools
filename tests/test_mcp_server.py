from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from kater import mcp_server


def test_mcp_missing_package_message() -> None:
    with (
        patch("kater.mcp_server.import_module", side_effect=ModuleNotFoundError("mcp")),
        pytest.raises(mcp_server.McpUnavailableError) as exc_info,
    ):
        mcp_server.create_server()

    assert "uv sync" in str(exc_info.value)


def test_mcp_registers_core_tools() -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(FastMCP=Mock(return_value=fake_server))

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        server = mcp_server.create_server(profile="core")

    assert server is fake_server
    registered = [call.kwargs["name"] for call in fake_server.tool.call_args_list]
    assert "kater_profiles" in registered
    assert "kater_doctor" in registered


def test_create_server_does_not_start_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = Mock()
    fake_server.tool.return_value = lambda handler: handler
    fake_module = Mock(FastMCP=Mock(return_value=fake_server))
    proxy_start = Mock()
    monkeypatch.setattr(
        "kater.proxy.get_proxy",
        lambda: Mock(start=proxy_start, list_tools=Mock(return_value=[])),
    )

    with patch("kater.mcp_server.import_module", return_value=fake_module):
        mcp_server.create_server(profile="core")

    proxy_start.assert_not_called()
