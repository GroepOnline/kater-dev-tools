from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_log = logging.getLogger("kater.oauth")

# Schemes permitted in a registered redirect_uri. ``http`` is allowed only for
# loopback (127.0.0.1/localhost) per RFC 8252 §7.3; everything else must be
# https. Dangerous schemes (javascript:, data:, file:) are rejected.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
# Bound on registered clients so an attacker cannot bloat oauth.json.
MAX_CLIENTS = 500
MAX_TOKENS = 5000


def _is_safe_redirect_uri(uri: str) -> bool:
    """Reject dangerous redirect_uri schemes and non-https non-loopback hosts."""
    try:
        parsed = urlparse(uri)
    except (ValueError, TypeError):
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme == "https":
        return True
    if scheme == "http" and (parsed.hostname or "") in _LOOPBACK_HOSTS:
        return True
    return False


@dataclass
class ClientRegistration:
    client_id: str
    client_secret: str | None = None
    client_name: str = ""
    redirect_uris: list[str] = field(default_factory=list)
    # OAuth token-endpoint auth method; "none" = public PKCE client. Not a secret.
    token_endpoint_auth_method: str = "none"
    created_at: float = field(default_factory=time.time)


@dataclass
class AuthCode:
    code: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    scope: str
    state: str | None
    created_at: float = field(default_factory=time.time)
    used: bool = False


@dataclass
class AccessToken:
    token: str
    client_id: str
    scope: str
    profile: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def is_valid(self) -> bool:
        return time.time() < self.expires_at if self.expires_at else True


def _db_path() -> Path:
    return Path.cwd() / ".kater" / "oauth.json"


_state: dict[str, Any] = {}

# Guards all read-modify-write access to _state and the backing file. The API
# runs under ThreadingHTTPServer, so concurrent /token and /register calls
# would otherwise race on _save() and corrupt oauth.json or lose writes.
_lock = threading.RLock()


def _load() -> dict[str, Any]:
    global _state
    if _state:
        return _state
    path = _db_path()
    if path.exists():
        _state = json.loads(path.read_text(encoding="utf-8"))
    else:
        _state = {"clients": {}, "codes": {}, "tokens": {}}
    return _state


def _save() -> None:
    global _state
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(
        json.dumps(_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # Restrict permissions so only the owner can read/write (no world access).
    # This prevents token theft by co-located processes on shared machines.
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def reset_state() -> None:
    global _state
    with _lock:
        _state = {}
        path = _db_path()
        if path.exists():
            path.unlink()


def register_client(
    client_name: str = "",
    redirect_uris: list[str] | None = None,
    token_endpoint_auth_method: str = "none",
) -> ClientRegistration:
    uris = [u for u in (redirect_uris or []) if u]
    if not uris:
        raise ValueError("redirect_uris is required and must be non-empty")
    bad = [u for u in uris if not _is_safe_redirect_uri(u)]
    if bad:
        raise ValueError(
            "redirect_uris must use https (or http for loopback); rejected: "
            + ", ".join(bad)
        )
    if token_endpoint_auth_method not in ("none", "client_secret_post"):
        token_endpoint_auth_method = "none"
    with _lock:
        data = _load()
        clients = data.get("clients", {})
        if len(clients) >= MAX_CLIENTS:
            raise ValueError("client registration limit reached")
        client_id = f"client_{secrets.token_hex(12)}"
        client = ClientRegistration(
            client_id=client_id,
            client_secret=secrets.token_hex(24),
            client_name=client_name[:200] or "unnamed",
            redirect_uris=uris,
            token_endpoint_auth_method=token_endpoint_auth_method,
        )
        clients[client_id] = {
            "client_id": client.client_id,
            "client_secret": client.client_secret,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": client.token_endpoint_auth_method,
            "created_at": client.created_at,
        }
        _save()
    return client


def get_client(client_id: str) -> ClientRegistration | None:
    with _lock:
        data = _load()
        raw = data["clients"].get(client_id)
    if not raw:
        return None
    return ClientRegistration(
        client_id=raw["client_id"],
        client_secret=raw.get("client_secret"),
        client_name=raw.get("client_name", ""),
        redirect_uris=raw.get("redirect_uris", []),
        token_endpoint_auth_method=raw.get("token_endpoint_auth_method", "none"),
        created_at=raw.get("created_at", time.time()),
    )


def validate_redirect_uri(
    client: ClientRegistration,
    redirect_uri: str,
) -> bool:
    # A client with no registered redirect URIs must not be able to receive
    # auth codes at an arbitrary location (open redirect / code injection).
    if not client.redirect_uris:
        return False
    if not redirect_uri:
        return False
    return redirect_uri in client.redirect_uris


def create_auth_code(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    scope: str = "",
    state: str | None = None,
    profile: str = "core",
) -> str:
    if code_challenge_method != "S256":
        raise ValueError("Only S256 code challenge method is supported")
    with _lock:
        data = _load()
        code = f"code_{secrets.token_hex(16)}"
        data["codes"][code] = {
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "scope": scope,
            "state": state,
            "profile": profile,
            "created_at": time.time(),
            "used": False,
        }
        _save()
    return code


def exchange_code(
    code: str,
    client_id: str,
    code_verifier: str,
    client_secret: str | None = None,
) -> dict[str, Any] | None:
    with _lock:
        data = _load()
        raw = data["codes"].get(code)
        if not raw or raw["used"] or raw["client_id"] != client_id:
            return None
        if time.time() - raw["created_at"] > 300:
            return None

        # Confidential clients (client_secret_post) must present their secret.
        client = data["clients"].get(client_id)
        if client and client.get("token_endpoint_auth_method") == "client_secret_post":
            secret = client.get("client_secret")
            if not secret or not client_secret or not secrets.compare_digest(
                client_secret, secret
            ):
                _log.warning("token exchange rejected: bad client_secret for %s", client_id)
                return None

        # Only S256 is issued (see create_auth_code); reject anything else.
        if raw["code_challenge_method"] != "S256":
            return None
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        if not secrets.compare_digest(expected, raw["code_challenge"]):
            return None

        raw["used"] = True
        _save()

        return create_token(
            client_id=client_id,
            scope=raw.get("scope", ""),
            profile=raw.get("profile", "core"),
        )


def create_token(
    client_id: str,
    scope: str = "",
    profile: str = "core",
    expires_in: int = 86400,
) -> dict[str, Any]:
    with _lock:
        data = _load()
        if len(data.get("tokens", {})) >= MAX_TOKENS:
            raise ValueError(f"Token limit reached ({MAX_TOKENS})")
        token_str = f"tok_{secrets.token_hex(24)}"
        now = time.time()
        data["tokens"][token_str] = {
            "token": token_str,
            "client_id": client_id,
            "scope": scope,
            "profile": profile,
            "created_at": now,
            "expires_at": now + expires_in,
        }
        _save()
    return {
        "access_token": token_str,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "scope": scope,
    }


def validate_token(token: str) -> AccessToken | None:
    with _lock:
        data = _load()
        raw = data["tokens"].get(token)
    if not raw:
        return None
    at = AccessToken(
        token=raw["token"],
        client_id=raw["client_id"],
        scope=raw.get("scope", ""),
        profile=raw.get("profile", "core"),
        created_at=raw.get("created_at", time.time()),
        expires_at=raw.get("expires_at", 0),
    )
    if not at.is_valid():
        return None
    return at


def revoke_token(token: str) -> bool:
    with _lock:
        data = _load()
        if token in data["tokens"]:
            del data["tokens"][token]
            _save()
            return True
    return False


def cleanup_expired() -> int:
    with _lock:
        data = _load()
        now = time.time()
        expired = [
            t for t, v in data["tokens"].items()
            if v.get("expires_at", 0) > 0 and now >= v["expires_at"]
        ]
        for t in expired:
            del data["tokens"][t]
        old_codes = [
            c for c, v in data["codes"].items()
            if now - v.get("created_at", now) > 600
        ]
        for c in old_codes:
            del data["codes"][c]
        if expired or old_codes:
            _save()
    return len(expired) + len(old_codes)


def render_consent_page(
    client_name: str,
    redirect_uri: str,
    state: str | None,
    authorize_url: str,
    profile: str = "core",
) -> str:
    # Escape for HTML text content AND attribute values. The prior code only
    # stripped < and >, which let `state` break out of an href attribute and
    # run script (reflected XSS). html.escape(quote=True) covers &, <, >, ", '.
    safe_name = html.escape(client_name or "", quote=True)
    safe_uri = html.escape(redirect_uri or "", quote=True)
    safe_profile = html.escape(profile or "", quote=True)
    # state is interpolated into an href query parameter; URL-encode it so it
    # cannot inject & / = / quotes, then HTML-escape the result for safety.
    if state:
        from urllib.parse import quote_plus

        state_param = f"&state={html.escape(quote_plus(state), quote=True)}"
    else:
        state_param = ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Kater — Authorize</title>
<style>
:root {{
  --bg:#0a0e14; --surface:#121826; --border:#1e2733;
  --text:#e2e8f0; --dim:#64748b; --accent:#f59e0b;
  --green:#22c55e; --mono:'SF Mono','Consolas',monospace;
  color-scheme: dark;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
:focus-visible {{
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }}
}}
body {{
  background:var(--bg); color:var(--text);
  font-family:system-ui,sans-serif;
  display:flex; align-items:center; justify-content:center;
  min-height:100vh;
}}
.card {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:40px; max-width:420px; width:90%;
  text-align:center;
}}
.logo {{
  font-family:var(--mono); font-weight:700; font-size:20px;
  letter-spacing:2px; color:var(--accent); margin-bottom:24px;
}}
.logo::before {{
  content:''; display:inline-block; width:8px; height:8px;
  border-radius:50%; background:var(--accent);
  box-shadow:0 0 12px var(--accent); margin-right:8px;
  vertical-align:middle;
}}
h1 {{ font-size:18px; margin-bottom:8px; }}
p {{ color:var(--dim); font-size:14px; margin-bottom:24px; }}
.app-name {{
  font-family:var(--mono); font-weight:600; color:var(--text);
  padding:2px 8px; background:rgba(255,255,255,0.05);
  border-radius:4px; font-size:13px;
}}
.btn-row {{ display:flex; gap:12px; justify-content:center; }}
.btn {{
  font-family:var(--mono); font-size:13px; font-weight:600;
  padding:10px 24px; border-radius:8px; cursor:pointer;
  border:none; text-decoration:none; letter-spacing:0.5px;
  text-transform:uppercase; transition:200ms;
}}
.btn-allow {{ background:var(--green); color:#000; }}
.btn-allow:hover {{ opacity:0.9; }}
.btn-deny {{
  background:transparent; border:1px solid var(--border);
  color:var(--dim);
}}
.btn-deny:hover {{ color:var(--text); border-color:var(--text); }}
.meta {{
  margin-top:24px; padding-top:16px; border-top:1px solid var(--border);
  font-size:11px; color:var(--dim); font-family:var(--mono);
}}
</style></head><body>
<div class="card">
  <div class="logo">KATER</div>
  <h1>Authorize <span class="app-name">{safe_name}</span></h1>
  <p>This app wants to connect to your Kater MCP gateway
  (profile: {safe_profile}). It will be able to call tools
  exposed by this profile.</p>
  <div class="btn-row">
    <a class="btn btn-allow"
      href="{authorize_url}&approve=1{state_param}" role="button"
      aria-label="Allow {safe_name} to connect">Allow</a>
    <a class="btn btn-deny"
      href="{authorize_url}&approve=0{state_param}" role="button"
      aria-label="Deny access">Deny</a>
  </div>
  <div class="meta">Redirect: {safe_uri}</div>
</div>
</body></html>"""


def discovery_metadata(base_url: str) -> dict[str, Any]:
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/authorize",
        "token_endpoint": f"{base_url}/token",
        "registration_endpoint": f"{base_url}/register",
        "revocation_endpoint": f"{base_url}/revoke",
        "grant_types_supported": ["authorization_code"],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "scopes_supported": ["profile", "tools"],
    }


def resource_metadata(base_url: str) -> dict[str, Any]:
    return {
        "resource": base_url,
        "authorization_servers": [base_url],
        "scopes_supported": ["profile", "tools"],
        "bearer_methods_supported": ["header"],
    }
