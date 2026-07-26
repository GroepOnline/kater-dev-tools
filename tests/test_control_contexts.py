"""Unit tests for remote context persistence (CHE-695)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kater.control_plane import contexts
from kater.control_plane.models import RemoteContext


@pytest.fixture
def ctx_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    contexts.reset_cache()
    yield tmp_path
    contexts.reset_cache()


def test_create_and_get_context(ctx_db) -> None:
    record = contexts.create_context(
        principal_id="agent-1",
        label="demo",
        profile="ops",
        scopes=["github.read", "models.invoke"],
        repository="acme/app",
        environment="staging",
        allowed_capabilities=["web.search"],
        ttl_seconds=3600,
        metadata={"ticket": "CHE-695"},
    )
    assert record.context_id.startswith("rctx_")
    assert len(record.context_id) == len("rctx_") + 32
    assert record.principal_id == "agent-1"
    assert record.label == "demo"
    assert record.profile == "ops"
    assert record.scopes == frozenset({"github.read", "models.invoke"})
    assert record.allowed_capabilities == frozenset({"web.search"})
    assert record.repository == "acme/app"
    assert record.environment == "staging"
    assert record.metadata == {"ticket": "CHE-695"}
    assert record.expires_at is not None
    assert record.is_active()

    loaded = contexts.get_context(record.context_id)
    assert loaded is not None
    assert loaded.to_dict()["context_id"] == record.context_id
    assert loaded.to_dict()["active"] is True

    remote = loaded.as_remote_context()
    assert isinstance(remote, RemoteContext)
    assert remote.allows(frozenset({"github.read"}))
    assert not remote.allows(frozenset({"github.write"}))


def test_create_context_requires_principal(ctx_db) -> None:
    with pytest.raises(ValueError, match="principal_id"):
        contexts.create_context(principal_id="  ")


def test_list_filters_principal_and_revoked(ctx_db) -> None:
    a = contexts.create_context(principal_id="a", scopes=["x"])
    b = contexts.create_context(principal_id="b", scopes=["y"])
    contexts.revoke_context(a.context_id)

    active_a = contexts.list_contexts(principal_id="a")
    assert active_a == []

    all_a = contexts.list_contexts(principal_id="a", include_revoked=True)
    assert [row.context_id for row in all_a] == [a.context_id]
    assert all_a[0].revoked_at is not None
    assert not all_a[0].is_active()

    only_b = contexts.list_contexts(principal_id="b")
    assert [row.context_id for row in only_b] == [b.context_id]


def test_revoke_is_idempotent(ctx_db) -> None:
    record = contexts.create_context(principal_id="agent-1")
    first = contexts.revoke_context(record.context_id)
    second = contexts.revoke_context(record.context_id)
    assert first is not None and second is not None
    assert first.revoked_at == second.revoked_at
    assert contexts.revoke_context("rctx_" + "0" * 32) is None


def test_purge_expired_removes_only_expired(ctx_db) -> None:
    alive = contexts.create_context(principal_id="agent-1", ttl_seconds=3600)
    expired = contexts.create_context(principal_id="agent-1", ttl_seconds=1)
    # Force expiry in the past via direct update through revoke path timing.
    past = datetime.now(UTC) - timedelta(seconds=10)
    with contexts._lock:
        db = contexts._get_db()
        db.execute(
            "UPDATE remote_contexts SET expires_at = ? WHERE context_id = ?",
            (past.timestamp(), expired.context_id),
        )
        db.commit()

    removed = contexts.purge_expired(now=datetime.now(UTC))
    assert removed == 1
    assert contexts.get_context(expired.context_id) is None
    assert contexts.get_context(alive.context_id) is not None
