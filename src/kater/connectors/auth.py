"""Connector auth binding resolution and redaction helpers."""

from __future__ import annotations

import os
import re
from typing import Any

from kater.connectors.errors import ConnectorAuthError
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorRecord,
    looks_like_secret_key,
)
from kater.settings import load_settings

_BEARER_SECRET = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_NAMED_SECRET = re.compile(
    r"(?i)\b(authorization|api[-_ ]?key|token|secret|password)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_AUTH_HEADER = re.compile(r"(?i)(authorization\s*:\s*)([^\s,;]+)")


def _env_names_from_binding(binding: AuthBindingRef) -> tuple[str, ...]:
    if binding.kind is AuthBindingKind.NONE:
        return ()
    return tuple(name.strip() for name in binding.ref.split(",") if name.strip())


def _stored_env_for_connector(connector_id: str) -> dict[str, str]:
    settings = load_settings()
    override = settings.server_overrides.get(connector_id)
    if not override:
        return {}
    env = dict(override.env or {})
    if override.connections:
        env = {**env, **override.connections[0].env}
    return env


def _env_has_value(name: str, *, connector_id: str | None = None) -> bool:
    if os.environ.get(name):
        return True
    if connector_id:
        stored = _stored_env_for_connector(connector_id)
        if stored.get(name):
            return True
        settings_env = load_settings().get_server_env(connector_id)
        if settings_env.get(name):
            return True
    return False


def binding_is_satisfied(
    binding: AuthBindingRef,
    *,
    connector_id: str | None = None,
) -> bool:
    """Return True when all referenced credential names are present."""
    if binding.kind is AuthBindingKind.NONE:
        return True
    names = _env_names_from_binding(binding)
    if not names:
        return binding.kind is AuthBindingKind.NONE
    if binding.kind is AuthBindingKind.SETTINGS:
        stored = _stored_env_for_connector(connector_id or "")
        return all(stored.get(name) or os.environ.get(name) for name in names)
    # env, chefvault, and other named bindings resolve via process/settings env.
    return all(_env_has_value(name, connector_id=connector_id) for name in names)


def missing_auth_names(
    binding: AuthBindingRef,
    *,
    connector_id: str | None = None,
) -> tuple[str, ...]:
    """Return env/settings key names that are still missing (never secret values)."""
    if binding.kind is AuthBindingKind.NONE:
        return ()
    names = _env_names_from_binding(binding)
    missing: list[str] = []
    for name in names:
        if not _env_has_value(name, connector_id=connector_id):
            missing.append(name)
    return tuple(missing)


def assert_auth(record: ConnectorRecord) -> None:
    """Raise ConnectorAuthError when required auth bindings are unsatisfied."""
    if binding_is_satisfied(record.auth_binding, connector_id=record.id):
        return
    missing = missing_auth_names(record.auth_binding, connector_id=record.id)
    if missing:
        message = f"missing auth for connector {record.id!r}: {', '.join(missing)}"
    else:
        message = f"auth binding unsatisfied for connector {record.id!r}"
    raise ConnectorAuthError(message, connector_id=record.id)


def redact_text(text: str | None) -> str:
    """Redact bearer tokens and named secrets from free-form text."""
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    cleaned = _BEARER_SECRET.sub("Bearer ***", cleaned)
    cleaned = _NAMED_SECRET.sub(r"\1\2***", cleaned)
    cleaned = _AUTH_HEADER.sub(r"\1***", cleaned)
    return cleaned[:500]


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with secret-like keys masked."""
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if looks_like_secret_key(str(key)):
            redacted[key] = "***"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted
