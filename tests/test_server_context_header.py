"""Tests for the ``X-Kater-Context`` header being threaded through the full
REST pipeline (``kater.api.server.handle``), not just ``authenticate()``
directly.

``authenticate()`` itself and route-level capability filtering are already
covered by test_authgate.py, test_context_tokens.py, and
test_capability_audit.py; this file only exercises the new
``request.header("x-kater-context")`` wiring added to ``handle()`` in
src/kater/api/server.py.
"""

from __future__ import annotations

import pytest

from kater.api import Request
from kater.api.server import handle
from kater.control_plane import contexts
from kater.control_plane import tokens as context_tokens


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "test-context-secret")
    context_tokens.reset_token_secret_cache()
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()


def _request(path: str, *, method: str = "GET", headers: dict[str, str] | None = None) -> Request:
    return Request(
        method=method,
        path=path,
        query={},
        headers={k.lower(): v for k, v in (headers or {}).items()},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1",
    )


def test_handle_without_context_header_still_works(ctx_db) -> None:
    """Regression: adding context_header support must not break plain requests."""
    resp = handle(_request("/api/capabilities"))
    assert resp.status == 200
    assert resp.payload is not None


def test_handle_applies_valid_context_header(ctx_db) -> None:
    record = contexts.create_context(
        principal_id="agent-handle",
        allowed_capabilities=["kater.profiles.list"],
    )
    token = context_tokens.issue_token(record, ttl_seconds=120)
    resp = handle(_request("/api/capabilities", headers={"X-Kater-Context": token}))
    assert resp.status == 200
    assert resp.payload is not None
    assert resp.payload["context"]["context_id"] == record.context_id
    ids = {item["capability_id"] for item in resp.payload["capabilities"]}
    assert ids == {"kater.profiles.list"}


def test_handle_rejects_invalid_context_header(ctx_db) -> None:
    resp = handle(_request("/api/capabilities", headers={"X-Kater-Context": "garbage"}))
    assert resp.status == 401
    assert resp.payload is not None
    assert "context" in resp.payload["error"].lower()


def test_handle_rejects_invalid_context_header_on_a_different_route(ctx_db) -> None:
    # Same wiring, a different (non-fabric) route — guards against the header
    # only being threaded through for /api/capabilities specifically.
    resp = handle(_request("/api/automations", headers={"X-Kater-Context": "garbage"}))
    assert resp.status == 401
    assert resp.payload is not None
    assert "context" in resp.payload["error"].lower()