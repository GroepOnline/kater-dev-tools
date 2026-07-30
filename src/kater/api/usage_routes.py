"""HTTP routes for the usage / cost events ledger.

Importing this module registers endpoints into ``models.ROUTER`` via
``@route``. Kept separate from fabric/computer handlers so parallel
agents can own those surfaces without merge fights.
"""

from __future__ import annotations

from typing import Any

from kater.api.models import Request, Response, route
from kater.authgate import capability_allowed, resolve_request_identity
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
    """
    Parse and constrain the requested usage event limit.

    Parameters:
        req (Request): Request containing the optional `limit` query parameter
        default (int): Value to use when `limit` is absent
        maximum (int): Upper bound for the parsed limit

    Returns:
        int: The limit clamped to the range from 1 through `maximum`

    Raises:
        ValueError: If the `limit` query parameter cannot be converted to an integer
    """
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


def _scoped_summary(summary: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    """Recompute a usage summary from the capabilities a scoped caller may see.

    Parameters:
        summary (dict[str, Any]): Full summary as returned by the ledger.
        allowed (frozenset[str]): Capability allowlist of the calling context.

    Returns:
        dict[str, Any]: Summary restricted to the allowed capabilities, with totals recomputed.
    """
    rows = [
        row
        for row in summary.get("capabilities", [])
        if capability_allowed(str(row.get("capability") or ""), allowed)
    ]
    total = sum(int(row.get("count") or 0) for row in rows)
    success = sum(int(row.get("success") or 0) for row in rows)
    cost = sum(float(row.get("total_cost_units") or 0) for row in rows)
    return {
        "total_events": total,
        "overall_success_rate": round((success / total) * 100, 1) if total else 0.0,
        "total_cost_units": round(cost, 4),
        "capabilities": rows,
    }


@route("GET", "/api/usage")
def _usage_list(req: Request) -> Response:
    """
    List usage events with optional capability filtering.

    Parameters:
        req (Request): The request containing the `limit` and optional `capability` query
            parameters.

    Returns:
        Response: A JSON response containing the event count and events, or a 400 error when `limit`
            is invalid.
    """
    try:
        limit = _parse_limit(req)
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    capability = (req.query1("capability") or "").strip() or None
    identity = resolve_request_identity(req)
    events = usage_ledger.list_usage_events(limit=limit, capability=capability)
    # A scoped context token only ever sees activity for capabilities on its
    # allowlist; an absent allowlist (admin/local caller) is unrestricted.
    if identity.allowed_capabilities is not None:
        events = [
            event
            for event in events
            if capability_allowed(
                str(event.get("capability") or ""), identity.allowed_capabilities
            )
        ]
    return Response.json(
        200,
        {
            "total": len(events),
            "events": events,
        },
    )


@route("GET", "/api/usage/summary")
def _usage_summary(req: Request) -> Response:
    """Return the usage summary, optionally filtered by capability.

    Parameters:
        req (Request): HTTP request containing the optional capability query parameter.

    Returns:
        Response: JSON response containing per-capability usage summary data.
    """
    capability = (req.query1("capability") or "").strip() or None
    identity = resolve_request_identity(req)
    summary = usage_ledger.usage_summary(capability=capability)
    if identity.allowed_capabilities is not None:
        summary = _scoped_summary(summary, identity.allowed_capabilities)
    return Response.json(200, summary)
