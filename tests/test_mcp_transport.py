from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock

from kater.mcp.transport import combine_mcp_transports


class _FakeAsyncContext:
    def __init__(self, label: str, entered: list[str]) -> None:
        self._label = label
        self._entered = entered

    async def __aenter__(self) -> None:
        self._entered.append(self._label)

    async def __aexit__(self, *exc: object) -> None:
        return None


def test_combine_mcp_transports_enters_both_transport_lifespans() -> None:
    entered: list[str] = []

    fake_sse_app = Mock()
    fake_sse_app.routes = [Mock(path="/sse")]
    fake_sse_app.router.lifespan_context = lambda app: _FakeAsyncContext("sse", entered)

    fake_stream_app = Mock()
    fake_stream_app.routes = [Mock(path="/mcp")]
    fake_stream_app.router.lifespan_context = lambda app: _FakeAsyncContext("stream", entered)

    class FakeServer:
        def sse_app(self, **kwargs: Any) -> Mock:
            return fake_sse_app

        def streamable_http_app(self, **kwargs: Any) -> Mock:
            return fake_stream_app

    app = combine_mcp_transports(FakeServer(), security=None)
    asyncio.run(_run_lifespan(app))

    assert entered == ["sse", "stream"]


async def _run_lifespan(app: Any) -> None:
    async with app.router.lifespan_context(app):
        return


def test_combine_mcp_transports_runs_streamable_session_manager() -> None:
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("kater-test")
    app = combine_mcp_transports(server, security=None)

    async def _run() -> None:
        async with app.router.lifespan_context(app):
            assert server.session_manager is not None

    asyncio.run(_run())
