"""Secret-free connection views over env bindings and Catalog Connect accounts.

A connection is the credential/account binding for one integration. Values never
leave this module: API and catalog rows expose ids, labels, and secret *names*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kater.connect import list_connections, source_is_configured
from kater.connectors.auth import binding_is_satisfied, missing_auth_names
from kater.connectors.models import AuthBindingKind, ConnectorRecord
from kater.connectors.store import get_connector, list_connectors
from kater.profiles import (
    ToolSource,
    all_tool_sources,
    is_private_source,
    is_public_mode,
    visible_tool_sources,
)
from kater.settings import load_settings


@dataclass(frozen=True, slots=True)
class IntegrationManifest:
    """Provider adapter behind a toolkit. Credentials stay on connections."""

    id: str
    toolkit: str
    transport: str
    auth_kind: str
    actions: tuple[str, ...] = ()
    connections: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "toolkit": self.toolkit,
            "transport": self.transport,
            "auth_kind": self.auth_kind,
            "actions": list(self.actions),
            "connections": list(self.connections),
        }


@dataclass(frozen=True, slots=True)
class ConnectionView:
    """Agent-facing connection row. Never contains secret values."""

    id: str
    toolkit: str
    integration: str
    label: str
    origin: str
    auth_kind: str
    configured: bool
    status: str
    secret_names: tuple[str, ...] = ()
    created_at: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "toolkit": self.toolkit,
            "integration": self.integration,
            "label": self.label,
            "origin": self.origin,
            "auth_kind": self.auth_kind,
            "configured": self.configured,
            "status": self.status,
            "secret_names": list(self.secret_names),
            "created_at": self.created_at,
        }


def default_connection_id(integration_id: str) -> str:
    return f"{integration_id}:default"


def parse_connection_id(connection_id: str) -> tuple[str, str]:
    text = (connection_id or "").strip()
    if not text:
        raise ValueError("connection id is required")
    if ":" not in text:
        return text, "default"
    integration, _, suffix = text.partition(":")
    if not integration or not suffix:
        raise ValueError(f"invalid connection id: {connection_id!r}")
    return integration, suffix


def _secret_names(record: ConnectorRecord | None, source: ToolSource | None) -> tuple[str, ...]:
    names: list[str] = []
    if record is not None and record.auth_binding.kind is not AuthBindingKind.NONE:
        names.extend(
            part.strip() for part in record.auth_binding.ref.split(",") if part.strip()
        )
    if source is not None:
        names.extend(source.env)
        if source.oauth:
            names.append(source.oauth.token_env)
    return tuple(dict.fromkeys(names))


def _default_view(
    integration_id: str,
    *,
    record: ConnectorRecord | None,
    source: ToolSource | None,
) -> ConnectionView:
    settings = load_settings()
    if record is not None:
        configured = binding_is_satisfied(record.auth_binding, connector_id=record.id)
        missing = tuple(missing_auth_names(record.auth_binding, connector_id=record.id))
        status = "ready" if configured else ("auth_missing" if missing else record.status.value)
        auth_kind = record.auth_binding.kind.value
    elif source is not None:
        configured = source_is_configured(source, settings)
        status = "ready" if configured else "auth_missing"
        auth_kind = "oauth" if source.oauth else ("env" if source.env else "none")
    else:
        configured = False
        status = "unknown"
        auth_kind = "none"
    return ConnectionView(
        id=default_connection_id(integration_id),
        toolkit=integration_id,
        integration=integration_id,
        label="default",
        origin="env",
        auth_kind=auth_kind,
        configured=configured,
        status=status,
        secret_names=_secret_names(record, source),
    )


def _oauth_views(source: ToolSource) -> list[ConnectionView]:
    views: list[ConnectionView] = []
    for conn in list_connections(source):
        views.append(
            ConnectionView(
                id=f"{source.name}:{conn.id}",
                toolkit=source.name,
                integration=source.name,
                label=conn.label or conn.extra.get("team") or conn.extra.get("tenant") or conn.id,
                origin="oauth",
                auth_kind="oauth",
                configured=True,
                status="ready",
                secret_names=tuple(sorted(conn.env)),
                created_at=conn.created_at or None,
            )
        )
    return views


def _hidden_integration_ids() -> set[str]:
    if not is_public_mode():
        return set()
    return {source.name for source in all_tool_sources() if is_private_source(source)}


def list_connection_views(
    records: dict[str, ConnectorRecord] | None = None,
) -> list[ConnectionView]:
    """Return every default and saved connection without secret values."""
    sources = {source.name: source for source in visible_tool_sources()}
    if records is None:
        try:
            records = {record.id: record for record in list_connectors()}
        except Exception:
            records = {}
    hidden = _hidden_integration_ids()
    views: list[ConnectionView] = []
    seen: set[str] = set()
    for integration_id in sorted(set(sources) | set(records)):
        if integration_id in hidden:
            continue
        source = sources.get(integration_id)
        record = records.get(integration_id)
        if source is not None and source.transport.value == "native" and record is None:
            continue
        default = _default_view(integration_id, record=record, source=source)
        views.append(default)
        seen.add(default.id)
        if source is not None:
            for view in _oauth_views(source):
                if view.id not in seen:
                    views.append(view)
                    seen.add(view.id)
    views.sort(key=lambda item: (item.integration, item.origin != "env", item.id))
    return views


def get_connection_view(connection_id: str) -> ConnectionView | None:
    wanted = (connection_id or "").strip()
    if not wanted:
        return None
    for view in list_connection_views():
        if view.id == wanted:
            return view
    integration, suffix = parse_connection_id(wanted)
    if suffix == "default":
        record = get_connector(integration)
        source = next((item for item in visible_tool_sources() if item.name == integration), None)
        if record is None and source is None:
            return None
        return _default_view(integration, record=record, source=source)
    return None


def integration_manifest(integration_id: str) -> IntegrationManifest | None:
    """Build a secret-free integration manifest from the live catalog."""
    wanted = (integration_id or "").strip()
    if not wanted:
        return None
    record = get_connector(wanted)
    source = next((item for item in visible_tool_sources() if item.name == wanted), None)
    if record is None and source is None:
        return None
    views = [view for view in list_connection_views() if view.integration == wanted]
    if record is not None:
        actions = tuple(capability.id for capability in record.capabilities)
        transport = record.transport.kind
        auth_kind = record.auth_binding.kind.value
    else:
        actions = ()
        transport = source.transport.value if source is not None else ""
        if source is not None and source.oauth:
            auth_kind = "oauth"
        elif source is not None and source.env:
            auth_kind = "env"
        else:
            auth_kind = "none"
    return IntegrationManifest(
        id=wanted,
        toolkit=wanted,
        transport=transport,
        auth_kind=auth_kind,
        actions=actions,
        connections=tuple(view.id for view in views) or (default_connection_id(wanted),),
    )


def resolve_integration_id(connection_id: str | None, *, fallback: str | None = None) -> str:
    if connection_id:
        integration, _suffix = parse_connection_id(connection_id)
        return integration
    if fallback:
        return fallback
    raise ValueError("connection or integration is required")
