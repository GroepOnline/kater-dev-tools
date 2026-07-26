"""Signed remote-context tokens and discovery allowlist binding."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from kater.api import ROUTER, Request, Response
from kater.authgate import (
    AuthContext,
    RequestIdentity,
    authenticate,
    capability_allowed,
    identity_from_record,
    resolve_request_identity,
)
from kater.control_plane import contexts
from kater.control_plane import tokens as context_tokens
from kater.settings import KaterSettings


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-context-secret")
    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


def _call(
    method: str,
    path: str,
    *,
    query: dict[str, list[str]] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
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


def test_issue_verify_roundtrip(ctx_db) -> None:
    record = contexts.create_context(
        principal_id="agent-a",
        scopes=["github.read"],
        allowed_capabilities=["kater.profiles.list"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=120)
    assert token.count(".") == 1

    loaded = context_tokens.verify_token(token)
    assert loaded is not None
    assert loaded.context_id == record.context_id
    assert loaded.principal_id == "agent-a"

    identity = identity_from_record(loaded)
    assert identity.context_id == record.context_id
    assert identity.allowed_capabilities == frozenset({"kater.profiles.list"})


def test_revoked_context_token_fails(ctx_db) -> None:
    record = contexts.create_context(principal_id="agent-a")
    token = context_tokens.issue_token(record, ttl_seconds=120)
    contexts.revoke_context(record.context_id)
    assert context_tokens.verify_token(token) is None


def test_expired_token_fails(ctx_db, monkeypatch) -> None:
    record = contexts.create_context(principal_id="agent-a")
    token = context_tokens.issue_token(record, ttl_seconds=1)
    future = time.time() + 10
    monkeypatch.setattr(context_tokens.time, "time", lambda: future)
    assert context_tokens.verify_token(token) is None


def test_tampered_token_fails(ctx_db) -> None:
    record = contexts.create_context(principal_id="agent-a")
    token = context_tokens.issue_token(record, ttl_seconds=120)
    payload, sig = token.split(".", 1)
    tampered = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + sig
    assert context_tokens.verify_token(tampered) is None
    bad_sig = payload + "." + ("A" * len(sig))
    assert context_tokens.verify_token(bad_sig) is None


def test_issue_token_rest_endpoint(ctx_db) -> None:
    created = _call(
        "POST",
        "/api/contexts",
        body={"principal_id": "agent-rest", "allowed_capabilities": ["kater.profiles"]},
    )
    assert created.status == 201
    assert created.payload is not None
    context_id = created.payload["context_id"]

    issued = _call(
        "POST",
        f"/api/contexts/{context_id}/token",
        body={"ttl_seconds": 600},
    )
    assert issued.status == 200
    assert issued.payload is not None
    assert "token" in issued.payload
    assert issued.payload["expires_at"] > time.time()
    assert context_tokens.verify_token(issued.payload["token"]) is not None


def test_discover_filters_allowed_capabilities(ctx_db) -> None:
    record = contexts.create_context(
        principal_id="agent-filter",
        allowed_capabilities=["kater.profiles.list"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)

    open_resp = _call("GET", "/api/capabilities", query={"profile": ["core"]})
    assert open_resp.status == 200
    assert open_resp.payload is not None
    open_ids = {item["capability_id"] for item in open_resp.payload["capabilities"]}
    assert "kater.profiles.list" in open_ids
    assert len(open_ids) >= 2

    scoped = _call(
        "GET",
        "/api/capabilities",
        query={"profile": ["core"]},
        headers={"X-Kater-Context": token},
    )
    assert scoped.status == 200
    assert scoped.payload is not None
    scoped_ids = {item["capability_id"] for item in scoped.payload["capabilities"]}
    assert scoped_ids == {"kater.profiles.list"}
    assert scoped.payload["context"]["context_id"] == record.context_id


def test_authenticate_binds_context_header(ctx_db) -> None:
    record = contexts.create_context(
        principal_id="agent-auth",
        allowed_capabilities=["web.search"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)
    decision = authenticate(
        AuthContext(
            settings=KaterSettings(),
            path="/api/capabilities",
            context_header=token,
        )
    )
    assert decision.allowed is True
    assert isinstance(decision.identity, RequestIdentity)
    assert decision.identity.context_id == record.context_id
    assert decision.identity.allowed_capabilities == frozenset({"web.search"})


def test_authenticate_rejects_invalid_context_header(ctx_db) -> None:
    decision = authenticate(
        AuthContext(
            settings=KaterSettings(),
            path="/api/capabilities",
            context_header="not.a.validtoken",
        )
    )
    assert decision.allowed is False
    assert decision.error is not None
    assert "context" in decision.error.lower()


def test_resolve_request_identity_from_header(ctx_db) -> None:
    record = contexts.create_context(
        principal_id="agent-hdr",
        allowed_capabilities=["kater.profiles"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)
    req = Request(
        method="GET",
        path="/api/capabilities",
        query={},
        headers={"x-kater-context": token},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
    )
    identity = resolve_request_identity(req)
    assert identity.context_id == record.context_id
    assert capability_allowed("kater.profiles.list", identity.allowed_capabilities)
    assert not capability_allowed("web.search", identity.allowed_capabilities)
