from __future__ import annotations

import ipaddress
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    mode: str = "none"  # none | apikey | oauth
    api_keys: list[str] = Field(default_factory=list)
    oauth_issuer: str | None = None
    oauth_audience: str | None = None
    oauth_jwks_url: str | None = None


class ServerOverride(BaseModel):
    enabled: bool | None = None
    env: dict[str, str] = Field(default_factory=dict)
    args_override: list[str] | None = None
    url_override: str | None = None


class KaterSettings(BaseModel):
    version: int = 2
    default_profile: str = "core"
    auth: AuthConfig = Field(default_factory=AuthConfig)
    server_overrides: dict[str, ServerOverride] = Field(default_factory=dict)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit_per_min: int = 0
    host: str = "127.0.0.1"
    api_port: int = 9091
    mcp_port: int = 9090
    ws_port: int = 9092
    storage_backend: str = "sqlite"
    db_path: str = ".kater/kater.db"
    body_size_limit: int = 1048576
    high_risk_default_disabled: bool = True
    # Proxy circuit-breaker tuning (magic numbers were previously hardcoded).
    proxy_failure_threshold: int = 5
    proxy_recovery_timeout: float = 30.0

    def is_server_enabled(self, name: str, default: bool = True) -> bool:
        override = self.server_overrides.get(name)
        if override and override.enabled is not None:
            return override.enabled
        return default

    def set_server_enabled(self, name: str, enabled: bool) -> None:
        if name not in self.server_overrides:
            self.server_overrides[name] = ServerOverride()
        self.server_overrides[name].enabled = enabled

    def get_server_env(self, name: str) -> dict[str, str]:
        override = self.server_overrides.get(name)
        if override:
            return override.env
        return {}

    def apply_credentials_to_env(self) -> None:
        """Load persisted per-server credentials into the process environment.

        Externally-provided env (e.g. systemd/secret managers) always wins, so
        we only fill gaps — that way an operator can override a dashboard-set
        value from the outside without it being clobbered on restart.
        """
        for override in self.server_overrides.values():
            for key, value in (override.env or {}).items():
                if value:
                    os.environ.setdefault(key, value)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_safe_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        if "api_keys" in d.get("auth", {}):
            keys = d["auth"]["api_keys"]
            d["auth"]["api_keys"] = len(keys) if keys else 0
        # Stored MCP server credentials must never be echoed back over the API.
        # Keep the var names (so the UI knows what's set) but mask the values.
        for override in d.get("server_overrides", {}).values():
            env = override.get("env")
            if env:
                override["env"] = {key: "***" for key in env}
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KaterSettings:
        return cls.model_validate(data)


SETTINGS_FILE = "settings.json"

# Per-project settings cache (cwd-resolved key). Bounded to one entry in
# practice; a dict keeps it explicit and easy to invalidate.
_settings_cache: dict[str, KaterSettings] = {}


def settings_path(project_dir: Path | None = None) -> Path:
    project_dir = project_dir or Path.cwd()
    return project_dir / ".kater" / SETTINGS_FILE


def load_settings(project_dir: Path | None = None) -> KaterSettings:
    # In-process cache: the hot path (every HTTP request) used to re-read and
    # re-parse settings.json on each call. Invalidation happens in save_settings.
    cache_key = str((project_dir or Path.cwd()).resolve())
    cached = _settings_cache.get(cache_key)
    if cached is not None:
        return cached
    path = settings_path(project_dir)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            settings = KaterSettings.from_dict(data)
        except (json.JSONDecodeError, ValueError):
            settings = _settings_from_env()
    else:
        settings = _settings_from_env()
    settings = _apply_env_security_overrides(settings)
    _settings_cache[cache_key] = settings
    return settings


def invalidate_settings_cache(project_dir: Path | None = None) -> None:
    """Drop the cached settings so the next load re-reads from disk/env."""
    if project_dir is not None:
        _settings_cache.pop(str(project_dir.resolve()), None)
    else:
        _settings_cache.clear()


def _apply_env_security_overrides(settings: KaterSettings) -> KaterSettings:
    """Env wins for security-sensitive fields on public deployments."""
    host = os.environ.get("KATER_HOST", settings.host)
    if not _is_public_deploy(host):
        return settings

    auth_mode = os.environ.get("KATER_AUTH_MODE", "").strip()
    if auth_mode:
        settings.auth.mode = auth_mode
        if auth_mode == "apikey":
            keys_raw = os.environ.get("KATER_API_KEYS", "")
            api_keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
            if not api_keys:
                single = os.environ.get("KATER_API_KEY", "")
                if single:
                    api_keys = [single]
            if api_keys:
                settings.auth.api_keys = api_keys
        elif auth_mode == "oauth":
            settings.auth.oauth_issuer = os.environ.get(
                "KATER_OAUTH_ISSUER", settings.auth.oauth_issuer
            )
            settings.auth.oauth_audience = os.environ.get(
                "KATER_OAUTH_AUDIENCE", settings.auth.oauth_audience
            )

    rate_raw = os.environ.get("KATER_RATE_LIMIT", "").strip()
    if rate_raw:
        try:
            settings.rate_limit_per_min = int(rate_raw)
        except ValueError:
            pass  # Ignore invalid values; keep the default.

    cors_raw = os.environ.get("KATER_CORS_ORIGINS", "").strip()
    if cors_raw:
        settings.cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

    settings.host = host
    return settings


# Thread-safety: a single lock serialises read-modify-write sequences so
# concurrent API requests cannot overwrite each other's changes, and an
# atomic write (tmp + replace) prevents corruption on crash.

_settings_lock = threading.Lock()


def save_settings(settings: KaterSettings, project_dir: Path | None = None) -> Path:
    path = settings_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    with _settings_lock:
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{threading.get_ident()}")
        tmp.write_text(
            json.dumps(settings.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp.chmod(0o600)
        os.replace(tmp, path)
    # Drop the cache so the next load_settings() reflects the new on-disk state.
    invalidate_settings_cache(project_dir)
    return path


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_public_deploy(host: str) -> bool:
    """True when Kater is reachable beyond localhost (direct bind or via tunnel).

    Cloudflare Tunnel and reverse proxies bind to loopback but expose the
    service publicly — ``KATER_PUBLIC=1`` opts into secure defaults in that case.
    """
    if _env_truthy("KATER_PUBLIC"):
        return True
    return host not in ("127.0.0.1", "localhost", "::1")


def is_public_settings(settings: KaterSettings) -> bool:
    return _is_public_deploy(os.environ.get("KATER_HOST", settings.host))


def unsafe_public_settings_override_enabled() -> bool:
    return _env_truthy("KATER_ALLOW_UNSAFE_PUBLIC_SETTINGS")


def allow_query_api_key(settings: KaterSettings) -> bool:
    return not is_public_settings(settings)


def _is_trusted_proxy_peer(peer_ip: str) -> bool:
    if _env_truthy("KATER_TRUST_PROXY"):
        return True
    try:
        ip = ipaddress.ip_address(peer_ip)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def resolve_client_ip(forwarded_for: str | None, client_address_ip: str) -> str:
    if forwarded_for and _is_trusted_proxy_peer(client_address_ip):
        return forwarded_for.split(",")[0].strip() or client_address_ip
    return client_address_ip


def _get_auth_from_env(is_public: bool) -> AuthConfig:
    auth_mode = os.environ.get("KATER_AUTH_MODE", "")
    if not auth_mode:
        auth_mode = "oauth" if is_public else "none"

    if auth_mode == "apikey":
        keys_raw = os.environ.get("KATER_API_KEYS", "")
        api_keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
        if not api_keys:
            single = os.environ.get("KATER_API_KEY", "")
            if single:
                api_keys = [single]
        if is_public and not api_keys:
            api_keys = [_generate_default_key()]
        return AuthConfig(mode="apikey", api_keys=api_keys)
    elif auth_mode == "oauth":
        return AuthConfig(
            mode="oauth",
            oauth_issuer=os.environ.get("KATER_OAUTH_ISSUER"),
            oauth_audience=os.environ.get("KATER_OAUTH_AUDIENCE"),
            oauth_jwks_url=os.environ.get("KATER_OAUTH_JWKS_URL"),
        )

    return AuthConfig(mode=auth_mode)


def _get_cors_from_env(is_public: bool) -> list[str]:
    cors_raw = os.environ.get("KATER_CORS_ORIGINS", "")
    if cors_raw:
        return [o.strip() for o in cors_raw.split(",") if o.strip()]
    return ["http://localhost:9091"] if is_public else ["*"]


def _safe_env_int(env_var: str, default: int) -> int:
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _settings_from_env() -> KaterSettings:
    host = os.environ.get("KATER_HOST", "127.0.0.1")
    is_public = _is_public_deploy(host)

    auth = _get_auth_from_env(is_public)
    cors_origins = _get_cors_from_env(is_public)
    rate_limit = _safe_env_int("KATER_RATE_LIMIT", 60 if is_public else 0)

    return KaterSettings(
        auth=auth,
        cors_origins=cors_origins,
        rate_limit_per_min=rate_limit,
        host=host,
        api_port=_safe_env_int("KATER_API_PORT", 9091),
        mcp_port=_safe_env_int("KATER_MCP_PORT", 9090),
        ws_port=_safe_env_int("KATER_WS_PORT", 9092),
    )


@dataclass(frozen=True)
class ListenConfig:
    """Single source of truth for where the three servers bind.

    One process binds one host with three ports (REST API, MCP SSE, WebSocket).
    Collapsing host/port handling here removes the literals that were scattered
    across cli, serve, api, mcp_server and websocket — and the footgun where
    different entrypoints defaulted to different hosts (0.0.0.0 vs 127.0.0.1).
    """

    host: str = "127.0.0.1"
    api_port: int = 9091
    mcp_port: int = 9090
    ws_port: int = 9092


def resolve_listen_config(
    *,
    host: str | None = None,
    api_port: int | None = None,
    mcp_port: int | None = None,
    ws_port: int | None = None,
    settings: KaterSettings | None = None,
) -> ListenConfig:
    """Merge explicit overrides over persisted/env settings.

    Precedence: explicit argument > settings (file or env-derived) > default.
    """
    settings = settings or load_settings()
    return ListenConfig(
        host=host if host is not None else settings.host,
        api_port=api_port if api_port is not None else settings.api_port,
        mcp_port=mcp_port if mcp_port is not None else settings.mcp_port,
        ws_port=ws_port if ws_port is not None else settings.ws_port,
    )


def _generate_default_key() -> str:
    import secrets as _secrets
    return f"kat_{_secrets.token_hex(16)}"


def check_admin(
    authorization_header: str | None,
    settings: KaterSettings | None = None,
) -> bool:
    """True if the caller holds the operator/admin credential.

    Operators set ``KATER_ADMIN_KEY`` to separate "use tools" from "change
    settings". When unset, every authenticated caller is treated as admin
    (single-user local default). When set, sensitive settings mutations
    (auth mode, api_keys, CORS, rate limit) require this key, so a leaked
    tool-credential cannot weaken the gateway.
    """
    admin_key = os.environ.get("KATER_ADMIN_KEY", "")
    if not admin_key:
        if settings is not None and is_public_settings(settings):
            return False
        return True
    token = _extract_bearer(authorization_header)
    if not token:
        return False
    return secrets.compare_digest(token, admin_key)


# ── Auth helpers ───────────────────────────────────────────────────


def check_auth(
    settings: KaterSettings,
    authorization_header: str | None,
    query_api_key: str | None,
) -> tuple[bool, str | None]:
    if settings.auth.mode == "none":
        return True, None

    if settings.auth.mode == "apikey":
        token = _extract_bearer(authorization_header)
        if not token and allow_query_api_key(settings):
            token = query_api_key
        if not token:
            return False, (
                "Missing API key. Use Authorization: Bearer <key>."
            )
        for key in settings.auth.api_keys:
            if secrets.compare_digest(token, key):
                return True, None
        return False, "Invalid API key."

    if settings.auth.mode == "oauth":
        token = _extract_bearer(authorization_header)
        if not token:
            return False, "Missing bearer token."
        dashboard_key = os.environ.get("KATER_DASHBOARD_KEY", "")
        if dashboard_key and token and secrets.compare_digest(token, dashboard_key):
            return True, None
        from kater.oauth import validate_token

        at = validate_token(token)
        if at and at.is_valid():
            return True, None
        return False, "Invalid or expired token."

    return False, "Unsupported auth mode."


def cors_allow_origin(
    settings: KaterSettings,
    request_origin: str | None,
) -> str | None:
    if not settings.cors_origins or "*" in settings.cors_origins:
        return request_origin or "*"
    if request_origin and request_origin in settings.cors_origins:
        return request_origin
    return None


def _extract_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


# ── Rate limiter ───────────────────────────────────────────────────


class RateLimiter:
    def __init__(self, max_per_min: int) -> None:
        self.max_per_min = max_per_min
        self._hits: dict[str, list[float]] = {}
        self._check_count = 0
        self._lock = threading.Lock()

    def check(self, client_id: str) -> bool:
        if self.max_per_min <= 0:
            return True
        now = time.time()
        window = 60.0
        with self._lock:
            hits = [t for t in self._hits.get(client_id, []) if now - t < window]
            if len(hits) >= self.max_per_min:
                self._hits[client_id] = hits
                return False
            hits.append(now)
            self._hits[client_id] = hits
            self._check_count += 1
            if len(self._hits) > 500 and self._check_count % 500 == 0:
                self._evict_idle(now, window)
            return True

    def _evict_idle(self, now: float, window: float) -> None:
        idle = [c for c, ts in self._hits.items() if not ts or now - ts[-1] >= window]
        for c in idle:
            del self._hits[c]
