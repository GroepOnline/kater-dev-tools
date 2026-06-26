from __future__ import annotations

import json
import os
import time
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
    api_port: int = 9091
    mcp_port: int = 9090
    storage_backend: str = "sqlite"
    db_path: str = ".kater/kater.db"
    body_size_limit: int = 1048576
    high_risk_default_disabled: bool = True

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

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_safe_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        if "api_keys" in d.get("auth", {}):
            keys = d["auth"]["api_keys"]
            d["auth"]["api_keys"] = len(keys) if keys else 0
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KaterSettings:
        return cls.model_validate(data)


SETTINGS_FILE = "settings.json"


def settings_path(project_dir: Path | None = None) -> Path:
    project_dir = project_dir or Path.cwd()
    return project_dir / ".kater" / SETTINGS_FILE


def load_settings(project_dir: Path | None = None) -> KaterSettings:
    path = settings_path(project_dir)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return KaterSettings.from_dict(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return _settings_from_env()


def save_settings(settings: KaterSettings, project_dir: Path | None = None) -> Path:
    path = settings_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _settings_from_env() -> KaterSettings:
    host = os.environ.get("KATER_HOST", "127.0.0.1")
    is_public = host not in ("127.0.0.1", "localhost", "::1")

    auth_mode = os.environ.get("KATER_AUTH_MODE", "")
    if not auth_mode:
        auth_mode = "apikey" if is_public else "none"

    auth = AuthConfig(mode=auth_mode)

    if auth_mode == "apikey":
        keys_raw = os.environ.get("KATER_API_KEYS", "")
        api_keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
        if not api_keys:
            single = os.environ.get("KATER_API_KEY", "")
            if single:
                api_keys = [single]
        if is_public and not api_keys:
            api_keys = [_generate_default_key()]
        auth = AuthConfig(mode="apikey", api_keys=api_keys)
    elif auth_mode == "oauth":
        auth = AuthConfig(
            mode="oauth",
            oauth_issuer=os.environ.get("KATER_OAUTH_ISSUER"),
            oauth_audience=os.environ.get("KATER_OAUTH_AUDIENCE"),
            oauth_jwks_url=os.environ.get("KATER_OAUTH_JWKS_URL"),
        )

    cors_raw = os.environ.get("KATER_CORS_ORIGINS", "")
    if cors_raw:
        cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
    else:
        cors_origins = ["http://localhost:9091"] if is_public else ["*"]

    rate_limit = int(os.environ.get("KATER_RATE_LIMIT", "60" if is_public else "0"))

    return KaterSettings(
        auth=auth,
        cors_origins=cors_origins,
        rate_limit_per_min=rate_limit,
        api_port=int(os.environ.get("KATER_API_PORT", "9091")),
        mcp_port=int(os.environ.get("KATER_MCP_PORT", "9090")),
    )


def _generate_default_key() -> str:
    import secrets as _secrets
    return f"kat_{_secrets.token_hex(16)}"


# ── Auth helpers ───────────────────────────────────────────────────


def check_auth(
    settings: KaterSettings,
    authorization_header: str | None,
    query_api_key: str | None,
) -> tuple[bool, str | None]:
    if settings.auth.mode == "none":
        return True, None

    if settings.auth.mode == "apikey":
        token = _extract_bearer(authorization_header) or query_api_key
        if not token:
            return False, (
                "Missing API key. Use Authorization: Bearer <key>"
                " or ?api_key=<key>."
            )
        if token in settings.auth.api_keys:
            return True, None
        return False, "Invalid API key."

    if settings.auth.mode == "oauth":
        token = _extract_bearer(authorization_header)
        if not token:
            return False, "Missing bearer token."
        from kater.oauth import validate_token

        at = validate_token(token)
        if at and at.is_valid():
            return True, None
        return False, "Invalid or expired token."

    return True, None


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

    def check(self, client_id: str) -> bool:
        if self.max_per_min <= 0:
            return True
        now = time.time()
        window = 60.0
        hits = self._hits.get(client_id, [])
        hits = [t for t in hits if now - t < window]
        if len(hits) >= self.max_per_min:
            return False
        hits.append(now)
        self._hits[client_id] = hits
        return True
