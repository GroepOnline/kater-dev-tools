from __future__ import annotations

import os

import pytest

from kater.connectors.auth import (
    assert_auth,
    binding_is_satisfied,
    missing_auth_names,
    redact_mapping,
    redact_text,
)
from kater.connectors.errors import ConnectorAuthError
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
)
from kater.settings import KaterSettings, ServerOverride, save_settings


def _record(*, auth_ref: str = "MISSING_TOKEN") -> ConnectorRecord:
    return ConnectorRecord(
        id="auth.demo",
        display_name="Auth Demo",
        type=ConnectorType.INTERNAL,
        version="1.0.0",
        transport=ConnectorTransport(kind="native"),
        auth_binding=AuthBindingRef(kind=AuthBindingKind.ENV, ref=auth_ref),
        status=ConnectorStatus.ENABLED,
        origin="dynamic",
    )


def test_auth_missing_fail_closed() -> None:
    record = _record()
    assert binding_is_satisfied(record.auth_binding, connector_id=record.id) is False
    assert missing_auth_names(record.auth_binding, connector_id=record.id) == ("MISSING_TOKEN",)
    with pytest.raises(ConnectorAuthError) as exc:
        assert_auth(record)
    assert exc.value.code == "auth_missing"


def test_auth_satisfied_from_process_env(monkeypatch) -> None:
    monkeypatch.setenv("MISSING_TOKEN", "secret-value-not-in-record")
    record = _record()
    assert binding_is_satisfied(record.auth_binding, connector_id=record.id) is True
    assert_auth(record)


def test_auth_satisfied_from_settings_override(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = KaterSettings(
        server_overrides={
            "auth.demo": ServerOverride(env={"MISSING_TOKEN": "from-settings"}),
        }
    )
    save_settings(settings, tmp_path)
    record = _record()
    assert binding_is_satisfied(record.auth_binding, connector_id=record.id) is True


def test_redact_bearer_tokens() -> None:
    text = "Upstream failed: Bearer abc.def.ghi and more"
    assert redact_text(text) == "Upstream failed: Bearer *** and more"


def test_redact_named_secrets_and_authorization_header() -> None:
    text = "authorization: Bearer deadbeef token=supersecret"
    redacted = redact_text(text)
    assert "deadbeef" not in redacted
    assert "supersecret" not in redacted
    assert "***" in redacted


def test_redact_mapping_masks_secret_keys() -> None:
    payload = {
        "endpoint": "https://example.test",
        "api_key": "plain-secret",
        "nested": {"access_token": "nested-secret"},
    }
    redacted = redact_mapping(payload)
    assert redacted["endpoint"] == "https://example.test"
    assert redacted["api_key"] == "***"
    assert redacted["nested"]["access_token"] == "***"


def test_record_as_dict_never_contains_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("MISSING_TOKEN", "super-secret-token-value")
    record = _record()
    payload = record.as_dict()
    serialized = str(payload)
    assert "super-secret-token-value" not in serialized
    assert payload["auth_binding"]["ref"] == "MISSING_TOKEN"
    assert os.environ.get("MISSING_TOKEN") == "super-secret-token-value"
