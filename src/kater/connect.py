"""Catalog Connect: per-server account connections (multi-account OAuth).

One ToolSource can hold several provider accounts (two Slack workspaces,
two Azure tenants). Tokens stay in gitignored settings; the API never
echoes values.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

from kater.profiles import OAuthConnectConfig, ToolSource
from kater.settings import KaterSettings, ServerConnection, ServerOverride, load_settings


def oauth_env_keys(oauth: OAuthConnectConfig) -> set[str]:
    keys = {oauth.client_id_env, oauth.token_env}
    if oauth.client_secret_env:
        keys.add(oauth.client_secret_env)
    if oauth.refresh_env:
        keys.add(oauth.refresh_env)
    return {k for k in keys if k}


def declared_credential_keys(source: ToolSource) -> set[str]:
    keys = set(source.env)
    if source.oauth:
        keys |= oauth_env_keys(source.oauth)
    return keys


def _env_satisfies(source: ToolSource, env: dict[str, str]) -> bool:
    if source.oauth and env.get(source.oauth.token_env):
        return True
    if source.env:
        return all(env.get(var) or os.environ.get(var) for var in source.env)
    return False


def list_connections(
    source: ToolSource, settings: KaterSettings | None = None
) -> list[ServerConnection]:
    settings = settings or load_settings()
    override = settings.server_overrides.get(source.name)
    if not override:
        return []
    if override.connections:
        return list(override.connections)
    if override.env and _env_satisfies(source, override.env):
        return [
            ServerConnection(
                id="legacy",
                label="saved credentials",
                env=dict(override.env),
                created_at=0.0,
            )
        ]
    return []


def source_is_configured(source: ToolSource, settings: KaterSettings | None = None) -> bool:
    settings = settings or load_settings()
    for conn in list_connections(source, settings):
        if _env_satisfies(source, conn.env):
            return True
    if source.oauth and os.environ.get(source.oauth.token_env):
        return True
    if source.env:
        return all(os.environ.get(var) for var in source.env)
    return True


def oauth_client_configured(source: ToolSource, settings: KaterSettings | None = None) -> bool:
    if not source.oauth:
        return False
    settings = settings or load_settings()
    override = settings.server_overrides.get(source.name)
    stored = dict(override.env) if override else {}
    client_id = stored.get(source.oauth.client_id_env) or os.environ.get(source.oauth.client_id_env)
    return bool(client_id)


def resolve_oauth_client(
    source: ToolSource, settings: KaterSettings | None = None
) -> tuple[str, str]:
    """Return (client_id, client_secret) for outbound OAuth. Secret may be empty."""
    if not source.oauth:
        return "", ""
    settings = settings or load_settings()
    override = settings.server_overrides.get(source.name)
    stored = dict(override.env) if override else {}
    client_id = (
        stored.get(source.oauth.client_id_env) or os.environ.get(source.oauth.client_id_env) or ""
    ).strip()
    secret = ""
    if source.oauth.client_secret_env:
        secret = (
            stored.get(source.oauth.client_secret_env)
            or os.environ.get(source.oauth.client_secret_env)
            or ""
        ).strip()
    return client_id, secret


def public_oauth(
    source: ToolSource, settings: KaterSettings | None = None
) -> dict[str, Any] | None:
    if not source.oauth:
        return None
    settings = settings or load_settings()
    connections = []
    for conn in list_connections(source, settings):
        if not _env_satisfies(source, conn.env):
            continue
        connections.append(
            {
                "id": conn.id,
                "label": (
                    conn.label or conn.extra.get("team") or conn.extra.get("tenant") or conn.id
                ),
                "created_at": conn.created_at,
            }
        )
    return {
        "provider": source.oauth.provider,
        "client_configured": oauth_client_configured(source, settings),
        "token_env": source.oauth.token_env,
        "connections": connections,
    }


def add_connection(
    settings: KaterSettings,
    name: str,
    env: dict[str, str],
    *,
    label: str = "",
    extra: dict[str, Any] | None = None,
) -> ServerConnection:
    conn = ServerConnection(
        id=secrets.token_hex(8),
        label=label.strip(),
        env={k: v for k, v in env.items() if str(v).strip()},
        extra=dict(extra or {}),
        created_at=time.time(),
    )
    override = settings.server_overrides.get(name) or ServerOverride()
    override.connections = list(override.connections)
    override.connections.append(conn)
    if not override.env:
        override.env = dict(conn.env)
    settings.server_overrides[name] = override
    return conn


def remove_connection(settings: KaterSettings, name: str, conn_id: str) -> bool:
    override = settings.server_overrides.get(name)
    if not override:
        return False
    before = len(override.connections)
    override.connections = [c for c in override.connections if c.id != conn_id]
    if len(override.connections) == before:
        if conn_id == "legacy" and override.env:
            override.env = {}
            return True
        return False
    if override.connections:
        override.env = dict(override.connections[0].env)
    else:
        override.env = {}
    return True


def launch_instances(
    source: ToolSource, settings: KaterSettings | None = None
) -> list[tuple[str, dict[str, str]]]:
    """Backend name + env overlay for each connected account."""
    settings = settings or load_settings()
    conns = [c for c in list_connections(source, settings) if _env_satisfies(source, c.env)]
    if not conns:
        env: dict[str, str] = {}
        for var in source.env:
            val = os.environ.get(var)
            if val:
                env[var] = val
        if source.oauth:
            token = os.environ.get(source.oauth.token_env)
            if token:
                env[source.oauth.token_env] = token
        if env and _env_satisfies(source, env):
            conns = [ServerConnection(id="env", env=env)]
    out: list[tuple[str, dict[str, str]]] = []
    for index, conn in enumerate(conns):
        backend = source.name if index == 0 else f"{source.name}__{conn.id}"
        merged = dict(conn.env)
        if source.oauth:
            client_id, client_secret = resolve_oauth_client(source, settings)
            if client_id:
                merged.setdefault(source.oauth.client_id_env, client_id)
            if client_secret and source.oauth.client_secret_env:
                merged.setdefault(source.oauth.client_secret_env, client_secret)
        out.append((backend, merged))
    return out
