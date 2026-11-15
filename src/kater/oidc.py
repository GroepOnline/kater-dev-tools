"""Authentik / mesh Auth OIDC relying party (product login gate).

When ``AUTH_OIDC_ISSUER`` and ``AUTH_OIDC_CLIENT_ID`` are set, Kater prefers
Authentik over Cloudflare Access for browser login: ``/authorize`` redirects
to the IdP and ``/oidc/callback`` finishes the code flow, then issues a local
gateway auth code (existing ``/token`` PKCE exchange).

No client secrets belong in git. Discovery and token exchange use HTTPS
(or loopback HTTP for local mock IdPs). ID tokens are verified against the
discovered JWKS with RS256; issuer, audience, expiry, nonce and subject are
checked before granting a session.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import jwt

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_MAX_BODY = 65536
_HTTP_TIMEOUT = 10.0
_PENDING_TTL = 600.0
_MAX_PENDING = 256
_DISCOVERY_TTL = 60.0
_DEFAULT_SCOPES = ("openid",)

_OIDC_ENV_KEYS = (
    "AUTH_OIDC_ISSUER",
    "AUTH_OIDC_CLIENT_ID",
    "AUTH_OIDC_CLIENT_SECRET",
    "AUTH_OIDC_REDIRECT_URI",
    "AUTH_OIDC_SCOPES",
    "AUTH_OIDC_AUDIENCE",
)


class OidcError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.safe_message = message or code
        super().__init__(self.safe_message)


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    client_secret: str | None = None
    redirect_uri: str | None = None
    scopes: tuple[str, ...] = _DEFAULT_SCOPES
    audience: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.issuer and self.client_id)


@dataclass(frozen=True)
class OidcDiscovery:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str | None = None
    userinfo_endpoint: str | None = None
    end_session_endpoint: str | None = None
    scopes_supported: tuple[str, ...] = ()
    code_challenge_methods_supported: tuple[str, ...] = ()


@dataclass(frozen=True)
class PendingAuthorize:
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    scope: str
    state: str | None
    profile: str


@dataclass
class LoginSession:
    state: str
    nonce: str
    code_verifier: str
    callback_uri: str
    created_at: float
    pending: PendingAuthorize | None = None
    next_path: str = "/dashboard"
    browser_binding: str = ""
    consumed: bool = False


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str = ""


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> HttpResponse: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class StdlibTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> HttpResponse:
        if not _is_allowed_idp_url(url):
            raise OidcError("oidc_url_insecure")
        req = Request(url, data=body, method=method, headers=headers or {})  # noqa: S310 — scheme checked
        opener = build_opener(_NoRedirect())
        try:
            with opener.open(req, timeout=_HTTP_TIMEOUT) as resp:
                raw = resp.read(_MAX_BODY + 1)
                if len(raw) > _MAX_BODY:
                    raise OidcError("oidc_response_too_large")
                return HttpResponse(
                    status=int(getattr(resp, "status", 200)),
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    body=raw,
                    url=str(resp.geturl()),
                )
        except HTTPError as exc:
            raw = exc.read(_MAX_BODY) if exc.fp else b""
            return HttpResponse(
                status=int(exc.code),
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                body=raw,
                url=url,
            )
        except URLError as exc:
            raise OidcError("oidc_unreachable", "IdP request failed") from exc


_transport: HttpTransport = StdlibTransport()
_pending: dict[str, LoginSession] = {}
_pending_lock = threading.Lock()
_discovery_cache: dict[str, tuple[float, OidcDiscovery]] = {}
_discovery_lock = threading.Lock()


def set_transport(transport: HttpTransport | None) -> None:
    global _transport
    _transport = transport or StdlibTransport()


def reset_oidc_state() -> None:
    with _pending_lock:
        _pending.clear()
    with _discovery_lock:
        _discovery_cache.clear()


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def any_oidc_env_set() -> bool:
    return any(_env(key) for key in _OIDC_ENV_KEYS)


def load_oidc_config() -> OidcConfig:
    scopes_raw = _env("AUTH_OIDC_SCOPES")
    scopes = tuple(scopes_raw.split()) if scopes_raw else _DEFAULT_SCOPES
    return OidcConfig(
        issuer=_env("AUTH_OIDC_ISSUER"),
        client_id=_env("AUTH_OIDC_CLIENT_ID"),
        client_secret=_env("AUTH_OIDC_CLIENT_SECRET") or None,
        redirect_uri=_env("AUTH_OIDC_REDIRECT_URI") or None,
        scopes=scopes,
        audience=_env("AUTH_OIDC_AUDIENCE") or None,
    )


def oidc_enabled(config: OidcConfig | None = None) -> bool:
    return (config or load_oidc_config()).enabled


def oidc_partial(config: OidcConfig | None = None) -> bool:
    cfg = config or load_oidc_config()
    return any_oidc_env_set() and not cfg.enabled


def oidc_public_status(config: OidcConfig | None = None) -> dict[str, Any]:
    cfg = config or load_oidc_config()
    return {
        "enabled": cfg.enabled,
        "issuer": cfg.issuer or None,
        "client_id": cfg.client_id or None,
        "redirect_uri": cfg.redirect_uri or None,
        "scopes": list(cfg.scopes),
        "partial": oidc_partial(cfg),
        "gate": "authentik" if cfg.enabled else "local_or_access",
    }


def discovery_url(issuer: str) -> str:
    value = issuer.strip()
    if not value:
        raise OidcError("oidc_issuer_missing")
    if value.endswith("/.well-known/openid-configuration"):
        return value
    return value.rstrip("/") + "/.well-known/openid-configuration"


def _is_allowed_idp_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and host:
        return True
    return parsed.scheme == "http" and host in _LOOPBACK_HOSTS


def resolve_callback_uri(req_base_url: str, *, public: bool) -> str:
    cfg = load_oidc_config()
    if cfg.redirect_uri:
        if not _is_allowed_callback(cfg.redirect_uri):
            raise OidcError("oidc_redirect_invalid")
        return cfg.redirect_uri
    if public:
        raise OidcError(
            "oidc_redirect_unconfigured",
            "Set AUTH_OIDC_REDIRECT_URI for public deploys",
        )
    parsed = urlparse(req_base_url)
    if (parsed.hostname or "") not in _LOOPBACK_HOSTS:
        raise OidcError("oidc_redirect_unconfigured")
    return req_base_url.rstrip("/") + "/oidc/callback"


def _is_allowed_callback(uri: str) -> bool:
    try:
        parsed = urlparse(uri)
    except (ValueError, TypeError):
        return False
    if parsed.path.rstrip("/") != "/oidc/callback":
        return False
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and (parsed.hostname or "") in _LOOPBACK_HOSTS


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _normalize_issuer(value: str) -> str:
    return value.rstrip("/") + "/"


def discover(issuer: str, transport: HttpTransport | None = None) -> OidcDiscovery:
    url = discovery_url(issuer)
    if not _is_allowed_idp_url(url):
        raise OidcError("oidc_issuer_insecure")
    now = time.time()
    with _discovery_lock:
        cached = _discovery_cache.get(url)
        if cached and now - cached[0] < _DISCOVERY_TTL:
            return cached[1]
    client = transport or _transport
    resp = client.request("GET", url, headers={"Accept": "application/json"})
    if resp.status != 200:
        raise OidcError("oidc_discovery_failed", f"discovery HTTP {resp.status}")
    try:
        payload = json.loads(resp.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OidcError("oidc_discovery_invalid") from exc
    if not isinstance(payload, dict):
        raise OidcError("oidc_discovery_invalid")
    authorization = str(payload.get("authorization_endpoint") or "")
    token = str(payload.get("token_endpoint") or "")
    discovered_issuer = str(payload.get("issuer") or "")
    if not authorization or not token or not discovered_issuer:
        raise OidcError("oidc_discovery_incomplete")
    if not _is_allowed_idp_url(authorization) or not _is_allowed_idp_url(token):
        raise OidcError("oidc_discovery_insecure")
    expected = _normalize_issuer(issuer)
    if issuer.rstrip("/").endswith("/.well-known/openid-configuration"):
        expected = _normalize_issuer(url.rsplit("/.well-known/", 1)[0])
    if _normalize_issuer(discovered_issuer) != expected:
        raise OidcError("oidc_issuer_mismatch")
    discovery = OidcDiscovery(
        issuer=discovered_issuer,
        authorization_endpoint=authorization,
        token_endpoint=token,
        jwks_uri=str(payload["jwks_uri"]) if payload.get("jwks_uri") else None,
        userinfo_endpoint=(
            str(payload["userinfo_endpoint"]) if payload.get("userinfo_endpoint") else None
        ),
        end_session_endpoint=(
            str(payload["end_session_endpoint"]) if payload.get("end_session_endpoint") else None
        ),
        scopes_supported=tuple(payload.get("scopes_supported") or ()),
        code_challenge_methods_supported=tuple(
            payload.get("code_challenge_methods_supported") or ()
        ),
    )
    with _discovery_lock:
        _discovery_cache[url] = (now, discovery)
    return discovery


def build_authorize_url(
    *,
    discovery: OidcDiscovery,
    config: OidcConfig,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    sep = "&" if "?" in discovery.authorization_endpoint else "?"
    return f"{discovery.authorization_endpoint}{sep}{urlencode(params)}"


def _purge_pending_locked(now: float) -> None:
    stale = [key for key, session in _pending.items() if now - session.created_at > _PENDING_TTL]
    for key in stale:
        del _pending[key]


def begin_login(
    *,
    callback_uri: str,
    pending: PendingAuthorize | None = None,
    next_path: str = "/dashboard",
    browser_binding: str = "",
    config: OidcConfig | None = None,
    transport: HttpTransport | None = None,
) -> str:
    cfg = config or load_oidc_config()
    if not cfg.enabled:
        raise OidcError("oidc_not_configured")
    if not _is_allowed_callback(callback_uri):
        raise OidcError("oidc_redirect_invalid")
    discovery = discover(cfg.issuer, transport=transport)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    session = LoginSession(
        state=state,
        nonce=nonce,
        code_verifier=verifier,
        callback_uri=callback_uri,
        created_at=time.time(),
        pending=pending,
        next_path=next_path or "/dashboard",
        browser_binding=browser_binding,
    )
    now = time.time()
    with _pending_lock:
        _purge_pending_locked(now)
        if len(_pending) >= _MAX_PENDING:
            raise OidcError("oidc_busy")
        _pending[state] = session
    return build_authorize_url(
        discovery=discovery,
        config=cfg,
        redirect_uri=callback_uri,
        state=state,
        nonce=nonce,
        code_challenge=challenge,
    )


def begin_authorize_login(
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    callback_uri: str,
    code_challenge_method: str = "S256",
    scope: str = "",
    state: str | None = None,
    profile: str = "core",
    browser_binding: str = "",
    config: OidcConfig | None = None,
    transport: HttpTransport | None = None,
) -> str:
    pending = PendingAuthorize(
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        scope=scope,
        state=state,
        profile=profile,
    )
    return begin_login(
        callback_uri=callback_uri,
        pending=pending,
        browser_binding=browser_binding,
        config=config,
        transport=transport,
    )


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise OidcError("oidc_id_token_invalid")
    payload = parts[1]
    pad = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + pad)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OidcError("oidc_id_token_invalid") from exc
    if not isinstance(data, dict):
        raise OidcError("oidc_id_token_invalid")
    return data


def validate_id_token_claims(
    claims: dict[str, Any],
    *,
    config: OidcConfig,
    discovery: OidcDiscovery,
    nonce: str,
    now: float | None = None,
) -> None:
    current = time.time() if now is None else now
    iss = str(claims.get("iss") or "")
    if _normalize_issuer(iss) != _normalize_issuer(discovery.issuer):
        raise OidcError("oidc_id_token_iss")
    aud = claims.get("aud")
    audiences = [aud] if isinstance(aud, str) else aud
    if not isinstance(audiences, list) or not all(isinstance(a, str) for a in audiences):
        raise OidcError("oidc_id_token_aud")
    if len(audiences) > 1 and claims.get("azp") != config.client_id:
        raise OidcError("oidc_id_token_aud")
    if "azp" in claims and claims["azp"] != config.client_id:
        raise OidcError("oidc_id_token_aud")
    if config.client_id not in audiences:
        raise OidcError("oidc_id_token_aud")
    if config.audience and config.audience not in audiences:
        raise OidcError("oidc_id_token_aud")
    try:
        exp = float(claims["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OidcError("oidc_id_token_exp") from exc
    if not math.isfinite(exp) or exp <= current:
        raise OidcError("oidc_id_token_expired")
    if str(claims.get("nonce") or "") != nonce:
        raise OidcError("oidc_id_token_nonce")


def _form_body(fields: dict[str, str]) -> bytes:
    return urlencode(fields).encode("ascii")


def exchange_code(
    *,
    code: str,
    session: LoginSession,
    config: OidcConfig,
    discovery: OidcDiscovery,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    fields = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": session.callback_uri,
        "client_id": config.client_id,
        "code_verifier": session.code_verifier,
    }
    if config.client_secret:
        fields["client_secret"] = config.client_secret
    client = transport or _transport
    resp = client.request(
        "POST",
        discovery.token_endpoint,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=_form_body(fields),
    )
    if resp.status != 200:
        raise OidcError("oidc_token_failed", f"token HTTP {resp.status}")
    try:
        payload = json.loads(resp.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OidcError("oidc_token_invalid") from exc
    if not isinstance(payload, dict) or not payload.get("id_token"):
        raise OidcError("oidc_token_invalid")
    return payload


@dataclass
class OidcCallbackResult:
    subject: str
    access_token: str = ""
    expires_at: float = 0.0
    claims: dict[str, Any] = field(default_factory=dict)
    pending: PendingAuthorize | None = None
    next_path: str = "/dashboard"


def complete_callback(
    *,
    code: str,
    state: str,
    browser_binding: str = "",
    config: OidcConfig | None = None,
    transport: HttpTransport | None = None,
) -> OidcCallbackResult:
    if not code or not state:
        raise OidcError("oidc_callback_missing")
    cfg = config or load_oidc_config()
    if not cfg.enabled:
        raise OidcError("oidc_not_configured")
    now = time.time()
    with _pending_lock:
        _purge_pending_locked(now)
        session = _pending.get(state)
        if (session is None or session.consumed
                or not secrets.compare_digest(session.browser_binding, browser_binding)):
            raise OidcError("oidc_state_invalid")
        session.consumed = True
    try:
        discovery = discover(cfg.issuer, transport=transport)
        token_payload = exchange_code(
            code=code,
            session=session,
            config=cfg,
            discovery=discovery,
            transport=transport,
        )
        claims = verify_id_token(str(token_payload["id_token"]), discovery, cfg, transport)
        validate_id_token_claims(claims, config=cfg, discovery=discovery, nonce=session.nonce)
        subject = str(claims.get("sub") or "")
        if not subject:
            raise OidcError("oidc_id_token_sub")
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OidcError("oidc_token_invalid")
        try:
            expires_in = float(token_payload["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OidcError("oidc_token_invalid") from exc
        if not math.isfinite(expires_in) or expires_in <= 0:
            raise OidcError("oidc_token_invalid")
        expires_at = min(float(claims["exp"]), now + expires_in, now + 3600)
    finally:
        with _pending_lock:
            _pending.pop(state, None)
    return OidcCallbackResult(
        subject=subject,
        access_token=access_token,
        expires_at=expires_at,
        claims=claims,
        pending=session.pending,
        next_path=session.next_path,
    )


def verify_id_token(
    token: str, discovery: OidcDiscovery, config: OidcConfig,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    """Pin RS256 and fetch the current issuer keys without trusting token URLs."""
    if not discovery.jwks_uri or not _is_allowed_idp_url(discovery.jwks_uri):
        raise OidcError("oidc_jwks_invalid")
    response = (transport or _transport).request(
        "GET", discovery.jwks_uri, headers={"Accept": "application/json"}
    )
    if response.status != 200:
        raise OidcError("oidc_jwks_unavailable")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise OidcError("oidc_id_token_invalid")
        keys = json.loads(response.body)["keys"]
        matching = [key for key in keys if key.get("kid") == header["kid"]
                    and key.get("use", "sig") == "sig"
                    and key.get("alg", "RS256") == "RS256"]
        if len(matching) != 1:
            raise OidcError("oidc_id_token_invalid")
        key = jwt.PyJWK.from_dict(matching[0], algorithm="RS256").key
        return jwt.decode(token, key, algorithms=["RS256"], audience=config.client_id,
                          issuer=discovery.issuer,
                          options={"require": ["exp", "iat", "sub", "iss", "aud", "nonce"]})
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise OidcError("oidc_id_token_invalid") from exc


def userinfo(access_token: str, subject: str) -> dict[str, Any]:
    """Uncached provider check: revoked and expired access tokens stop working immediately."""
    cfg = load_oidc_config()
    discovery = discover(cfg.issuer)
    if not discovery.userinfo_endpoint or not _is_allowed_idp_url(discovery.userinfo_endpoint):
        raise OidcError("oidc_userinfo_unavailable")
    response = _transport.request("GET", discovery.userinfo_endpoint, headers={
        "Accept": "application/json", "Authorization": f"Bearer {access_token}",
    })
    if response.status in {401, 403}:
        raise OidcError("oidc_session_invalid")
    if response.status != 200:
        raise OidcError("oidc_userinfo_unavailable")
    try:
        claims = json.loads(response.body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise OidcError("oidc_userinfo_unavailable") from exc
    if not isinstance(claims, dict) or claims.get("sub") != subject:
        raise OidcError("oidc_session_invalid")
    required_groups = set(_env("AUTH_OIDC_REQUIRED_GROUPS").split())
    if required_groups and (not isinstance(claims.get("groups"), list)
                            or not required_groups.intersection(claims["groups"])):
        raise OidcError("oidc_entitlement_required")
    return claims
