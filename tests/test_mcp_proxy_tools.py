from __future__ import annotations

from unittest.mock import Mock

from kater import mcp_server


def test_build_proxy_handler_no_args() -> None:
    proxy = Mock()
    proxy.call_tool.return_value = {"ok": True}

    handler = mcp_server._build_proxy_handler(
        "linear__list_teams",
        {"type": "object", "properties": {}},
        proxy,
    )
    result = handler()

    assert result == {"ok": True}
    proxy.call_tool.assert_called_once_with("linear__list_teams", {})


def test_build_proxy_handler_with_optional_and_required_args() -> None:
    proxy = Mock()
    proxy.call_tool.return_value = {"ok": True}

    handler = mcp_server._build_proxy_handler(
        "linear__list_issues",
        {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "teamId": {"type": "string"},
            },
            "required": ["teamId"],
        },
        proxy,
    )
    handler(limit=3, teamId="team-1")

    proxy.call_tool.assert_called_once_with(
        "linear__list_issues",
        {"limit": 3, "teamId": "team-1"},
    )


def test_make_proxy_tool_registers_schema_aware_handler() -> None:
    fake_server = Mock()
    captured: dict[str, object] = {}

    def capture(handler):
        captured["handler"] = handler
        return handler

    fake_server.tool.return_value = capture
    proxy = Mock()
    proxy.call_tool.return_value = {"content": []}

    mcp_server._make_proxy_tool(
        fake_server,
        {
            "name": "linear__list_issues",
            "description": "[linear] List issues",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        },
        proxy,
    )

    fn = captured["handler"]
    fn(limit=2)
    proxy.call_tool.assert_called_once_with("linear__list_issues", {"limit": 2})
