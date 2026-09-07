"""Native MCP tools for the agent-session transport.

Submit/continue/cancel/append/event-tail are MCP surfaces in this release. Full
session projection plus list/get/transition work remain REST-only; all surfaces
still share the same ``remote_contexts`` identity and transport store.
"""

from __future__ import annotations

import json
from typing import Any

from kater.authgate import get_request_identity
from kater.control_plane.session_transport import (
    SessionTransportError,
    append_event,
    cancel_work,
    continue_session,
    list_events,
    submit_work,
)


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **payload}


def _fail(exc: SessionTransportError) -> dict[str, Any]:
    return {"ok": False, "error": exc.message, "status": exc.status}


def kater_session_continue(context_id: str) -> dict[str, Any]:
    try:
        return _ok(continue_session(get_request_identity(), context_id))
    except SessionTransportError as exc:
        return _fail(exc)


def kater_session_submit(
    context_id: str,
    prompt: str,
    kater_context_id: str | None = None,
) -> dict[str, Any]:
    correlation: dict[str, Any] | None = None
    if kater_context_id is not None:
        correlation = {"katerContextId": kater_context_id}
    try:
        return _ok(submit_work(get_request_identity(), context_id, prompt, correlation=correlation))
    except SessionTransportError as exc:
        return _fail(exc)


def kater_session_events(
    context_id: str,
    after_seq: int = 0,
    limit: int = 100,
    wait_ms: int = 0,
) -> dict[str, Any]:
    try:
        return _ok(
            list_events(
                get_request_identity(),
                context_id,
                after_seq=after_seq,
                limit=limit,
                wait_ms=wait_ms,
            )
        )
    except SessionTransportError as exc:
        return _fail(exc)


def kater_session_cancel(
    context_id: str,
    work_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    try:
        return _ok(cancel_work(get_request_identity(), context_id, work_id, reason=reason))
    except SessionTransportError as exc:
        return _fail(exc)


def kater_session_append(
    context_id: str,
    event_type: str,
    work_id: str | None = None,
    payload_json: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    if payload_json:
        try:
            loaded = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"payload_json is not valid JSON: {exc}", "status": 400}
        if not isinstance(loaded, dict):
            return {"ok": False, "error": "payload_json must be an object", "status": 400}
        payload = loaded
    try:
        return _ok(
            append_event(
                get_request_identity(),
                context_id,
                event_type,
                work_id=work_id,
                payload=payload,
                provider=provider,
            )
        )
    except SessionTransportError as exc:
        return _fail(exc)
