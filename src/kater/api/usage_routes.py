"""HTTP routes for the usage / cost events ledger.

Importing this module registers endpoints into ``models.ROUTER`` via
``@route``. Kept separate from fabric/computer handlers so parallel
agents can own those surfaces without merge fights.
"""

from __future__ import annotations

from typing import Any

from kater.api.models import Request, Response, route
from kater.control_plane import usage as usage_ledger

# OpenAPI path fragments merged by ``openapi_spec._build_paths``.
USAGE_OPENAPI_PATHS: dict[str, Any] = {
    "/api/usage": {
        "get": {
            "summary": "List usage events",
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 100, "minimum": 1},
                    "description": "Max events to return (newest first).",
                },
                {
                    "name": "capability",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Filter to a single capability id.",
                },
            ],
            "responses": {
                "200": {
                    "description": "Usage event page.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "400": {
                    "description": "Invalid query",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        }
    },
    "/api/usage/summary": {
        "get": {
            "summary": "Usage aggregates by capability",
            "parameters": [
                {
                    "name": "capability",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Optional filter to a single capability id.",
                },
            ],
            "responses": {
                "200": {
                    "description": "Per-capability usage summary.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
            },
        }
    },
}


def _parse_limit(req: Request, default: int = 100, maximum: int = 1000) -> int:
    raw = req.query1("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid limit: {raw!r}") from None
    if value < 1:
        value = 1
    return min(value, maximum)


@route("GET", "/api/usage")
def _usage_list(req: Request) -> Response:
    try:
        limit = _parse_limit(req)
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    capability = (req.query1("capability") or "").strip() or None
    events = usage_ledger.list_usage_events(limit=limit, capability=capability)
    return Response.json(
        200,
        {
            "total": len(events),
            "events": events,
        },
    )


@route("GET", "/api/usage/summary")
def _usage_summary(req: Request) -> Response:
    capability = (req.query1("capability") or "").strip() or None
    return Response.json(200, usage_ledger.usage_summary(capability=capability))
