"""Kater REST API package.

This package splits the original ``api.py`` into focused modules:

- ``models`` — Request, Response, Route, RouteTable, route decorator
- ``routes`` — all @route-decorated endpoint handlers
- ``server`` — handle() pipeline, rate limiter, KaterAPIHandler, create_api_server

All public symbols are re-exported here so existing imports like
``from kater.api import create_api_server`` continue to work unchanged.
"""

from __future__ import annotations

# Models — the data seam between stdlib HTTP and app logic.
from kater.api.models import (
    ROUTER,
    Request,
    Response,
    Route,
    RouteTable,
    route,
)

# Routes import triggers @route registration into ROUTER as a side-effect.
# The symbols themselves are private (prefixed with _); _visible_source is
# re-exported because tests import it directly.
from kater.api.routes import _visible_source

# Server — pipeline, rate limiter, HTTP handler, factory functions.
from kater.api.server import (
    KaterAPIHandler,
    _base_url,
    _get_rate_limiter,
    _reset_rate_limiter,
    _resolve_client_ip,
    check_transport_rate_limit,
    create_api_server,
    handle,
    serve_api,
)

__all__ = [
    "ROUTER",
    "KaterAPIHandler",
    "Request",
    "Response",
    "Route",
    "RouteTable",
    "_base_url",
    "_get_rate_limiter",
    "_reset_rate_limiter",
    "_resolve_client_ip",
    "_visible_source",
    "check_transport_rate_limit",
    "create_api_server",
    "handle",
    "route",
    "serve_api",
]
