from __future__ import annotations

import pytest

from kater.connectors.errors import ConnectorExistsError
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    PermissionLevel,
    capability_required_permission,
    looks_like_secret_key,
    permission_allows,
)


def _transport() -> ConnectorTransport:
    return ConnectorTransport(
        kind="http",
        endpoint="https://example.invalid/v1",
        headers_template={"Authorization": "Bearer ${EXAMPLE_TOKEN}"},
    )


def test_capability_write_inference() -> None:
    assert capability_required_permission("github.issues.read") is PermissionLevel.READ
    assert capability_required_permission("github.issues.write") is PermissionLevel.WRITE
    assert capability_required_permission("cloudflare.dns.admin") is PermissionLevel.ADMIN


def test_permission_allows_matrix() -> None:
    assert permission_allows(PermissionLevel.READ, PermissionLevel.READ)
    assert not permission_allows(PermissionLevel.READ, PermissionLevel.WRITE)
    assert permission_allows(PermissionLevel.ADMIN, PermissionLevel.WRITE)
    assert not permission_allows(PermissionLevel.DISABLED, PermissionLevel.READ)


def test_literal_secret_in_header_template_rejected() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        ConnectorTransport(
            kind="http",
            endpoint="https://example.invalid",
            headers_template={"Authorization": "Bearer super-secret"},
        )


def test_metadata_secret_keys_rejected() -> None:
    with pytest.raises(ValueError, match="secret keys"):
        ConnectorRecord(
            id="proof.api",
            display_name="Proof",
            type=ConnectorType.API,
            version="1.0.0",
            transport=_transport(),
            metadata={"api_key": "nope"},
        )


def test_new_connector_defaults_disabled() -> None:
    record = ConnectorRecord(
        id="clickhouse",
        display_name="ClickHouse",
        type=ConnectorType.API,
        version="1.0.0",
        transport=_transport(),
        capabilities=(ConnectorCapability(id="clickhouse.ping"),),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.ENV, ref="CLICKHOUSE_URL"),
    )
    assert record.status is ConnectorStatus.DISABLED
    assert record.permission_for("ops") is PermissionLevel.DISABLED


def test_invalid_connector_id_rejected() -> None:
    with pytest.raises(ValueError, match="connector id"):
        ConnectorRecord(
            id="Click House",
            display_name="Bad",
            type=ConnectorType.API,
            version="1.0.0",
            transport=_transport(),
        )


def test_as_dict_has_refs_not_secrets() -> None:
    record = ConnectorRecord(
        id="github",
        display_name="GitHub",
        type=ConnectorType.MCP,
        version="1.0.0",
        transport=ConnectorTransport(
            kind="stdio",
            command="npx",
            env_template={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"},
        ),
        auth_binding=AuthBindingRef.from_env_names(["GITHUB_PERSONAL_ACCESS_TOKEN"]),
        status=ConnectorStatus.ENABLED,
        permissions={"ops": PermissionLevel.WRITE},
    )
    dumped = record.as_dict()
    blob = str(dumped)
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in blob
    assert "ghp_" not in blob
    assert dumped["auth_binding"]["kind"] == "env"


def test_looks_like_secret_key() -> None:
    assert looks_like_secret_key("Authorization")
    assert looks_like_secret_key("api-key")
    assert not looks_like_secret_key("display_name")


def test_exists_error_shape() -> None:
    err = ConnectorExistsError("github")
    assert err.as_dict()["error"] == "duplicate_connector"
    assert err.connector_id == "github"
