from __future__ import annotations

import pytest

from kater.connectors.errors import ConnectorPolicyError
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    PermissionLevel,
)
from kater.connectors.policy import assert_profile_access, bind_profile, required_permission
from kater.connectors.store import clear_connector_state, create_connector, set_status


def _record(
    *,
    status: ConnectorStatus = ConnectorStatus.ENABLED,
    permissions: dict[str, PermissionLevel] | None = None,
) -> ConnectorRecord:
    return ConnectorRecord(
        id="policy.demo",
        display_name="Policy Demo",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        capabilities=(
            ConnectorCapability(id="policy.read"),
            ConnectorCapability(id="policy.write", mutation=True),
        ),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"core", "ops"}),
        permissions=permissions or {},
        status=status,
        origin="dynamic",
    )


@pytest.fixture(autouse=True)
def connector_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kater").mkdir()
    clear_connector_state()
    yield
    clear_connector_state()


def test_profile_read_access_allowed() -> None:
    record = _record(permissions={"core": PermissionLevel.READ})
    level = assert_profile_access(record, "core", "policy.read")
    assert level is PermissionLevel.READ


def test_write_blocked_when_only_read_granted() -> None:
    record = _record(permissions={"core": PermissionLevel.READ})
    with pytest.raises(ConnectorPolicyError) as exc:
        assert_profile_access(record, "core", "policy.write", mutation=True)
    assert exc.value.code == "policy_blocked"


def test_write_allowed_when_write_granted() -> None:
    record = _record(permissions={"core": PermissionLevel.WRITE})
    level = assert_profile_access(record, "core", "policy.write", mutation=True)
    assert level is PermissionLevel.WRITE


def test_admin_capability_requires_admin_permission() -> None:
    record = _record(permissions={"core": PermissionLevel.WRITE})
    with pytest.raises(ConnectorPolicyError):
        assert_profile_access(record, "core", "policy.admin.reset")


def test_admin_capability_allowed_with_admin_permission() -> None:
    record = _record(permissions={"core": PermissionLevel.ADMIN})
    level = assert_profile_access(record, "core", "policy.admin.reset")
    assert level is PermissionLevel.ADMIN


def test_disabled_connector_blocks_read() -> None:
    record = _record(status=ConnectorStatus.DISABLED, permissions={"core": PermissionLevel.READ})
    with pytest.raises(ConnectorPolicyError) as exc:
        assert_profile_access(record, "core", "policy.read")
    assert exc.value.code == "policy_blocked"


def test_new_connector_defaults_disabled_without_implicit_write() -> None:
    record = ConnectorRecord(
        id="fresh.demo",
        display_name="Fresh",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.NONE),
        profiles=frozenset({"core"}),
    )
    create_connector(record)
    assert record.status is ConnectorStatus.DISABLED
    assert record.permission_for("core") is PermissionLevel.DISABLED
    with pytest.raises(ConnectorPolicyError):
        assert_profile_access(record, "core", "fresh.read")


def test_enabled_connector_without_explicit_permission_defaults_read_only() -> None:
    record = _record(status=ConnectorStatus.ENABLED, permissions={})
    assert record.permission_for("core") is PermissionLevel.READ
    assert_profile_access(record, "core", "policy.read")
    with pytest.raises(ConnectorPolicyError):
        assert_profile_access(record, "core", "policy.write", mutation=True)


def test_bind_profile_persists_permission() -> None:
    create_connector(_record(status=ConnectorStatus.DISABLED))
    set_status("policy.demo", ConnectorStatus.ENABLED)
    updated = bind_profile("policy.demo", "core", PermissionLevel.WRITE)
    assert updated.permissions["core"] is PermissionLevel.WRITE


def test_required_permission_mutation_hint() -> None:
    assert required_permission("policy.read", mutation=False) is PermissionLevel.READ
    assert required_permission("policy.read", mutation=True) is PermissionLevel.WRITE
    assert required_permission("policy.admin.reset") is PermissionLevel.ADMIN
