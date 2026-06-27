"""Proxy REST API routes from the MCP port to the API server.

ChatGPT Remote MCP expects ``/sse`` and OAuth bootstrap on the same origin.
The web dashboard expects ``/dashboard``, ``/api/*``, and (via tunnel) ``/ws``.
Kater runs MCP (9090), REST (9091), and WebSocket (9092) separately; this
middleware forwards non-MCP HTTP to the API so a single-host Cloudflare Tunnel
can point at ``localhost:9090``.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib import error, request

from kater.authgate import should_proxy_to_api
from kater.settings import load_settings


class _NoRedirect(request.HTTPRedirectHandler):
    """Do not follow redirects — OAuth /authorize must reach the browser as 302."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


# OAuth approve flows return 302 to the client redirect_uri; following them here
# would fetch the dashboard server-side and strip ?code= from the browser URL.
_PROXY_OPENER = request.build_opener(_NoRedirect())


async def _proxy_to_api(scope: dict, receive: Any, send: Any, api_port: int) -> None:
    path = scope.get("path") or "/"
    query = scope.get("query_string", b"").decode("latin-1")
    url = f"http://127.0.0.1:{api_port}{path}"
    if query:
        url = f"{url}?{query}"

    headers = {
        k.decode("latin-1"): v.decode("latin-1")
        for k, v in scope.get("headers", [])
    }
    host = headers.get("host")
    if host:
        headers["X-Forwarded-Host"] = host
        if headers.get("x-forwarded-proto"):
            headers["X-Forwarded-Proto"] = headers["x-forwarded-proto"]
        elif host.endswith(".chefgroep.online") or ".online" in host:
            headers["X-Forwarded-Proto"] = "https"
        else:
            headers["X-Forwarded-Proto"] = "http"

    body = b""
    if scope.get("method") in {"POST", "PUT", "PATCH"}:
        chunks: list[bytes] = []
        while True:
            message = await receive()
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

    def _do_request() -> tuple[int, list[tuple[str, str]], bytes]:
        req = request.Request(
            url,
            data=body or None,
            method=scope.get("method", "GET"),
            headers=headers,
        )
        try:
            with _PROXY_OPENER.open(req, timeout=30) as resp:
                resp_headers = list(resp.headers.items())
                return resp.status, resp_headers, resp.read()
        except error.HTTPError as exc:
            return exc.code, list(exc.headers.items()), exc.read()

    status, resp_headers, resp_body = await asyncio.to_thread(_do_request)

    out_headers: list[tuple[bytes, bytes]] = []
    for key, value in resp_headers:
        lowered = key.lower()
        if lowered in {"transfer-encoding", "connection", "content-length"}:
            continue
        out_headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    out_headers.append((b"content-length", str(len(resp_body)).encode("ascii")))

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": out_headers,
        }
    )
    await send({"type": "http.response.body", "body": resp_body})


class ApiProxyMiddleware:
    """Forward dashboard and REST paths from the MCP listener to the API port."""

    def __init__(self, app: Any, *, api_port: int | None = None) -> None:
        self._app = app
        self._api_port = api_port

    def _resolve_api_port(self) -> int:
        if self._api_port is not None:
            return self._api_port
        return load_settings().api_port

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path") or "/"
        if should_proxy_to_api(path):
            await _proxy_to_api(scope, receive, send, self._resolve_api_port())
            return

        await self._app(scope, receive, send)
