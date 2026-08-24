from __future__ import annotations

import pytest

from kater.connectors.models import ConnectorStatus, PermissionLevel
from kater.connectors.seed import seed_builtin_connectors
from kater.connectors.store import clear_connector_state, get_connector, list_connectors


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "LINEAR_API_KEY",
        "SENTRY_AUTH_TOKEN",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLICKHOUSE_URL",
        "CLICKHOUSE_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)


def test_seed_is_idempotent():
    first = seed_builtin_connectors()
    second = seed_builtin_connectors()
    assert first > 0
    assert second == first
    assert len(list_connectors()) == first


def test_in_scope_connectors_have_seed_origin():
    seed_builtin_connectors()
    for name in ("github", "linear", "sentry", "cloudflare"):
        record = get_connector(name)
        assert record.origin == "seed"


def test_out_of_scope_connectors_disabled():
    seed_builtin_connectors()
    for name in ("notion", "postgres", "slack", "upstash", "gitlab"):
        record = get_connector(name)
        assert record.status is ConnectorStatus.DISABLED
        assert record.metadata.get("scope") == "out_of_scope"
        assert record.permission_for("ops") is PermissionLevel.DISABLED


def test_github_enabled_when_env_present(monkeypatch):
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "gh_test")
    seed_builtin_connectors()
    github = get_connector("github")
    assert github.status is ConnectorStatus.ENABLED
    assert github.permission_for("ops") is PermissionLevel.WRITE
    assert github.permission_for("analysis") is PermissionLevel.READ


def test_clickhouse_proof_is_disabled_and_unsupported_without_url():
    seed_builtin_connectors()
    clickhouse = get_connector("clickhouse")
    assert clickhouse is not None
    assert clickhouse.status is ConnectorStatus.DISABLED
    assert clickhouse.metadata.get("shape") == "clickhouse"
    assert clickhouse.metadata.get("unsupported_runtime") is True
    assert clickhouse.origin == "seed"
