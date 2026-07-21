from __future__ import annotations

import inspect
from unittest.mock import Mock

import pytest

from kater import mcp_server
from kater.mcp_server import InvalidToolSchemaError


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


# ---------------------------------------------------------------------------
# Regression: signature shape preserved under the no-exec rewrite.
# FastMCP reads parameter metadata via inspect.signature, so the handler we
# build must expose the schema property names as keyword-only parameters.
# ---------------------------------------------------------------------------


def test_build_proxy_handler_exposes_signature_for_fastmcp() -> None:
    from typing import Any

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
        Mock(),
    )
    sig = inspect.signature(handler)
    assert list(sig.parameters) == ["limit", "teamId"]
    for param in sig.parameters.values():
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.default is None
        assert param.annotation is Any
    assert sig.return_annotation is Any


def test_build_proxy_handler_rejects_positional_args() -> None:
    proxy = Mock()
    handler = mcp_server._build_proxy_handler(
        "linear__list_issues",
        {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        proxy,
    )
    # Positional args were never accepted by the exec-based handler either:
    # it built a function with explicit keyword params and calling positionally
    # would have bound the first param. The keyword-only signature makes this
    # rejection explicit.
    with pytest.raises(TypeError):
        handler(2)  # type: ignore[misc]


def test_build_proxy_handler_drops_none_optional_values() -> None:
    proxy = Mock()
    handler = mcp_server._build_proxy_handler(
        "linear__list_issues",
        {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "teamId": {"type": "string"},
            },
        },
        proxy,
    )
    handler(teamId="team-1", limit=None)
    proxy.call_tool.assert_called_once_with("linear__list_issues", {"teamId": "team-1"})


# ---------------------------------------------------------------------------
# Adversarial payloads: every form of injection that exec() would have
# executed is now a clean rejection at schema-validation time.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prop_name",
    [
        # Import-then-call tricks that the old exec would have run.
        "__import__('os').system('rm -rf /')",
        "exec('raise SystemExit')",
        # Attribute access smuggled in via the parameter name.
        "__class__.__init__",
        "__globals__",
        "proxy.__call__",
        # Statement separators / multiple statements.
        "a; import os",
        # Bracket-and-call syntax the old exec would have parsed as a subscript.
        "os['system']",
        # Dunder-based attribute injection.
        "__builtins__",
        # Reserved closure names that would shadow the handler's bindings.
        "proxy",
        "tool_name",
        # Empty / whitespace / non-string junk.
        "",
        " ",
        "1abc",  # invalid leading char
        "has space",
    ],
)
def test_build_proxy_handler_rejects_unsafe_property_name(prop_name: str) -> None:
    with pytest.raises(InvalidToolSchemaError):
        mcp_server._build_proxy_handler(
            "linear__list_issues",
            {"type": "object", "properties": {prop_name: {"type": "string"}}},
            Mock(),
        )


@pytest.mark.parametrize(
    "tool_name",
    [
        "__import__('os').system('rm -rf /')",
        "exec('raise SystemExit')",
        "evil; rm -rf /",
        "",
        "1abc",
        "has space",
    ],
)
def test_build_proxy_handler_rejects_unsafe_tool_name(tool_name: str) -> None:
    with pytest.raises(InvalidToolSchemaError):
        mcp_server._build_proxy_handler(
            tool_name,
            {"type": "object", "properties": {}},
            Mock(),
        )


def test_build_proxy_handler_rejects_enormous_schema() -> None:
    # _MAX_TOOL_PROPERTIES + 1 entries — fail closed rather than reflect a
    # signature that an attacker could use to OOM introspection.
    too_many = {f"p{i}": {"type": "string"} for i in range(mcp_server._MAX_TOOL_PROPERTIES + 1)}
    with pytest.raises(InvalidToolSchemaError):
        mcp_server._build_proxy_handler(
            "linear__bomb",
            {"type": "object", "properties": too_many},
            Mock(),
        )


def test_build_proxy_handler_rejects_non_object_properties() -> None:
    with pytest.raises(InvalidToolSchemaError):
        mcp_server._build_proxy_handler(
            "linear__bad",
            {"type": "object", "properties": ["limit", "teamId"]},  # type: ignore[dict-item]
            Mock(),
        )


def test_build_proxy_handler_rejects_non_list_required() -> None:
    with pytest.raises(InvalidToolSchemaError):
        mcp_server._build_proxy_handler(
            "linear__bad",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
                "required": "limit",  # type: ignore[dict-item]
            },
            Mock(),
        )


def test_make_proxy_tool_skips_unsafe_schema_instead_of_registering() -> None:
    """Fail closed at registration: a malicious proxy tool is logged and skipped
    rather than crashing proxy registration entirely."""
    fake_server = Mock()
    proxy = Mock()

    mcp_server._make_proxy_tool(
        fake_server,
        {
            "name": "evil__import",
            "description": "should be skipped",
            "inputSchema": {
                "type": "object",
                "properties": {"__import__('os')": {"type": "string"}},
            },
        },
        proxy,
    )

    # No tool was registered.
    fake_server.tool.assert_not_called()
    # And the proxy was never called.
    proxy.call_tool.assert_not_called()
