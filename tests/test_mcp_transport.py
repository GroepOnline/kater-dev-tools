from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock

from kater.mcp.transport import StreamableHttpOnSseMiddleware, combine_mcp_transports


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


def test_streamable_http_on_sse_rewrites_post_and_delete_only() -> None:
    seen: list[str] = []

    async def inner(scope: dict[str, Any], receive: Any, send: Any) -> None:
        seen.append(f"{scope.get('method')} {scope.get('path')}")
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = StreamableHttpOnSseMiddleware(inner)

    async def run(method: str, path: str, headers: list[tuple[bytes, bytes]] | None = None) -> None:
        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers or [],
            "raw_path": path.encode(),
        }

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_msg: dict[str, Any]) -> None:
            return None

        await mw(scope, receive, send)

    asyncio.run(run("POST", "/sse"))
    asyncio.run(run("GET", "/sse"))
    asyncio.run(run("GET", "/sse", [(b"mcp-session-id", b"sess-1")]))
    asyncio.run(run("DELETE", "/sse"))
    asyncio.run(run("POST", "/mcp"))
    assert seen == [
        "POST /mcp",
        "GET /sse",
        "GET /mcp",
        "DELETE /mcp",
        "POST /mcp",
    ]


def test_post_sse_initialize_is_not_method_not_allowed() -> None:
    """Cursor POSTs Streamable HTTP to /sse; that must not 405."""
    from mcp.server.mcpserver import MCPServer
    from starlette.testclient import TestClient

    server = MCPServer("kater-test")

    @server.tool(name="kater_profiles")
    def profiles() -> dict[str, Any]:
        return {"profiles": ["ops"]}

    app = combine_mcp_transports(server, security=None)
    with TestClient(app, base_url="http://127.0.0.1:9090") as client:
        resp = client.post(
            "/sse",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code != 405
    assert resp.status_code == 200
    assert b"kater-test" in resp.content or b"protocolVersion" in resp.content
