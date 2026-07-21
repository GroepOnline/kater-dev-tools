from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import urllib.parse
from urllib.parse import urlencode

import pytest

from kater.api import create_api_server
from kater.gateway import ApiProxyMiddleware
from kater.oauth import register_client, reset_state


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


async def _request(
    mw: ApiProxyMiddleware,
    path: str,
    *,
    query_string: bytes = b"",
) -> tuple[int, bytes, list[tuple[bytes, bytes]]]:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": query_string,
        "headers": [],
    }
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    await mw(scope, receive, send)
    status = sent[0]["status"]
    headers = sent[0].get("headers", [])
    body = b"".join(m.get("body", b"") for m in sent if m.get("type") == "http.response.body")
    return status, body, headers


def test_api_proxy_forwards_oauth_discovery(api_server) -> None:
    async def downstream(scope, receive, send):
        raise AssertionError("should not reach MCP app")

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, body, _ = asyncio.run(_request(mw, "/.well-known/oauth-authorization-server"))
    assert status == 200
    data = json.loads(body)
    assert "authorization_endpoint" in data


def test_api_proxy_forwards_dashboard(api_server) -> None:
    async def downstream(scope, receive, send):
        raise AssertionError("should not reach MCP app")

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, body, _ = asyncio.run(_request(mw, "/dashboard"))
    assert status == 200
    assert b"KATER" in body or b"kater" in body.lower()


def test_api_proxy_forwards_api_routes(api_server) -> None:
    async def downstream(scope, receive, send):
        raise AssertionError("should not reach MCP app")

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, _, _ = asyncio.run(_request(mw, "/api/status"))
    assert status == 200


def test_api_proxy_passes_through_oauth_redirect(api_server) -> None:
    reset_state()
    redirect_uri = "https://kater.example/dashboard"
    client = register_client(
        client_name="test",
        redirect_uris=[redirect_uri],
    )
    consent_query = urlencode(
        {
            "response_type": "code",
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": "abc123",
            "code_challenge_method": "S256",
        }
    ).encode()

    async def downstream(scope, receive, send):
        raise AssertionError("should not reach MCP app")

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, body, headers = asyncio.run(_request(mw, "/authorize", query_string=consent_query))
    assert status == 200
    cookie = next(
        (v.decode().split(";", 1)[0] for k, v in headers if k.lower() == b"set-cookie"),
        "",
    )
    assert cookie.startswith("kater_oauth_consent=")
    html = body.decode()
    allow_href = re.search(r'href="([^"]+approve=1[^"]+)"', html)
    assert allow_href is not None
    approve_url = allow_href.group(1).replace("&amp;", "&")
    parsed = urllib.parse.urlparse(approve_url)

    async def _request_with_cookie(
        mw: ApiProxyMiddleware,
        path: str,
        *,
        query_string: bytes,
        cookie: str,
    ) -> tuple[int, bytes, list[tuple[bytes, bytes]]]:
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query_string,
            "headers": [(b"cookie", cookie.encode())],
        }
        sent: list = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(msg):
            sent.append(msg)

        await mw(scope, receive, send)
        response_status = sent[0]["status"]
        response_headers = sent[0].get("headers", [])
        response_body = b"".join(
            m.get("body", b"") for m in sent if m.get("type") == "http.response.body"
        )
        return response_status, response_body, response_headers

    status, body, headers = asyncio.run(
        _request_with_cookie(
            mw,
            parsed.path,
            query_string=parsed.query.encode(),
            cookie=cookie,
        )
    )
    assert status == 302
    assert body == b""
    location = next(
        (v.decode() for k, v in headers if k.lower() == b"location"),
        "",
    )
    assert location.startswith(f"{redirect_uri}?code=")


def test_api_proxy_passes_through_mcp_paths(api_server) -> None:
    called = {"v": False}

    async def downstream(scope, receive, send):
        called["v"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = ApiProxyMiddleware(downstream, api_port=9925)
    status, body, _ = asyncio.run(_request(mw, "/sse"))
    assert called["v"] is True
    assert status == 200
    assert body == b"ok"
