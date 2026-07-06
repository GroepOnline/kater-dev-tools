"""Proxy REST API routes from the MCP port to the API server.

ChatGPT Remote MCP expects ``/sse`` and OAuth bootstrap on the same origin.
The web dashboard expects ``/dashboard``, ``/api/*``, and (via tunnel) ``/ws``.
Kater runs MCP (9090), REST (9091), and WebSocket (9092) separately; this
middleware forwards non-MCP HTTP to the API so a single-host Cloudflare Tunnel
can point at ``localhost:9090``.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib import error, request

from kater.authgate import should_proxy_to_api
from kater.settings import load_settings


class _NoRedirect(request.HTTPRedirectHandler):
    """Do not follow redirects — OAuth /authorize must reach the browser as 302."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# OAuth approve flows return 302 to the client redirect_uri; following them here
# would fetch the dashboard server-side and strip ?code= from the browser URL.
_PROXY_OPENER = request.build_opener(_NoRedirect())


def _build_proxy_url(scope: dict, api_port: int) -> str:
    path = scope.get("path") or "/"
    query = scope.get("query_string", b"").decode("latin-1")
    url = f"http://127.0.0.1:{api_port}{path}"
    if query:
        url = f"{url}?{query}"
    return url


def _prepare_proxy_headers(scope: dict) -> dict[str, str]:
    headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
    host = headers.get("host")
    if host:
        headers["X-Forwarded-Host"] = host
        if headers.get("x-forwarded-proto"):
            headers["X-Forwarded-Proto"] = headers["x-forwarded-proto"]
        else:
            # A tunnel terminates TLS, so the upstream socket is plain HTTP.
            # Detect https by a non-loopback public host (configurable). This
            # avoids baking any single org domain into shared source.
            https_hosts = os.environ.get("KATER_HTTPS_HOSTS", "")
            is_https_tunnel = host not in ("localhost:9091", "127.0.0.1:9091") and (
                not host.startswith(("127.", "localhost", "::1"))
                or any(h and h in host for h in https_hosts.split(","))
            )
            headers["X-Forwarded-Proto"] = "https" if is_https_tunnel else "http"
    return headers


async def _read_proxy_body(scope: dict, receive: Any) -> bytes:
    if scope.get("method") not in {"POST", "PUT", "PATCH"}:
        return b""

    from kater.settings import load_settings

    body_limit = load_settings().body_size_limit
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        chunk = message.get("body", b"")
        total += len(chunk)
        if total > body_limit:
            raise ValueError("Request body too large")
        chunks.append(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _format_proxy_response_headers(
    resp_headers: list[tuple[str, str]], body_len: int
) -> list[tuple[bytes, bytes]]:
    out_headers: list[tuple[bytes, bytes]] = []
    for key, value in resp_headers:
        lowered = key.lower()
        if lowered in {"transfer-encoding", "connection", "content-length"}:
            continue
        out_headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    out_headers.append((b"content-length", str(body_len).encode("ascii")))
    return out_headers


async def _proxy_to_api(scope: dict, receive: Any, send: Any, api_port: int) -> None:
    url = _build_proxy_url(scope, api_port)
    headers = _prepare_proxy_headers(scope)
    body = await _read_proxy_body(scope, receive)

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
    out_headers = _format_proxy_response_headers(resp_headers, len(resp_body))

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
