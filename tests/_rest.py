"""Shared REST test helper for driving the in-process ROUTER.

Consolidates the near-identical ``_call`` helpers that previously lived in
several test modules. The signature is a superset of those variants: it
accepts optional ``query``, ``body``, and ``headers`` and preserves the exact
request shape the callers rely on (localhost base_url, JSON body encoding, and
lower-cased header keys).
"""

from __future__ import annotations

import json
from typing import Any

from kater.api import ROUTER, Request, Response


def call(
    method: str,
    path: str,
    *,
    query: dict[str, list[str]] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """
    Dispatch an in-process request to the handler matching the given method and path.

    Parameters:
        method (str): HTTP method to match.
        path (str): Request path to match.
        query (dict[str, list[str]] | None): Query parameters for the request.
        body (dict[str, Any] | None): Request body to encode as JSON.
        headers (dict[str, str] | None): Request headers.

    Returns:
        Response: The matched route handler's response.
    """
    matched = ROUTER.match(method, path)
    assert matched is not None, f"{method} {path} has no route"
    route, params = matched
    raw = b"" if body is None else json.dumps(body).encode()
    req_headers = dict(headers or {})
    if body is not None:
        req_headers.setdefault("content-type", "application/json")
    req = Request(
        method=method,
        path=path,
        query=query or {},
        headers={k.lower(): v for k, v in req_headers.items()},
        raw_body=raw,
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
        params=params,
    )
    return route.handler(req)
