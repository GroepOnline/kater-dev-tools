from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest

from kater.api import create_api_server
from kater.gateway import ApiProxyMiddleware


@pytest.fixture
def api_server():
    server = create_api_server("127.0.0.1", 9925)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield server
    server.shutdown()
    server.server_close()
    time.sleep(0.2)


async def _request(mw: ApiProxyMiddleware, path: str) -> tuple[int, bytes]:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [],
    }
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    await mw(scope, receive, send)
    status = sent[0]["status"]
    body = b"".join(
        m.get("body", b"") for m in sent if m.get("type") == "http.response.body"
    )
    return status, body


def test_api_proxy_forwards_oauth_discovery(api_server) -> None:
    async def downstream(scope, receive, send):
        raise AssertionError("should not reach MCP app")

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, body = asyncio.run(_request(mw, "/.well-known/oauth-authorization-server"))
    assert status == 200
    data = json.loads(body)
    assert "authorization_endpoint" in data


def test_api_proxy_passes_through_mcp_paths(api_server) -> None:
    called = {"v": False}

    async def downstream(scope, receive, send):
        called["v"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, body = asyncio.run(_request(mw, "/sse"))
    assert called["v"] is True
    assert status == 200
    assert body == b"ok"
