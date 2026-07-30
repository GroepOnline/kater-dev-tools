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
    headers: dict[str, str] | None = None,
    raw_body: bytes | None = None,
) -> Response:
    """
    Invoke a registered API route with a constructed request.

    Parameters:
        method: HTTP method for the request.
        path: Request path.
        query: Optional query parameters.
        body: Optional JSON request body.
        headers: Optional extra request headers (merged with content-type).
        raw_body: Optional raw request body bytes, used instead of ``body``
            to exercise malformed-JSON handling.

    Returns:
        The response produced by the matched route handler.

    Raises:
        AssertionError: If no route matches the method and path.
    """
    matched = ROUTER.match(method, path)
    assert matched is not None, f"{method} {path} has no route"
    route, params = matched
    if raw_body is not None:
        raw = raw_body
    else:
        raw = b"" if body is None else json.dumps(body).encode()
    req_headers = dict(headers or {})
    if body is not None or raw_body is not None:
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


class TestCsvSetHelper:
    def test_none_and_empty_yield_empty_set(self) -> None:
        from kater.api.fabric_routes import _csv_set

        assert _csv_set(None) == frozenset()
        assert _csv_set("") == frozenset()

    def test_splits_and_trims_values(self) -> None:
        from kater.api.fabric_routes import _csv_set

        assert _csv_set("a, b ,, c") == frozenset({"a", "b", "c"})


class TestTruthyHelper:
    @pytest.mark.parametrize("raw", ["1", "true", "True", "yes", "YES", "on", " on "])
    def test_truthy_values(self, raw: str) -> None:
        from kater.api.fabric_routes import _truthy

        assert _truthy(raw) is True

    @pytest.mark.parametrize("raw", [None, "", "0", "false", "no", "off", "garbage"])
    def test_falsy_values(self, raw: str | None) -> None:
        from kater.api.fabric_routes import _truthy

        assert _truthy(raw) is False


@pytest.fixture
def token_db(tmp_path, monkeypatch):
    """Isolated working directory + reset caches for signed-context-token tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-context-secret")
    from kater.control_plane import tokens as context_tokens

    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


class TestIdentityOwnsContext:
    def test_scoped_identity_cannot_see_other_principals_context(self, token_db) -> None:
        from kater.control_plane import tokens as context_tokens

        mine = contexts.create_context(principal_id="agent-a")
        other = contexts.create_context(principal_id="agent-b")
        token = context_tokens.issue_token(mine, ttl_seconds=300)
        headers = {"x-kater-context": token}

        # Own context is visible...
        own = _call("GET", f"/api/contexts/{mine.context_id}", headers=headers)
        assert own.status == 200

        # ...but another principal's context is not, across every verb.
        assert _call("GET", f"/api/contexts/{other.context_id}", headers=headers).status == 404
        assert (
            _call(
                "POST", f"/api/contexts/{other.context_id}/revoke", headers=headers
            ).status
            == 404
        )
        assert (
            _call("DELETE", f"/api/contexts/{other.context_id}", headers=headers).status
            == 404
        )

    def test_unrestricted_identity_sees_any_context(self, token_db) -> None:
        record = contexts.create_context(principal_id="agent-c")
        # No context header at all => open/unrestricted identity.
        resp = _call("GET", f"/api/contexts/{record.context_id}")
        assert resp.status == 200


class TestContextsIssueToken:
    def test_issue_token_ok(self, ctx_db) -> None:
        record = contexts.create_context(principal_id="agent-token")
        resp = _call(
            "POST",
            f"/api/contexts/{record.context_id}/token",
            body={"ttl_seconds": 60},
        )
        assert resp.status == 200
        assert resp.payload is not None
        assert resp.payload["context_id"] == record.context_id
        assert resp.payload["token"]
        assert resp.payload["expires_at"] is not None

    def test_issue_token_malformed_body_returns_400(self, ctx_db) -> None:
        record = contexts.create_context(principal_id="agent-token")
        resp = _call(
            "POST",
            f"/api/contexts/{record.context_id}/token",
            raw_body=b"{not valid json",
        )
        assert resp.status == 400

    def test_issue_token_invalid_ttl_returns_400(self, ctx_db) -> None:
        record = contexts.create_context(principal_id="agent-token")
        resp = _call(
            "POST",
            f"/api/contexts/{record.context_id}/token",
            body={"ttl_seconds": "not-a-number"},
        )
        assert resp.status == 400
        assert resp.payload is not None
        assert "ttl_seconds" in resp.payload["error"]

    def test_issue_token_missing_context_returns_404(self, ctx_db) -> None:
        missing_id = "rctx_" + ("a" * 32)
        resp = _call("POST", f"/api/contexts/{missing_id}/token", body={})
        assert resp.status == 404

    def test_issue_token_revoked_context_returns_404(self, ctx_db) -> None:
        record = contexts.create_context(principal_id="agent-token")
        contexts.revoke_context(record.context_id)
        resp = _call(
            "POST",
            f"/api/contexts/{record.context_id}/token",
            body={},
        )
        assert resp.status == 404


class TestAuditCapabilitiesInvalidLimit:
    def test_non_integer_limit_returns_400(self) -> None:
        resp = _call("GET", "/api/audit/capabilities", query={"limit": ["not-an-int"]})
        assert resp.status == 400
        assert resp.payload is not None
        assert "limit" in resp.payload["error"]
