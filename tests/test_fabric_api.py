"""REST coverage for capability discovery and remote contexts."""

from __future__ import annotations

import json
from typing import Any

import pytest

from kater.api import ROUTER, Request, Response
from kater.control_plane import contexts


def _call(
    method: str,
    path: str,
    *,
    query: dict[str, list[str]] | None = None,
    body: dict[str, Any] | None = None,
) -> Response:
    """
    Invoke a registered API route with a constructed request.
    
    Parameters:
        method: HTTP method for the request.
        path: Request path.
        query: Optional query parameters.
        body: Optional JSON request body.
    
    Returns:
        The response produced by the matched route handler.
    
    Raises:
        AssertionError: If no route matches the method and path.
    """
    matched = ROUTER.match(method, path)
    assert matched is not None, f"{method} {path} has no route"
    route, params = matched
    raw = b"" if body is None else json.dumps(body).encode()
    headers = {"content-type": "application/json"} if body is not None else {}
    req = Request(
        method=method,
        path=path,
        query=query or {},
        headers=headers,
        raw_body=raw,
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
        params=params,
    )
    return route.handler(req)


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    """
    Provide an isolated temporary working directory for context-related tests.
    
    Parameters:
        tmp_path: Temporary directory used as the test working directory.
    
    Yields:
        pathlib.Path: The temporary working directory.
    """
    monkeypatch.chdir(tmp_path)
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()


def test_capabilities_discover_route_registered() -> None:
    assert ROUTER.match("GET", "/api/capabilities") is not None
    assert ROUTER.match("GET", "/api/capabilities/kater.profiles.list") is not None


def test_capabilities_discover_returns_builtins() -> None:
    resp = _call("GET", "/api/capabilities", query={"profile": ["core"]})
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["total"] >= 1
    ids = {item["capability_id"] for item in resp.payload["capabilities"]}
    assert "kater.profiles.list" in ids
    assert resp.payload["context"]["max_risk"] == "external_write"


def test_capabilities_discover_rejects_bad_max_risk() -> None:
    resp = _call("GET", "/api/capabilities", query={"max_risk": ["nope"]})
    assert resp.status == 400
    assert resp.payload is not None
    assert "max_risk" in resp.payload["error"]


def test_capabilities_get_known_and_missing() -> None:
    ok = _call("GET", "/api/capabilities/kater.profiles.list")
    assert ok.status == 200
    assert ok.payload is not None
    assert ok.payload["capability_id"] == "kater.profiles.list"
    assert ok.payload["transport"] == "native"

    missing = _call("GET", "/api/capabilities/does.not.exist")
    assert missing.status == 404


def test_contexts_crud_and_revoke(ctx_db) -> None:
    created = _call(
        "POST",
        "/api/contexts",
        body={
            "principal_id": "agent-9",
            "label": "lane",
            "scopes": ["github.read"],
            "ttl_seconds": 120,
        },
    )
    assert created.status == 201
    assert created.payload is not None
    context_id = created.payload["context_id"]
    assert context_id.startswith("rctx_")
    assert created.payload["active"] is True

    listed = _call("GET", "/api/contexts", query={"principal_id": ["agent-9"]})
    assert listed.status == 200
    assert listed.payload is not None
    assert listed.payload["total"] == 1

    got = _call("GET", f"/api/contexts/{context_id}")
    assert got.status == 200
    assert got.payload is not None
    assert got.payload["principal_id"] == "agent-9"

    revoked = _call("POST", f"/api/contexts/{context_id}/revoke")
    assert revoked.status == 200
    assert revoked.payload is not None
    assert revoked.payload["revoked_at"] is not None
    assert revoked.payload["active"] is False

    listed_active = _call("GET", "/api/contexts", query={"principal_id": ["agent-9"]})
    assert listed_active.payload is not None
    assert listed_active.payload["total"] == 0

    deleted = _call("DELETE", f"/api/contexts/{context_id}")
    assert deleted.status == 200
    assert deleted.payload is not None
    assert deleted.payload["revoked_at"] is not None


def test_contexts_create_requires_principal(ctx_db) -> None:
    resp = _call("POST", "/api/contexts", body={"label": "x"})
    assert resp.status == 400
    assert resp.payload is not None
    assert "principal_id" in resp.payload["error"]


def test_contexts_missing_returns_404(ctx_db) -> None:
    missing_id = "rctx_" + ("a" * 32)
    assert _call("GET", f"/api/contexts/{missing_id}").status == 404
    assert _call("POST", f"/api/contexts/{missing_id}/revoke").status == 404
    assert _call("DELETE", f"/api/contexts/{missing_id}").status == 404
