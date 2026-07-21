"""Request pipeline, rate limiter, and stdlib HTTP server adapter.

This module owns the ``handle()`` function that every REST request flows
through, the shared rate limiter (also used by MCP and WebSocket transports),
and the ``KaterAPIHandler`` that translates raw HTTP into ``Request``/``Response``.
"""

from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

# Import routes once so every @route decorator fires and populates ROUTER.
# This import MUST happen before any call to handle(); it is safe at module
# level because routes.py only uses lazy imports for heavy dependencies.
from kater.api.models import ROUTER, Request, Response
from kater.settings import (
    RateLimiter,
    cors_allow_origin,
    load_settings,
    resolve_client_ip,
    sanitize_header_value,
)

_log = logging.getLogger(__name__)


# ── Rate limiter (module-level) ────────────────────────────────────

_rate_limiter: RateLimiter | None = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        settings = load_settings()
        _rate_limiter = RateLimiter(settings.rate_limit_per_min)
    return _rate_limiter


def check_transport_rate_limit(client_ip: str) -> bool:
    """Shared rate-limit gate for non-REST transports (MCP /sse, WebSocket).

    REST applies the limiter inside ``handle()``; MCP and WS call this so the
    actual tool surface is throttled too. No-op when rate limiting is disabled.
    """
    return _get_rate_limiter().check(client_ip)


def _reset_rate_limiter() -> None:
    # Called after settings change so a new rate_limit_per_min takes effect
    # immediately instead of being pinned to the value at first request.
    global _rate_limiter
    _rate_limiter = None


# ── Client IP resolution ───────────────────────────────────────────


def _resolve_client_ip(forwarded_for: str | None, client_address_ip: str) -> str:
    return resolve_client_ip(forwarded_for, client_address_ip)


# ── The pipeline: one function decides every request ───────────────


def handle(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response.json(200, {"ok": True})

    matched = ROUTER.match(request.method, request.path)
    if matched is None:
        return Response.json(404, {"error": f"Not found: {request.path}"})

    matched_route, params = matched
    request.params = params

    if matched_route.rate_limit and not _get_rate_limiter().check(request.client_ip):
        return Response.json(429, {"error": "Rate limit exceeded. Try again later."})

    if not matched_route.public:
        from kater.authgate import AuthContext, authenticate

        decision = authenticate(
            AuthContext(
                settings=load_settings(),
                authorization_header=request.header("authorization"),
                query_api_key=request.query1("api_key"),
                path=request.path,
            )
        )
        if not decision.allowed:
            return Response.json(401, {"error": decision.error or "Unauthorized"})

    try:
        return matched_route.handler(request)
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    except Exception:
        _log.exception("Internal error handling %s %s", request.method, request.path)
        return Response.json(500, {"error": "Internal server error"})


# ── Stdlib HTTP adapter ────────────────────────────────────────────


def _base_url(handler: BaseHTTPRequestHandler) -> str:
    # Only trust X-Forwarded-Host when the connection originates from a
    # loopback proxy (Cloudflare Tunnel / Tailscale Funnel connect from
    # 127.0.0.1).  An external client connecting directly to 0.0.0.0 can
    # forge the header and poison the OAuth issuer URL.
    peer = handler.client_address[0] if handler.client_address else ""
    host = handler.headers.get("Host", "localhost:9091")
    if peer in ("127.0.0.1", "::1", ""):
        xfh = handler.headers.get("X-Forwarded-Host")
        if xfh:
            host = xfh
    scheme = "https" if handler.headers.get("X-Forwarded-Proto") == "https" else "http"
    return f"{scheme}://{host}"


class KaterAPIHandler(BaseHTTPRequestHandler):
    server_version = "KaterAPI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _build_request(self, method: str) -> Request | None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            self._write(Response.json(400, {"error": "Invalid Content-Length header"}))
            return None
        raw = b""
        if length:
            if length > load_settings().body_size_limit:
                self._write(Response.json(400, {"error": "Request body too large"}))
                return None
            raw = self.rfile.read(length)
        return Request(
            method=method,
            path=path,
            query=parse_qs(parsed.query),
            headers={k.lower(): v for k, v in self.headers.items()},
            raw_body=raw,
            client_ip=_resolve_client_ip(
                self.headers.get("X-Forwarded-For"),
                self.client_address[0] if self.client_address else "unknown",
            ),
            base_url=_base_url(self),
        )

    def _dispatch(self, method: str) -> None:
        request = self._build_request(method)
        if request is None:
            return
        self._write(handle(request))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_HEAD(self) -> None:
        # HEAD is GET-for-routing with no body. Reuse the single pipeline so
        # auth + rate limiting cannot drift from the GET path (previously do_HEAD
        # re-implemented auth inline and skipped the rate limiter).
        request = self._build_request("HEAD")
        if request is None:
            return
        get_request = Request(
            method="GET",
            path=request.path,
            query=request.query,
            headers=request.headers,
            raw_body=request.raw_body,
            client_ip=request.client_ip,
            base_url=request.base_url,
            params=request.params,
        )
        response = handle(get_request)
        # Same headers/status, but HEAD must not carry a body.
        self._write(
            Response(
                status=response.status,
                body=b"",
                content_type=response.content_type,
                headers=response.headers,
            )
        )

    def do_OPTIONS(self) -> None:
        # Apply rate limiting to OPTIONS (CORS preflight) to prevent DoS.
        if _get_rate_limiter().check(
            _resolve_client_ip(
                self.headers.get("X-Forwarded-For", ""),
                self.client_address[0] if self.client_address else "",
            )
        ):
            self._write(Response.json(200, {"ok": True}))
        else:
            self._write(Response.json(429, {"error": "rate limit exceeded"}))

    def _write(self, response: Response) -> None:
        body = response.encoded()
        origin = self.headers.get("Origin")
        allow = cors_allow_origin(load_settings(), origin)
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(body)))
        if allow:
            self.send_header("Access-Control-Allow-Origin", sanitize_header_value(allow))
            # Vary: Origin ensures CDNs/proxies don't cache a response
            # with a permissive ACAO header and serve it to a different origin.
            if allow != "*":
                self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if self.headers.get("X-Forwarded-Proto") == "https":
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for key, value in response.headers.items():
            self.send_header(sanitize_header_value(key), sanitize_header_value(value))
        self.end_headers()
        if body:
            self.wfile.write(body)


def create_api_server(host: str = "127.0.0.1", port: int = 9091) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), KaterAPIHandler)


def serve_api(host: str = "127.0.0.1", port: int = 9091) -> None:
    server = create_api_server(host, port)
    server.serve_forever()
