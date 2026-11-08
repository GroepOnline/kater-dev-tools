"""Opt-in Auth introspection for the dedicated product transport.

Auth POST /v1/introspect accepts JSON {token, resource}, authenticated with a
resource-specific service key. Its active response has sub, plane, scope, aud,
and exp (Unix seconds). Issuer trust comes from the configured HTTPS endpoint;
the proven Auth contract does not include an iss claim. No token is cached.
"""

from __future__ import annotations

import json
import math
import os
import re
import ssl
import time
from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
from typing import Literal, Self
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator

_SCOPE = re.compile(r"[\x21\x23-\x5b\x5d-\x7e]+")
_OPAQUE = re.compile(r"[\x21-\x7e]+")
_MAX_RESPONSE_BYTES = 16384


def _validate_https_url(value: str, *, origin_only: bool = False) -> None:
    parts = urlsplit(value)
    if (
        not value.startswith("https://")
        or not _OPAQUE.fullmatch(value)
        or any(char in value for char in ("\\", "?", "#"))
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.netloc != parts.netloc.lower()
        or any(segment in {".", ".."} for segment in unquote(parts.path).split("/"))
        or (origin_only and parts.path)
    ):
        raise ValueError("Expected an exact HTTPS URL without credentials, query or fragment")
    # Accessing port also rejects malformed and out-of-range ports.
    if parts.port == 0:
        raise ValueError("HTTPS port must be positive")


class ResourceAuthConfig(BaseModel):
    """Explicit resource contract. Store only the service key's environment name."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: StrictBool = False
    issuer: str = ""
    resource: str = ""
    allowed_scopes: tuple[str, ...] = ()
    service_key_env: str = Field(
        default="KATER_RESOURCE_AUTH_SERVICE_KEY", pattern=r"^[A-Z_][A-Z0-9_]*$"
    )
    timeout_seconds: float = Field(default=5.0, gt=0, le=30, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.issuer:
            _validate_https_url(self.issuer, origin_only=True)
        if self.resource:
            _validate_https_url(self.resource)
        if len(set(self.allowed_scopes)) != len(self.allowed_scopes) or any(
            not _SCOPE.fullmatch(scope) for scope in self.allowed_scopes
        ):
            raise ValueError("Resource scopes must be distinct OAuth scope tokens")
        if self.enabled and not (self.issuer and self.resource and self.allowed_scopes):
            raise ValueError("Enabled resource auth requires issuer, resource and allowed scopes")
        return self


@dataclass(frozen=True, slots=True)
class ResourcePrincipal:
    issuer: str
    subject: str
    audience: str
    plane: Literal["internal"]
    scopes: frozenset[str]
    expires_at: int


class ResourceAuthError(Exception):
    """Safe error for a future HTTP adapter; never includes credentials or claims."""

    status_code = 503
    code = "resource_auth_error"

    def __init__(self) -> None:
        super().__init__(self.code)


class ResourceAuthDisabled(ResourceAuthError):
    code = "resource_auth_disabled"


class ResourceAuthConfigurationError(ResourceAuthError):
    code = "resource_auth_configuration_error"


class AuthUnavailable(ResourceAuthError):
    code = "auth_unavailable"


class InvalidToken(ResourceAuthError):
    status_code = 401
    code = "invalid_token"


class InsufficientScope(ResourceAuthError):
    status_code = 403
    code = "insufficient_scope"


class _ActiveClaims(BaseModel):
    model_config = ConfigDict(strict=True)

    sub: str = Field(min_length=1, max_length=1024, pattern=r"^[^\s\x00-\x1f\x7f]+$")
    plane: Literal["internal"]
    scope: str
    aud: str
    exp: int = Field(gt=0)


def _require_enabled_contract(config: ResourceAuthConfig) -> None:
    if not config.enabled:
        raise ResourceAuthDisabled()


def _require_contract(config: ResourceAuthConfig, required_scopes: frozenset[str]) -> None:
    _require_enabled_contract(config)
    if not required_scopes or not required_scopes.issubset(config.allowed_scopes):
        raise ResourceAuthConfigurationError()


def _parse_active_introspection(
    payload: object,
    *,
    config: ResourceAuthConfig,
    now: float | None = None,
) -> ResourcePrincipal:
    """Validate active Auth claims without making a tool authorization decision."""
    _require_enabled_contract(config)
    if not isinstance(payload, dict) or payload.get("active") is not True:
        raise InvalidToken()
    try:
        claims = _ActiveClaims.model_validate(payload)
    except ValidationError:
        raise InvalidToken() from None
    current_time = time.time() if now is None else now
    if not math.isfinite(current_time):
        raise AuthUnavailable()
    if (
        claims.aud != config.resource
        or claims.exp <= current_time
        or ("iss" in payload and payload["iss"] != config.issuer)
    ):
        raise InvalidToken()
    scope_tokens = claims.scope.split(" ") if claims.scope else []
    scopes = frozenset(scope_tokens)
    if (
        any(not _SCOPE.fullmatch(scope) for scope in scope_tokens)
        or len(scopes) != len(scope_tokens)
        or not scopes.issubset(config.allowed_scopes)
    ):
        raise InvalidToken()
    return ResourcePrincipal(
        issuer=config.issuer,
        subject=claims.sub,
        audience=claims.aud,
        plane=claims.plane,
        scopes=scopes,
        expires_at=claims.exp,
    )


def parse_introspection(
    payload: object,
    *,
    config: ResourceAuthConfig,
    required_scopes: frozenset[str],
    now: float | None = None,
) -> ResourcePrincipal:
    """Validate the Auth response and authorize explicit resource scopes.

    Invalid/inactive claims map to 401; valid tokens missing required scopes map
    to 403. Any supplied iss extension must match exactly, though Auth omits it.
    """
    _require_contract(config, required_scopes)
    principal = _parse_active_introspection(payload, config=config, now=now)
    if not required_scopes.issubset(principal.scopes):
        raise InsufficientScope()
    return principal


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError("Non-finite JSON number")


class IntrospectionClient:
    """Synchronous, uncached validation. No redirects, retries or local fallback."""

    def __init__(self, config: ResourceAuthConfig) -> None:
        self._config = config

    def validate_configuration(self) -> None:
        """Validate secret presence without sending a request or exposing its value."""
        _require_enabled_contract(self._config)
        service_key = os.environ.get(self._config.service_key_env, "")
        if len(service_key) < 32 or not _OPAQUE.fullmatch(service_key):
            raise ResourceAuthConfigurationError()

    def _request(self, token: str) -> object:
        config = self._config
        _require_enabled_contract(config)
        if not token or len(token) > 8192 or not _OPAQUE.fullmatch(token):
            raise InvalidToken()
        self.validate_configuration()
        service_key = os.environ[config.service_key_env]
        issuer = urlsplit(config.issuer)
        connection: HTTPSConnection | None = None
        try:
            connection = HTTPSConnection(
                issuer.netloc,
                timeout=config.timeout_seconds,
                context=ssl.create_default_context(),
            )
            connection.request(
                "POST",
                "/v1/introspect",
                body=json.dumps({"token": token, "resource": config.resource}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                # A 401/403 here rejects Kater's service key, not the user's token.
                raise AuthUnavailable()
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise AuthUnavailable()
            body = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(body) > _MAX_RESPONSE_BYTES:
                raise AuthUnavailable()
            payload: object = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (OSError, HTTPException, ValueError, RecursionError):
            raise AuthUnavailable() from None
        finally:
            if connection is not None:
                connection.close()
        return payload

    def check_readiness(self) -> bool:
        """Require Auth's inactive-token response, never accept malformed active claims."""
        payload = self._request("kater-readiness-deliberately-invalid")
        return isinstance(payload, dict) and payload.get("active") is False

    def introspect(self, token: str) -> ResourcePrincipal:
        """Validate a bearer and return its bounded claims without choosing a tool.

        The MCP transport needs this distinction so its OAuth middleware can
        advertise all granted scopes and enforce each tool's scope separately.
        The token is still checked remotely on every HTTP request; no positive
        result is cached.
        """
        payload = self._request(token)
        return _parse_active_introspection(payload, config=self._config)

    def authenticate(self, token: str, *, required_scopes: frozenset[str]) -> ResourcePrincipal:
        _require_contract(self._config, required_scopes)
        payload = self._request(token)
        return parse_introspection(
            payload,
            config=self._config,
            required_scopes=required_scopes,
        )
