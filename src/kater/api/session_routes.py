"""REST + OpenAPI for the agent-session work/event transport.

Importing this module registers endpoints into ``models.ROUTER`` via ``@route``.
"""

from __future__ import annotations

from typing import Any

from kater.api.models import Request, Response, route
from kater.authgate import resolve_request_identity
from kater.control_plane.session_transport import (
    CAP_CANCEL,
    CAP_CONTINUE,
    CAP_EVENTS_APPEND,
    CAP_EVENTS_READ,
    CAP_SUBMIT,
    CAP_TRANSITION,
    SessionTransportError,
    append_event,
    cancel_work,
    continue_session,
    events_as_sse,
    get_work,
    list_events,
    list_work,
    session_projection,
    submit_work,
    transition_work,
)

_ERROR = {
    "description": "Error",
    "content": {
        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
    },
}
_JSON_OK = {"content": {"application/json": {"schema": {"type": "object"}}}}
_CONTEXT_PARAM = {
    "name": "context_id",
    "in": "path",
    "required": True,
    "schema": {"type": "string"},
}
_WORK_PARAM = {
    "name": "work_id",
    "in": "path",
    "required": True,
    "schema": {"type": "string"},
}


SESSION_OPENAPI_PATHS: dict[str, Any] = {
    "/api/contexts/{context_id}/session": {
        "get": {
            "summary": "Project a remote context as an agent session",
            "parameters": [_CONTEXT_PARAM],
            "responses": {"200": {"description": "Session projection.", **_JSON_OK}, "404": _ERROR},
        }
    },
    "/api/contexts/{context_id}/session/continue": {
        "post": {
            "summary": "Continue an active agent session",
            "parameters": [_CONTEXT_PARAM],
            "responses": {
                "200": {"description": "Continued session.", **_JSON_OK},
                "403": _ERROR,
                "404": _ERROR,
                "409": _ERROR,
            },
        }
    },
    "/api/contexts/{context_id}/session/work": {
        "get": {
            "summary": "List NL work for a session",
            "parameters": [_CONTEXT_PARAM],
            "responses": {"200": {"description": "Work list.", **_JSON_OK}, "404": _ERROR},
        },
        "post": {
            "summary": "Submit natural-language work on a session",
            "parameters": [_CONTEXT_PARAM],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "201": {"description": "Accepted work.", **_JSON_OK},
                "400": _ERROR,
                "403": _ERROR,
                "404": _ERROR,
                "409": _ERROR,
            },
        },
    },
    "/api/contexts/{context_id}/session/work/{work_id}": {
        "get": {
            "summary": "Get one work item",
            "parameters": [_CONTEXT_PARAM, _WORK_PARAM],
            "responses": {"200": {"description": "Work item.", **_JSON_OK}, "404": _ERROR},
        }
    },
    "/api/contexts/{context_id}/session/work/{work_id}/cancel": {
        "post": {
            "summary": "Cancel session work",
            "parameters": [_CONTEXT_PARAM, _WORK_PARAM],
            "requestBody": {
                "required": False,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "200": {"description": "Cancelled work.", **_JSON_OK},
                "403": _ERROR,
                "404": _ERROR,
                "409": _ERROR,
            },
        }
    },
    "/api/contexts/{context_id}/session/work/{work_id}/transition": {
        "post": {
            "summary": "Advance work through the agent state machine",
            "parameters": [_CONTEXT_PARAM, _WORK_PARAM],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "200": {"description": "Updated work.", **_JSON_OK},
                "400": _ERROR,
                "403": _ERROR,
                "404": _ERROR,
                "409": _ERROR,
            },
        }
    },
    "/api/contexts/{context_id}/session/events": {
        "get": {
            "summary": "Poll or stream authoritative session events",
            "parameters": [
                _CONTEXT_PARAM,
                {
                    "name": "after_seq",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 0},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 100},
                },
                {
                    "name": "wait_ms",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 0},
                },
                {
                    "name": "stream",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "boolean", "default": False},
                },
            ],
            "responses": {
                "200": {
                    "description": "Session events as JSON or SSE.",
                    "content": {
                        "application/json": {"schema": {"type": "object"}},
                        "text/event-stream": {"schema": {"type": "string"}},
                    },
                },
                "404": _ERROR,
            },
        },
        "post": {
            "summary": "Append a Kater-neutral session event",
            "parameters": [_CONTEXT_PARAM],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "201": {"description": "Stored event.", **_JSON_OK},
                "400": _ERROR,
                "403": _ERROR,
                "404": _ERROR,
                "409": _ERROR,
            },
        },
    },
    "/api/contexts/{context_id}/session/events/stream": {
        "get": {
            "summary": "SSE snapshot of session events",
            "parameters": [
                _CONTEXT_PARAM,
                {
                    "name": "after_seq",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 0},
                },
                {
                    "name": "wait_ms",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 0},
                },
            ],
            "responses": {
                "200": {
                    "description": "text/event-stream batch.",
                    "content": {"text/event-stream": {"schema": {"type": "string"}}},
                },
                "404": _ERROR,
            },
        }
    },
}

# Referenced by tests that assert capability ids are published.
SESSION_CAPABILITIES = (
    CAP_CONTINUE,
    CAP_SUBMIT,
    CAP_CANCEL,
    CAP_TRANSITION,
    CAP_EVENTS_READ,
    CAP_EVENTS_APPEND,
)


def _fail(exc: SessionTransportError) -> Response:
    return Response.json(exc.status, {"error": exc.message})


def _int_query(req: Request, name: str, default: int) -> int:
    raw = req.query1(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SessionTransportError(400, f"{name} must be an integer") from exc


def _wants_sse(req: Request) -> bool:
    accept = (req.header("accept") or "").lower()
    stream = (req.query1("stream") or "").strip().lower()
    return "text/event-stream" in accept or stream in {"1", "true", "yes", "on"}


def _sse(payload: dict[str, Any]) -> Response:
    return Response(
        status=200,
        body=events_as_sse(payload),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-store", "Vary": "Authorization, X-Kater-Context"},
    )


@route("GET", "/api/contexts/{context_id}/session")
def _session_get(req: Request) -> Response:
    try:
        payload = session_projection(resolve_request_identity(req), req.params["context_id"])
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(200, payload)


@route("POST", "/api/contexts/{context_id}/session/continue")
def _session_continue(req: Request) -> Response:
    try:
        payload = continue_session(resolve_request_identity(req), req.params["context_id"])
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(200, payload)


@route("GET", "/api/contexts/{context_id}/session/work")
def _session_work_list(req: Request) -> Response:
    try:
        payload = list_work(resolve_request_identity(req), req.params["context_id"])
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(200, payload)


@route("POST", "/api/contexts/{context_id}/session/work")
def _session_work_submit(req: Request) -> Response:
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "body must be an object"})
    correlation = body.get("correlation")
    if correlation is not None and not isinstance(correlation, dict):
        return Response.json(400, {"error": "correlation must be an object"})
    try:
        payload = submit_work(
            resolve_request_identity(req),
            req.params["context_id"],
            str(body.get("prompt") or ""),
            correlation=correlation,
        )
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(201, payload)


@route("GET", "/api/contexts/{context_id}/session/work/{work_id}")
def _session_work_get(req: Request) -> Response:
    try:
        payload = get_work(
            resolve_request_identity(req),
            req.params["context_id"],
            req.params["work_id"],
        )
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(200, payload)


@route("POST", "/api/contexts/{context_id}/session/work/{work_id}/cancel")
def _session_work_cancel(req: Request) -> Response:
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "body must be an object"})
    reason = body.get("reason")
    try:
        payload = cancel_work(
            resolve_request_identity(req),
            req.params["context_id"],
            req.params["work_id"],
            reason=None if reason is None else str(reason),
        )
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(200, payload)


@route("POST", "/api/contexts/{context_id}/session/work/{work_id}/transition")
def _session_work_transition(req: Request) -> Response:
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "body must be an object"})
    state = str(body.get("state") or "").strip()
    if not state:
        return Response.json(400, {"error": "state is required"})
    reason = body.get("reason")
    try:
        payload = transition_work(
            resolve_request_identity(req),
            req.params["context_id"],
            req.params["work_id"],
            state,
            reason=None if reason is None else str(reason),
        )
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(200, payload)


@route("GET", "/api/contexts/{context_id}/session/events")
def _session_events_list(req: Request) -> Response:
    try:
        payload = list_events(
            resolve_request_identity(req),
            req.params["context_id"],
            after_seq=_int_query(req, "after_seq", 0),
            limit=_int_query(req, "limit", 100),
            wait_ms=_int_query(req, "wait_ms", 0),
        )
    except SessionTransportError as exc:
        return _fail(exc)
    if _wants_sse(req):
        return _sse(payload)
    return Response.json(200, payload)


@route("POST", "/api/contexts/{context_id}/session/events")
def _session_events_append(req: Request) -> Response:
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "body must be an object"})
    payload_obj = body.get("payload")
    if payload_obj is not None and not isinstance(payload_obj, dict):
        return Response.json(400, {"error": "payload must be an object"})
    try:
        stored = append_event(
            resolve_request_identity(req),
            req.params["context_id"],
            str(body.get("type") or ""),
            work_id=None if body.get("work_id") is None else str(body.get("work_id")),
            payload=payload_obj,
            provider=body.get("provider"),
        )
    except SessionTransportError as exc:
        return _fail(exc)
    return Response.json(201, stored)


@route("GET", "/api/contexts/{context_id}/session/events/stream")
def _session_events_stream(req: Request) -> Response:
    try:
        payload = list_events(
            resolve_request_identity(req),
            req.params["context_id"],
            after_seq=_int_query(req, "after_seq", 0),
            limit=_int_query(req, "limit", 100),
            wait_ms=_int_query(req, "wait_ms", 0),
        )
    except SessionTransportError as exc:
        return _fail(exc)
    return _sse(payload)
