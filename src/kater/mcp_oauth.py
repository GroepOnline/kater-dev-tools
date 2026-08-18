"""Outbound OAuth client for catalog Connect (Slack, Microsoft, generic).

Kater already speaks OAuth as a *server* (ChatGPT / dashboard login). This
module is the other direction: the operator clicks Connect, the browser
signs into the provider, tokens are stored as a server connection.

No live authorize/token exchange happens unless an operator starts Connect.
Tests must mock HTTP; this module never embeds credentials.
"""

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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from kater.connect_policy import assert_safe_oauth_base
from kater.profiles import ToolSource

_log = logging.getLogger("kater.mcp_oauth")
_lock = threading.Lock()
_PENDING_TTL = 600
_PENDING_NAME = "mcp-oauth-pending.json"

SLACK_PRM_URL = "https://mcp.slack.com/.well-known/oauth-protected-resource"
SLACK_DEFAULT_SCOPES = (
    "search:read.public,search:read.private,channels:history,channels:read,"
    "users:read,chat:write,canvases:write"
)


def _pending_path() -> Path:
    return Path.cwd() / ".kater" / _PENDING_NAME


def _load_pending() -> dict[str, Any]:
    path = _pending_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_pending(data: dict[str, Any]) -> None:
    path = _pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, path)


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _prune_locked(data: dict[str, Any], now: float) -> dict[str, Any]:
    return {
        key: value
        for key, value in data.items()
        if isinstance(value, dict) and float(value.get("expires_at") or 0) > now
    }


def redirect_uri(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/mcp/oauth/callback"


def slack_app_manifest(callback: str, source: ToolSource | None = None) -> dict[str, Any]:
    user_scopes = discover_scopes(source) if source else SLACK_DEFAULT_SCOPES.replace(",", " ")

    return {
        "display_information": {
            "name": "Kater MCP",
            "description": "Sign in from the Kater catalog to use Slack-hosted MCP.",
        },
        "features": {
            "bot_user": {"display_name": "Kater MCP", "always_online": False},
        },
        "oauth_config": {
            "redirect_urls": [callback],
            "scopes": {
                "bot": ["users:read"],
                "user": user_scopes.split(),
            },
        },
        "settings": {
            "org_deploy_enabled": False,
            "socket_mode_enabled": False,
            "token_rotation_enabled": False,
        },
    }


def discover_scopes(source: ToolSource) -> str:
    oauth = source.oauth
    if not oauth:
        return ""
    if oauth.scopes:
        return " ".join(oauth.scopes)
    if oauth.provider != "slack":
        return ""
    try:
        req = urllib.request.Request(SLACK_PRM_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode())
        scopes = body.get("scopes_supported") or body.get("scopes")
        if isinstance(scopes, list) and scopes:
            return " ".join(str(s) for s in scopes if s)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _log.info("slack PRM unavailable, using default scopes: %s", exc)
    return SLACK_DEFAULT_SCOPES.replace(",", " ")


def start_authorize(
    source: ToolSource,
    *,
    client_id: str,
    base_url: str,
    label: str = "",
) -> dict[str, str]:
    oauth = source.oauth
    if not oauth:
        raise ValueError(f"{source.name} has no OAuth connect config")
    if not client_id:
        raise ValueError("oauth client id is not configured")
    base_url = assert_safe_oauth_base(base_url)
    callback = redirect_uri(base_url)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        pending = _prune_locked(_load_pending(), now)
        pending[state] = {
            "server": source.name,
            "provider": oauth.provider,
            "label": label,
            "verifier": verifier,
            "redirect_uri": callback,
            "expires_at": now + _PENDING_TTL,
        }
        _save_pending(pending)
    scopes = discover_scopes(source)
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback,
        "state": state,
        **dict(oauth.extra_authorize),
    }
    if oauth.pkce:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    if scopes:
        params["scope"] = scopes
    if oauth.resource:
        params["resource"] = oauth.resource
    if oauth.provider == "microsoft":
        params.setdefault("prompt", "select_account")
        params.setdefault("response_mode", "query")
    url = oauth.authorize_url + "?" + urllib.parse.urlencode(params)
    return {"authorize_url": url, "state": state, "redirect_uri": callback}


def _form_post(url: str, payload: dict[str, str]) -> dict[str, Any]:
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"error": "token_http_error", "status": exc.code}
        if not isinstance(parsed, dict):
            parsed = {"error": "token_http_error", "status": exc.code}
        parsed.setdefault("error", f"token_http_{exc.code}")
        return parsed
    except OSError as exc:
        return {"error": "token_transport_error", "message": str(exc)}
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"error": "invalid_token_response"}
    return parsed if isinstance(parsed, dict) else {"error": "invalid_token_response"}


def _extract_tokens(provider: str, body: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if body.get("ok") is False:
        raise ValueError(str(body.get("error") or "provider_denied"))
    access = str(body.get("access_token") or body.get("authed_user", {}).get("access_token") or "")
    refresh = str(body.get("refresh_token") or "")
    extra: dict[str, Any] = {}
    if provider == "slack":
        raw_team = body.get("team")
        team = raw_team if isinstance(raw_team, dict) else {}
        extra["team"] = str(team.get("name") or team.get("id") or "")
        extra["team_id"] = str(team.get("id") or "")
    if provider == "microsoft":
        extra["token_type"] = str(body.get("token_type") or "Bearer")
        extra["expires_in"] = body.get("expires_in")
    if not access:
        raise ValueError("provider did not return an access token")
    return access, refresh, extra


def peek_pending(state: str) -> dict[str, Any]:
    now = time.time()
    with _lock:
        pending = _prune_locked(_load_pending(), now)
        record = pending.get(state)
    return dict(record) if isinstance(record, dict) else {}


def abandon_pending(state: str) -> dict[str, Any]:
    """Drop a pending session without exchanging a code (fail-closed)."""
    now = time.time()
    with _lock:
        pending = _prune_locked(_load_pending(), now)
        record = pending.pop(state, None)
        _save_pending(pending)
    return dict(record) if isinstance(record, dict) else {}


def consume_callback(
    *,
    state: str,
    code: str,
    client_id: str,
    client_secret: str,
    token_url: str,
    pkce: bool,
) -> dict[str, Any]:
    now = time.time()
    with _lock:
        pending = _prune_locked(_load_pending(), now)
        record = pending.pop(state, None)
        _save_pending(pending)
    if not record:
        raise ValueError("unknown or expired OAuth state")
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(record["redirect_uri"]),
        "client_id": client_id,
    }
    if client_secret:
        payload["client_secret"] = client_secret
    if pkce:
        payload["code_verifier"] = str(record["verifier"])
    body = _form_post(token_url, payload)
    access, refresh, extra = _extract_tokens(str(record.get("provider") or ""), body)
    return {
        "server": record["server"],
        "provider": record.get("provider"),
        "label": record.get("label") or extra.get("team") or "",
        "access_token": access,
        "refresh_token": refresh,
        "extra": extra,
    }


def callback_html(*, server: str, label: str, catalog_url: str, error: str = "") -> str:
    title = "Connect failed" if error else "Connected"
    detail = (
        html.escape(error)
        if error
        else (
            "Signed in"
            + (f" as {html.escape(label)}" if label else "")
            + f" for {html.escape(server)}."
        )
    )
    dest = html.escape(catalog_url, quote=True)
    script_url = (
        json.dumps(catalog_url)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )
    return (
        "<!doctype html><meta charset=utf-8><title>"
        + html.escape(title)
        + "</title><p>"
        + detail
        + '</p><p><a href="'
        + dest
        + '">Back to catalog</a></p>'
        + f"<script>location.replace({script_url})</script>"
    )
