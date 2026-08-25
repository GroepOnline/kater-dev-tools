"""Seed builtin ToolSources as persistent connectors (does not mutate profiles.py)."""

from __future__ import annotations

import os
from dataclasses import replace

from kater.connectors.auth import binding_is_satisfied
from kater.connectors.models import (
    AuthBindingRef,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
    PermissionLevel,
)
from kater.connectors.store import get_connector, upsert_connector
from kater.profiles import ToolSource, Transport, all_tool_sources

_IN_SCOPE = frozenset({"github", "linear", "sentry", "cloudflare"})
_OUT_OF_SCOPE = frozenset({"gitlab", "upstash", "slack", "postgres", "notion"})

_BUILTIN_CAPABILITIES: dict[str, tuple[ConnectorCapability, ...]] = {
    "github": (
        ConnectorCapability(id="github.repo.read", description="Read repository metadata"),
        ConnectorCapability(id="github.issues.read", description="Read GitHub issues"),
        ConnectorCapability(
            id="github.issues.write",
            description="Create or update GitHub issues",
            mutation=True,
        ),
        ConnectorCapability(id="github.pull_requests.read", description="Read pull requests"),
        ConnectorCapability(
            id="github.pull_requests.write",
            description="Create or update pull requests",
            mutation=True,
        ),
    ),
    "linear": (
        ConnectorCapability(id="linear.issues.read", description="Read Linear issues"),
        ConnectorCapability(
            id="linear.issues.write",
            description="Create or update Linear issues",
            mutation=True,
        ),
        ConnectorCapability(id="linear.projects.read", description="Read Linear projects"),
    ),
    "sentry": (
        ConnectorCapability(id="sentry.issues.read", description="Read Sentry issues"),
        ConnectorCapability(id="sentry.events.read", description="Read Sentry events"),
        ConnectorCapability(id="sentry.releases.read", description="Read Sentry releases"),
    ),
    "cloudflare": (
        ConnectorCapability(id="cloudflare.workers.read", description="Read Workers"),
        ConnectorCapability(
            id="cloudflare.workers.write",
            description="Deploy or update Workers",
            mutation=True,
        ),
        ConnectorCapability(id="cloudflare.dns.read", description="Read DNS records"),
        ConnectorCapability(
            id="cloudflare.dns.write",
            description="Update DNS records",
            mutation=True,
        ),
    ),
}


def _connector_type(source: ToolSource) -> ConnectorType:
    if source.transport is Transport.NATIVE:
        return ConnectorType.INTERNAL
    return ConnectorType.MCP


def _transport_from_source(source: ToolSource) -> ConnectorTransport:
    if source.transport is Transport.NATIVE:
        return ConnectorTransport(kind="native")
    if not source.mcp:
        raise ValueError(f"MCP source {source.name!r} missing mcp config")
    if source.transport is Transport.STDIO:
        return ConnectorTransport(
            kind="stdio",
            command=source.mcp.command or "",
            args=tuple(source.mcp.args),
            env_template=dict(source.mcp.env_template),
            headers_template=dict(source.mcp.headers_template),
        )
    url = source.mcp.url or ""
    kind = "http" if source.transport is Transport.HTTP else "sse"
    return ConnectorTransport(
        kind=kind,
        endpoint=url,
        headers_template=dict(source.mcp.headers_template),
        env_template=dict(source.mcp.env_template),
    )


def _permissions_for(name: str, *, env_ok: bool) -> dict[str, PermissionLevel]:
    if name in _OUT_OF_SCOPE:
        return {"ops": PermissionLevel.DISABLED}
    if not env_ok:
        return {}
    if name == "sentry":
        return {
            "ops": PermissionLevel.READ,
            "analysis": PermissionLevel.READ,
            "code": PermissionLevel.READ,
        }
    if name in _IN_SCOPE:
        return {
            "ops": PermissionLevel.WRITE,
            "analysis": PermissionLevel.READ,
            "code": PermissionLevel.READ,
        }
    return {}


def _status_for(name: str, *, env_ok: bool) -> ConnectorStatus:
    if name in _OUT_OF_SCOPE:
        return ConnectorStatus.DISABLED
    if name in _IN_SCOPE and env_ok:
        return ConnectorStatus.ENABLED
    return ConnectorStatus.DISABLED


def _metadata_for(name: str) -> dict[str, str]:
    if name in _OUT_OF_SCOPE:
        return {"scope": "out_of_scope"}
    return {}


def _record_from_source(source: ToolSource) -> ConnectorRecord:
    auth_binding = AuthBindingRef.from_env_names(source.env)
    env_ok = binding_is_satisfied(auth_binding, connector_id=source.name)
    caps = _BUILTIN_CAPABILITIES.get(source.name, ())
    profiles = frozenset(source.profiles)
    if source.name in _IN_SCOPE:
        profiles = frozenset(set(source.profiles) | {"analysis", "code"})
    return ConnectorRecord(
        id=source.name,
        display_name=source.name,
        type=_connector_type(source),
        version="1.0.0",
        transport=_transport_from_source(source),
        capabilities=caps,
        auth_binding=auth_binding,
        profiles=profiles,
        permissions=_permissions_for(source.name, env_ok=env_ok),
        status=_status_for(source.name, env_ok=env_ok),
        metadata=_metadata_for(source.name),
        origin="seed",
    )


def _clickhouse_proof_record() -> ConnectorRecord:
    url = os.environ.get("CLICKHOUSE_URL", "").strip()
    has_runtime = bool(url)
    return ConnectorRecord(
        id="clickhouse",
        display_name="ClickHouse",
        type=ConnectorType.API,
        version="1.0.0",
        transport=ConnectorTransport(
            kind="http",
            endpoint=url or "http://127.0.0.1:8123",
        ),
        capabilities=(
            ConnectorCapability(id="clickhouse.ping", description="HTTP ping"),
            ConnectorCapability(id="clickhouse.query", description="HTTP query"),
        ),
        auth_binding=AuthBindingRef.from_env_names(
            ["CLICKHOUSE_TOKEN"] if has_runtime else []
        ),
        profiles=frozenset({"ops", "cloud"}),
        permissions={"ops": PermissionLevel.DISABLED, "cloud": PermissionLevel.DISABLED},
        status=ConnectorStatus.DISABLED,
        metadata={
            "shape": "clickhouse",
            "scope": "proof",
            "unsupported_runtime": not has_runtime,
        },
        origin="seed",
    )


def _upsert_seed(record: ConnectorRecord) -> None:
    existing = get_connector(record.id)
    if existing is None:
        upsert_connector(record)
        return
    if existing.origin != "seed":
        return
    # Preserve operator intent: once a connector has been explicitly enabled or
    # disabled via the registry, keep its status/permissions on re-seed. Rows the
    # operator never touched are recomputed from the current env so adding an env
    # var later can enable the connector without a manual step.
    if existing.metadata.get("operator_managed") is True:
        upsert_connector(
            replace(
                record,
                status=existing.status,
                permissions=existing.permissions,
                profiles=existing.profiles or record.profiles,
                metadata={**record.metadata, "operator_managed": True},
            )
        )
        return
    if existing.status is ConnectorStatus.VALIDATED:
        # Validation is lifecycle progress, not derived seed state. Keep the discovered
        # capability contract and validated status across startup/doctor reseeds while
        # still allowing untouched env-derived permissions to be recomputed.
        upsert_connector(
            replace(
                record,
                status=ConnectorStatus.VALIDATED,
                capabilities=existing.capabilities,
                profiles=existing.profiles or record.profiles,
            )
        )
        return
    upsert_connector(
        replace(
            record,
            profiles=existing.profiles or record.profiles,
        )
    )


_SEEDED_SOURCES = _IN_SCOPE | _OUT_OF_SCOPE


def seed_builtin_connectors() -> int:
    count = 0
    for source in all_tool_sources():
        if source.name not in _SEEDED_SOURCES:
            continue
        if source.transport is Transport.NATIVE:
            continue
        _upsert_seed(_record_from_source(source))
        count += 1
    _upsert_seed(_clickhouse_proof_record())
    count += 1
    return count
