"""Signed remote-context tokens and discovery allowlist binding."""

from __future__ import annotations

import time

import pytest

from kater.api import Request
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
from tests._rest import call


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    """Configure an isolated test database and reset context-related caches before and after the
        test.

    Parameters:
        tmp_path: Temporary directory used as the test working directory.
        monkeypatch: Pytest fixture for temporarily changing the environment and working directory.

    Yields:
        The temporary test directory.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-context-secret")
    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


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


def test_mint_context_token_rejects_revoked_context(ctx_db) -> None:
    record = contexts.create_context(principal_id="agent-a")
    contexts.revoke_context(record.context_id)
    with pytest.raises(ValueError, match="context is not active"):
        contexts.mint_context_token(record.context_id, ttl_seconds=120)


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
    created = call(
        "POST",
        "/api/contexts",
        body={"principal_id": "agent-rest", "allowed_capabilities": ["kater.profiles"]},
    )
    assert created.status == 201
    assert created.payload is not None
    context_id = created.payload["context_id"]

    issued = call(
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

    open_resp = call("GET", "/api/capabilities", query={"profile": ["core"]})
    assert open_resp.status == 200
    assert open_resp.payload is not None
    open_ids = {item["capability_id"] for item in open_resp.payload["capabilities"]}
    assert "kater.profiles.list" in open_ids
    assert len(open_ids) >= 2

    scoped = call(
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


def test_scoped_caller_cannot_create_a_broader_context(ctx_db) -> None:
    """A restricted context token may not mint a context with wider permissions."""
    record = contexts.create_context(
        principal_id="agent-scoped",
        scopes=["github.read"],
        allowed_capabilities=["kater.profiles.list"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)
    headers = {"X-Kater-Context": token}

    other_principal = call(
        "POST",
        "/api/contexts",
        body={"principal_id": "agent-admin"},
        headers=headers,
    )
    assert other_principal.status == 403

    wider_capabilities = call(
        "POST",
        "/api/contexts",
        body={
            "principal_id": "agent-scoped",
            "allowed_capabilities": ["kater.profiles.list", "web.search"],
        },
        headers=headers,
    )
    assert wider_capabilities.status == 403

    unrestricted = call(
        "POST",
        "/api/contexts",
        body={"principal_id": "agent-scoped"},
        headers=headers,
    )
    assert unrestricted.status == 403

    wider_scopes = call(
        "POST",
        "/api/contexts",
        body={
            "principal_id": "agent-scoped",
            "scopes": ["github.read", "github.write"],
            "allowed_capabilities": ["kater.profiles.list"],
        },
        headers=headers,
    )
    assert wider_scopes.status == 403


def test_scoped_caller_can_create_a_narrower_context(ctx_db) -> None:
    """Non-broadening context creation stays available to scoped callers."""
    record = contexts.create_context(
        principal_id="agent-narrow",
        scopes=["github.read", "github.write"],
        allowed_capabilities=["kater.profiles"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=300)

    created = call(
        "POST",
        "/api/contexts",
        body={
            "principal_id": "agent-narrow",
            "scopes": ["github.read"],
            "allowed_capabilities": ["kater.profiles.list"],
        },
        headers={"X-Kater-Context": token},
    )
    assert created.status == 201
    assert created.payload is not None
    assert created.payload["principal_id"] == "agent-narrow"


def test_unscoped_caller_still_creates_any_context(ctx_db) -> None:
    """Requests without a context token keep administrative creation rights."""
    created = call(
        "POST",
        "/api/contexts",
        body={"principal_id": "agent-any", "allowed_capabilities": ["web.search"]},
    )
    assert created.status == 201
