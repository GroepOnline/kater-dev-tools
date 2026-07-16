"""All REST API route handlers.

Importing this module has the side-effect of registering every endpoint
into ``models.ROUTER`` via the ``@route`` decorator.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode

from kater.adapters.external import scan_adapters
from kater.api.models import Request, Response, route
from kater.chains import list_chains

if TYPE_CHECKING:
    pass
from kater.deploy import list_deploy_formats, render_deploy
from kater.doctor import run_doctor
from kater.profiles import get_source, list_profiles
from kater.proxy import get_proxy
from kater.registry import tools_for_profile
from kater.settings import (
    ServerOverride,
    is_public_settings,
    load_settings,
    save_settings,
    unsafe_public_settings_override_enabled,
)
from kater.telemetry import (
    eval_summary,
    load_events,
    record_chain_run,
    record_server_toggle,
    status_overview,
)
from kater.tunnel import (
    start_cloudflared,
    start_tailscale_funnel,
    stop_cloudflared,
    stop_tailscale_funnel,
    tunnel_overview,
)

# OAuth consent nonce machinery (module-level state shared with handlers).
_CONSENT_COOKIE = "kater_oauth_consent"
_CONSENT_TTL_SECONDS = 600
_consent_nonces: dict[str, float] = {}
_consent_lock = threading.Lock()


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_public_mode() -> bool:
    settings = load_settings()
    return _env_truthy("KATER_PUBLIC") or settings.host not in (
        "127.0.0.1",
        "localhost",
        "::1",
    )


def _cookie_value(req: Request, name: str) -> str:
    cookie = req.header("cookie") or ""
    prefix = f"{name}="
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix) :]
    return ""


def _new_consent_nonce() -> str:
    nonce = secrets.token_urlsafe(32)
    now = time.time()
    with _consent_lock:
        expired = [key for key, expiry in _consent_nonces.items() if expiry <= now]
        for key in expired:
            _consent_nonces.pop(key, None)
        _consent_nonces[nonce] = now + _CONSENT_TTL_SECONDS
    return nonce


def _consume_consent_nonce(req: Request) -> bool:
    supplied = req.query1("consent_nonce", "") or ""
    cookie = _cookie_value(req, _CONSENT_COOKIE)
    if not supplied or not cookie or not secrets.compare_digest(supplied, cookie):
        return False
    now = time.time()
    with _consent_lock:
        expiry = _consent_nonces.pop(supplied, 0)
    return expiry > now


def _adapter_payload(profile: str) -> dict[str, Any]:
    # Exposed over the network: never emit resolved secrets in launch hints.
    inventory = scan_adapters({profile}, include_secrets=False)
    settings = load_settings()
    adapters = []
    for a in inventory.sources:
        if not settings.is_server_enabled(a.source.name, default=True):
            continue
        adapters.append(
            {
                "name": a.source.name,
                "transport": a.source.transport.value,
                "configured": a.configured,
                "missing_env": a.missing_env,
                "risk": a.source.risk.value,
                "launch_hint": a.launch_hint,
                "enabled": settings.is_server_enabled(a.source.name, default=True),
            }
        )
    return {
        "profile": profile,
        "adapters": adapters,
        "total": len(adapters),
        "configured": sum(1 for a in adapters if a["configured"]),
    }


def _mcp_servers_payload() -> dict[str, Any]:
    from kater.profiles import visible_tool_sources

    settings = load_settings()
    servers = []
    for source in visible_tool_sources():
        if source.transport == "native":
            continue
        env_present = all(os.environ.get(v) for v in source.env)
        servers.append(
            {
                "name": source.name,
                "description": source.description,
                "transport": source.transport.value,
                "risk": source.risk.value,
                "profiles": sorted(source.profiles),
                "env_required": source.env,
                "env_configured": env_present,
                "homepage": source.homepage,
                "mcp": source.mcp.model_dump() if source.mcp else None,
                "enabled": settings.is_server_enabled(source.name, default=True),
            }
        )
    return {"total": len(servers), "servers": servers}


def _group_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


def _ws_broadcast(event_type: str, data: dict[str, Any]) -> None:
    try:
        from kater.websocket import broadcast_event

        broadcast_event({"type": event_type, **data, "ts": time.time()})
    except ImportError:
        pass


# ── Public endpoints (no auth) ─────────────────────────────────────


@route("GET", "/health", public=True)
def _health(_: Request) -> Response:
    from kater import __version__

    settings = load_settings()
    return Response.json(
        200,
        {"status": "ok", "version": __version__, "auth_mode": settings.auth.mode},
    )


@route("GET", "/", public=True)
@route("GET", "/dashboard", public=True)
def _dashboard(_: Request) -> Response:
    from kater.web import render_dashboard

    return Response.html(200, render_dashboard(ws_port=load_settings().ws_port))


@route("GET", "/.well-known/oauth-authorization-server", public=True)
def _oauth_discovery(req: Request) -> Response:
    from kater.oauth import discovery_metadata

    return Response.json(200, discovery_metadata(req.base_url))


@route("GET", "/.well-known/oauth-protected-resource", public=True)
def _oauth_resource(req: Request) -> Response:
    from kater.oauth import resource_metadata

    return Response.json(200, resource_metadata(req.base_url))


@route("GET", "/authorize", public=True)
def _authorize(req: Request) -> Response:
    from kater.oauth import (
        create_auth_code,
        get_client,
        get_or_create_dashboard_client,
        render_consent_page,
        validate_redirect_uri,
    )

    client_id = req.query1("client_id", "") or ""
    redirect_uri = req.query1("redirect_uri", "") or ""
    challenge = req.query1("code_challenge", "") or ""
    method = req.query1("code_challenge_method", "S256") or "S256"
    scope = req.query1("scope", "") or ""
    state = req.query1("state")
    profile = req.query1("profile", "core") or "core"
    approve = req.query1("approve", "") or ""

    if client_id == "kater-dashboard":
        client = get_or_create_dashboard_client(
            base_url=req.base_url,
            redirect_uri=redirect_uri,
        )
    else:
        client = get_client(client_id)
    if not client:
        return Response.json(400, {"error": "invalid_client"})
    if not validate_redirect_uri(client, redirect_uri):
        return Response.json(400, {"error": "invalid_redirect_uri"})

    if approve == "1":
        if not _consume_consent_nonce(req):
            return Response.json(403, {"error": "consent_required"})
        try:
            code = create_auth_code(
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=challenge,
                code_challenge_method=method,
                scope=scope,
                state=state,
                profile=profile,
            )
        except ValueError:
            return Response.json(
                400,
                {"error": "invalid_request", "detail": "unsupported code_challenge_method"},
            )
        sep = "&" if "?" in redirect_uri else "?"
        location = f"{redirect_uri}{sep}code={quote(code, safe='')}"
        if state:
            location += f"&state={quote(state, safe='')}"
        return Response.redirect(location)

    if approve == "0":
        _consume_consent_nonce(req)
        sep = "&" if "?" in redirect_uri else "?"
        return Response.redirect(f"{redirect_uri}{sep}error=access_denied")

    consent_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": method,
        "profile": profile,
    }
    if scope:
        consent_params["scope"] = scope
    authorize_self = f"{req.base_url}/authorize?{urlencode(consent_params)}"
    consent_nonce = _new_consent_nonce()

    response = Response.html(
        200,
        render_consent_page(
            client_name=client.client_name,
            redirect_uri=redirect_uri,
            state=state,
            authorize_url=authorize_self,
            profile=profile,
            consent_nonce=consent_nonce,
        ),
    )
    response.headers["Set-Cookie"] = (
        f"{_CONSENT_COOKIE}={consent_nonce}; Path=/authorize; HttpOnly; SameSite=Lax; Max-Age=600"
    )
    return response


@route("POST", "/token", public=True)
def _token(req: Request) -> Response:
    from kater.oauth import exchange_code

    params = req.json_or_form
    if params.get("grant_type", "") != "authorization_code":
        return Response.json(400, {"error": "unsupported_grant_type"})
    token = exchange_code(
        params.get("code", ""),
        params.get("client_id", ""),
        params.get("code_verifier", ""),
        client_secret=params.get("client_secret"),
    )
    if not token:
        return Response.json(400, {"error": "invalid_grant"})
    return Response.json(200, token)


@route("POST", "/register", public=True)
def _register_client(req: Request) -> Response:
    import secrets as _secrets

    from kater.oauth import register_client

    reg_token = os.environ.get("KATER_REGISTRATION_TOKEN", "")
    allow_dynamic = _env_truthy("KATER_ALLOW_DYNAMIC_REGISTRATION")
    if _is_public_mode() and (not allow_dynamic or not reg_token):
        return Response.json(403, {"error": "registration_disabled"})
    supplied = req.header("x-registration-token") or req.query1("registration_token") or ""
    if reg_token and (not supplied or not _secrets.compare_digest(supplied, reg_token)):
        return Response.json(403, {"error": "registration_forbidden"})

    body = req.json
    try:
        client = register_client(
            client_name=body.get("client_name", ""),
            redirect_uris=body.get("redirect_uris", []),
            token_endpoint_auth_method=body.get("token_endpoint_auth_method", "none"),
        )
    except ValueError as exc:
        return Response.json(400, {"error": "invalid_redirect_uri", "detail": str(exc)})
    return Response.json(
        201,
        {
            "client_id": client.client_id,
            "client_secret": client.client_secret,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": client.token_endpoint_auth_method,
        },
    )


@route("POST", "/revoke", public=True)
def _revoke(req: Request) -> Response:
    from kater.oauth import revoke_token

    revoke_token(req.form.get("token", ""))
    return Response.json(200, {"revoked": True})


# ── Read endpoints ─────────────────────────────────────────────────


@route("GET", "/api/profiles")
def _profiles(_: Request) -> Response:
    return Response.json(200, {"profiles": list_profiles()})


@route("GET", "/api/tools")
def _tools(_: Request) -> Response:
    profile = os.environ.get("KATER_PROFILE", "core")
    tools = tools_for_profile(profile)
    return Response.json(
        200,
        {"profile": profile, "tools": [t.model_dump(exclude={"handler"}) for t in tools]},
    )


@route("GET", "/api/adapters")
def _adapters(_: Request) -> Response:
    profile = os.environ.get("KATER_PROFILE", "core")
    return Response.json(200, _adapter_payload(profile))


@route("GET", "/api/doctor")
def _doctor(_: Request) -> Response:
    profile = os.environ.get("KATER_PROFILE", "core")
    return Response.json(200, run_doctor(profiles={profile}).model_dump(mode="json"))


@route("GET", "/api/chains")
def _chains(_: Request) -> Response:
    profile = os.environ.get("KATER_PROFILE", "core")
    chains = list_chains(profile)
    return Response.json(200, {"chains": [c.model_dump(mode="json") for c in chains]})


@route("POST", "/api/ws-ticket")
def _ws_ticket(_: Request) -> Response:
    from kater.websocket import WS_TICKET_TTL_SECONDS, issue_ws_ticket

    return Response.json(
        200,
        {
            "ticket": issue_ws_ticket(),
            "expires_in": WS_TICKET_TTL_SECONDS,
        },
    )


@route("GET", "/api/mcp/servers")
def _mcp_servers(_: Request) -> Response:
    return Response.json(200, _mcp_servers_payload())


def _visible_source(name: str):
    """Look up a server, hiding private (org-only) sources in public mode.

    A public deployment must not even acknowledge private servers exist, so
    callers treat a None result as a 404 — identical to a truly unknown name.
    """
    from kater.profiles import is_private_source, is_public_mode

    source = get_source(name)
    if not source or (is_public_mode() and is_private_source(source)):
        return None
    return source


@route("GET", "/api/mcp/servers/{name}")
def _mcp_server(req: Request) -> Response:
    source = _visible_source(req.params["name"])
    if not source:
        return Response.json(404, {"error": f"Unknown server: {req.params['name']}"})
    settings = load_settings()
    env_present = all(os.environ.get(v) for v in source.env)
    return Response.json(
        200,
        {
            "name": source.name,
            "description": source.description,
            "transport": source.transport.value,
            "risk": source.risk.value,
            "profiles": sorted(source.profiles),
            "env_required": source.env,
            "env_configured": env_present,
            "homepage": source.homepage,
            "mcp": source.mcp.model_dump() if source.mcp else None,
            "enabled": settings.is_server_enabled(source.name, default=True),
        },
    )


@route("GET", "/api/settings")
def _get_settings(_: Request) -> Response:
    return Response.json(200, load_settings().to_safe_dict())


@route("GET", "/api/deploy")
def _deploy_formats(_: Request) -> Response:
    return Response.json(200, {"formats": list_deploy_formats()})


@route("GET", "/api/deploy/{format}")
def _deploy_render(req: Request) -> Response:
    fmt = req.params["format"]
    profile = os.environ.get("KATER_PROFILE", "core")
    known = {entry["name"] for entry in list_deploy_formats()}
    if fmt not in known:
        return Response.json(
            404,
            {"error": (f"Unknown format '{fmt}'. Available: {', '.join(sorted(known))}")},
        )
    return Response.json(200, render_deploy(fmt, profile=profile))


@route("GET", "/api/status")
def _status(_: Request) -> Response:
    return Response.json(200, status_overview())


def _parse_limit(req: Request, default: int = 50, maximum: int = 1000) -> int:
    raw = req.query1("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid limit: {raw!r}") from None
    if value < 1:
        value = 1
    return min(value, maximum)


def _parse_since(req: Request) -> float | None:
    raw = req.query1("since")
    if not raw:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        pass
    try:
        from datetime import datetime

        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise ValueError(f"Invalid since: {raw!r}") from exc


@route("GET", "/api/events")
def _events(req: Request) -> Response:
    """Return a bounded, newest-first telemetry page matching request filters."""

    import kater.storage as storage

    try:
        limit = _parse_limit(req)
        since = _parse_since(req)
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    name = req.query1("name")
    success_raw = req.query1("success")
    success = success_raw.lower() == "true" if success_raw is not None else None
    rows = storage.query_events(
        limit=limit,
        name=name or None,
        since=since,
        success=success,
        newest_first=True,
    )
    events = []
    for idx, r in enumerate(rows):
        events.append(
            {
                "id": r.get("id", idx + 1),
                "type": r.get("type"),
                "name": r.get("name"),
                "timestamp": r.get("timestamp"),
                "duration_ms": int(r.get("duration_ms") or 0),
                "success": bool(r.get("success")),
                "profile": r.get("profile"),
                "metadata": r.get("metadata") or {},
            }
        )
    return Response.json(200, {"total": len(events), "events": events})


@route("GET", "/api/backends")
def _backends(
    _: Request,
    proxy_factory: Callable[[], Any] | None = None,
) -> Response:
    """Return backend health while keeping collection failures server-side."""

    overview = status_overview().get("servers", {})
    totals = {
        "enabled": overview.get("enabled", 0),
        "disabled": overview.get("disabled", 0),
        "configured": overview.get("configured", 0),
        "missing_env": overview.get("missing_env", 0),
    }
    settings = load_settings()
    per_server: dict[str, dict[str, bool]] = {}
    for source in __import__("kater.profiles", fromlist=["all_tool_sources"]).all_tool_sources():
        if source.transport == "native":
            continue
        env_present = all(os.environ.get(v) for v in source.env)
        per_server[source.name] = {
            "enabled": settings.is_server_enabled(source.name, default=True),
            "configured": bool(env_present),
            "missing_env": not env_present,
        }
    result = []
    provider = proxy_factory or get_proxy
    try:
        statuses = provider().statuses()
    except Exception:
        from kater.api.server import _log

        _log.exception("failed to collect backend statuses")
        return Response.json(
            503,
            {
                "error": "backend_status_unavailable",
                "message": "Backend status collection failed; check gateway logs and retry.",
                "backends": [],
                "servers": [],
                "totals": totals,
            },
        )
    for status in statuses:
        d = status.to_dict()
        extra = per_server.get(d["name"], {})
        d["enabled"] = extra.get("enabled")
        d["configured"] = extra.get("configured")
        d["missing_env"] = extra.get("missing_env")
        result.append(d)
    return Response.json(
        200,
        {
            "backends": result,
            "servers": result,
            "totals": totals,
        },
    )


@route("GET", "/api/telemetry")
def _telemetry(_: Request) -> Response:
    events = load_events()
    return Response.json(200, {"total": len(events), "events": events})


@route("GET", "/api/evals")
def _evals(_: Request) -> Response:
    return Response.json(200, eval_summary())


@route("GET", "/api/catalog")
def _catalog(req: Request) -> Response:
    from kater.profiles import visible_tool_sources

    settings = load_settings()
    query = (req.query1("q") or "").strip().lower()
    profile = (req.query1("profile") or "").strip()
    transport = (req.query1("transport") or "").strip().lower()
    risk = (req.query1("risk") or "").strip().lower()
    results = []
    for source in visible_tool_sources():
        if source.transport == "native":
            continue
        if profile and profile != "core" and profile not in source.profiles:
            continue
        if transport and source.transport.value != transport:
            continue
        if risk and source.risk.value != risk:
            continue
        if query:
            haystack = f"{source.name} {source.description}".lower()
            if query not in haystack:
                continue
        env_ok = all(os.environ.get(v) for v in source.env)
        results.append(
            {
                "name": source.name,
                "description": source.description,
                "transport": source.transport.value,
                "risk": source.risk.value,
                "profiles": sorted(source.profiles),
                "env_required": source.env,
                "env_configured": env_ok,
                "enabled": settings.is_server_enabled(source.name, default=True),
                "homepage": source.homepage,
                "context_cost": source.context_cost,
            }
        )
    return Response.json(
        200,
        {
            "total": len(results),
            "servers": results,
            "by_transport": _group_by(results, "transport"),
            "by_risk": _group_by(results, "risk"),
        },
    )


@route("GET", "/api/spec")
def _spec(_: Request) -> Response:
    from kater.openapi_spec import generate_spec

    return Response.json(200, generate_spec())


# ── PR control-plane API (§3/§4/§6/§7) ────────────────────────────


@route("GET", "/api/pr/policy")
def _pr_policy(_: Request) -> Response:
    from kater.pr_control import pr_policy_tool

    return Response.json(200, pr_policy_tool())


@route("GET", "/api/pr/list")
def _pr_list(req: Request) -> Response:
    from kater.pr_control import pr_list_tool

    state = (req.query1("state") or "open").strip()
    try:
        limit = int(req.query1("limit") or "30")
    except (ValueError, TypeError):
        limit = 30
    try:
        return Response.json(200, pr_list_tool(state=state, limit=limit))
    except RuntimeError as exc:
        return Response.json(502, {"error": str(exc)})


@route("GET", "/api/pr/{number}/status")
def _pr_status(req: Request) -> Response:
    from kater.pr_control import pr_status_tool

    try:
        number = int(req.params.get("number") or "")
    except (ValueError, TypeError):
        return Response.json(400, {"error": "invalid pr number"})
    try:
        return Response.json(200, pr_status_tool(number))
    except RuntimeError as exc:
        return Response.json(502, {"error": str(exc)})


@route("GET", "/api/pr/{number}/gate")
def _pr_gate(req: Request) -> Response:
    from kater.pr_control import pr_gate_tool

    try:
        number = int(req.params.get("number") or "")
    except (ValueError, TypeError):
        return Response.json(400, {"error": "invalid pr number"})
    expected = (req.query1("expected_head_sha") or "").strip()
    try:
        return Response.json(200, pr_gate_tool(number, expected_head_sha=expected))
    except RuntimeError as exc:
        return Response.json(502, {"error": str(exc)})


@route("GET", "/api/pr/audit")
def _pr_audit(req: Request) -> Response:
    from kater.pr_control import pr_audit_tool

    try:
        limit = int(req.query1("limit") or "100")
    except (ValueError, TypeError):
        limit = 100
    raw_number = req.query1("pr_number")
    number = int(raw_number) if raw_number else 0
    return Response.json(200, pr_audit_tool(pr_number=number, limit=limit))


@route("POST", "/api/pr/{number}/merge")
def _pr_merge(req: Request) -> Response:
    from kater.pr_control import MergeRejected, pr_merge_tool

    try:
        number = int(req.params.get("number") or "")
    except (ValueError, TypeError):
        return Response.json(400, {"error": "invalid pr number"})

    body: dict[str, Any] = {}
    try:
        body = req.json
    except (ValueError, TypeError):
        body = {}

    expected = str(body.get("expected_head_sha", "") or "")
    actor = str(body.get("actor", "") or "")
    try:
        return Response.json(200, pr_merge_tool(number, expected_head_sha=expected, actor=actor))
    except MergeRejected as exc:
        return Response.json(409, {"error": str(exc), "rejected": True})
    except RuntimeError as exc:
        return Response.json(502, {"error": str(exc)})


@route("GET", "/api/export")
def _export(_: Request) -> Response:
    # Reuse the single sanitizer so this export can never drift back into
    # leaking secrets (api_keys, stored MCP server credentials).
    settings = load_settings()
    safe = settings.to_safe_dict()
    return Response.json(
        200,
        {
            "version": settings.version,
            "default_profile": settings.default_profile,
            "auth": safe["auth"],
            "server_overrides": safe["server_overrides"],
            "cors_origins": settings.cors_origins,
            "rate_limit_per_min": settings.rate_limit_per_min,
            "storage_backend": settings.storage_backend,
            "exported_at": time.time(),
        },
    )


# ── Mutation endpoints ─────────────────────────────────────────────


@route("POST", "/api/chains/run")
def _chain_run(req: Request) -> Response:
    body = req.json
    name = body.get("name", "")
    profile = body.get("profile", os.environ.get("KATER_PROFILE", "core"))
    for c in list_chains(profile):
        if c.name == name:
            record_chain_run(c.name, steps=len(c.steps), profile=profile)
            return Response.json(
                200,
                {
                    "chain": c.name,
                    "description": c.description,
                    "profile": profile,
                    "steps": [
                        {"step": i + 1, "tool": s.tool, "reason": s.reason}
                        for i, s in enumerate(c.steps)
                    ],
                },
            )
    record_chain_run(name, steps=0, success=False, profile=profile, error="not_found")
    return Response.json(404, {"error": f"Chain '{name}' not found for profile '{profile}'."})


@route("POST", "/api/mcp/servers/{name}/{action}")
def _server_action(req: Request) -> Response:
    name = req.params["name"]
    action = req.params["action"]
    source = _visible_source(name)
    if not source:
        return Response.json(404, {"error": f"Unknown server: {name}"})
    settings = load_settings()
    if action == "enable":
        settings.set_server_enabled(name, True)
        save_settings(settings)
        record_server_toggle(name, action, True)
        _ws_broadcast("server_enabled", {"name": name})
        return Response.json(200, {"name": name, "enabled": True})
    if action == "disable":
        settings.set_server_enabled(name, False)
        save_settings(settings)
        record_server_toggle(name, action, False)
        _ws_broadcast("server_disabled", {"name": name})
        return Response.json(200, {"name": name, "enabled": False})
    if action == "toggle":
        current = settings.is_server_enabled(name, default=True)
        settings.set_server_enabled(name, not current)
        save_settings(settings)
        record_server_toggle(name, action, not current)
        _ws_broadcast("server_toggled", {"name": name, "enabled": not current})
        return Response.json(200, {"name": name, "enabled": not current})
    return Response.json(400, {"error": f"Unknown action: {action}"})


@route("POST", "/api/mcp/servers/{name}/credentials")
def _server_credentials(req: Request) -> Response:
    # Store the credentials a server needs to connect. Only env vars the server
    # actually declares are accepted (no arbitrary env injection), values are
    # applied to the live process and persisted (gitignored .kater/settings.json).
    name = req.params["name"]
    source = _visible_source(name)
    if not source:
        return Response.json(404, {"error": f"Unknown server: {name}"})

    body = req.json
    env = body.get("env")
    if not isinstance(env, dict):
        return Response.json(400, {"error": "Body must include an 'env' object."})

    declared = set(source.env)
    for key in env:
        if key not in declared:
            return Response.json(400, {"error": f"{name} does not use credential '{key}'."})

    settings = load_settings()
    override = settings.server_overrides.get(name) or ServerOverride()
    applied: list[str] = []
    for key, value in env.items():
        text = str(value or "").strip()
        if text:
            override.env[key] = text
            os.environ[key] = text
            applied.append(key)
        else:
            override.env.pop(key, None)
            # Clearing must also drop it from the live process, otherwise
            # env_configured below would still read the old value as "set".
            os.environ.pop(key, None)
    settings.server_overrides[name] = override
    save_settings(settings)

    env_present = all(os.environ.get(v) for v in source.env)
    _ws_broadcast("server_credentials", {"name": name, "env_configured": env_present})
    return Response.json(200, {"name": name, "env_configured": env_present, "applied": applied})


@route("GET", "/api/tunnel")
def _tunnel_status(_: Request) -> Response:
    return Response.json(200, tunnel_overview())


@route("POST", "/api/tunnel/{provider}/start")
def _tunnel_start(req: Request) -> Response:
    provider = req.params["provider"]
    if provider == "cloudflare":
        info = start_cloudflared()
    elif provider == "tailscale":
        info = start_tailscale_funnel()
    else:
        return Response.json(400, {"error": f"Unknown tunnel provider: {provider}"})
    return Response.json(200, info.to_dict())


@route("POST", "/api/tunnel/{provider}/stop")
def _tunnel_stop(req: Request) -> Response:
    provider = req.params["provider"]
    if provider == "cloudflare":
        ok = stop_cloudflared()
    elif provider == "tailscale":
        ok = stop_tailscale_funnel()
    else:
        return Response.json(400, {"error": f"Unknown tunnel provider: {provider}"})
    return Response.json(200, {"provider": provider, "stopped": ok, "running": False})


@route("POST", "/api/settings")
def _update_settings(req: Request) -> Response:
    from kater.api.server import _reset_rate_limiter
    from kater.settings import check_admin

    body = req.json
    settings = load_settings()
    # Sensitive settings mutations (auth mode, CORS, rate limit, api_keys)
    # require the operator/admin credential when KATER_ADMIN_KEY is set, so a
    # compromised tool-credential cannot weaken the gateway.
    if not check_admin(req.header("authorization"), settings):
        return Response.json(403, {"error": "admin credential required for settings changes"})

    if "auth" in body:
        auth_patch = body["auth"]
        if not isinstance(auth_patch, dict):
            return Response.json(400, {"error": "auth must be an object"})
        current = settings.auth.model_dump()
        current.update({k: v for k, v in auth_patch.items() if k in current})
        settings.auth = type(settings.auth).model_validate(current)
    if "cors_origins" in body:
        from kater.settings import sanitize_header_value

        settings.cors_origins = [
            sanitize_header_value(str(origin)) for origin in body["cors_origins"]
        ]
    if "rate_limit_per_min" in body:
        try:
            settings.rate_limit_per_min = int(body["rate_limit_per_min"])
        except (TypeError, ValueError):
            return Response.json(400, {"error": "rate_limit_per_min must be an integer"})
        _reset_rate_limiter()
    if "default_profile" in body:
        settings.default_profile = body["default_profile"]
    if "storage_backend" in body:
        backend = body["storage_backend"]
        if backend not in ("sqlite", "jsonl"):
            return Response.json(400, {"error": "storage_backend must be sqlite or jsonl"})
        settings.storage_backend = backend
    unsafe = unsafe_public_settings_override_enabled()
    if is_public_settings(settings) and not unsafe:
        if settings.auth.mode == "none":
            return Response.json(
                400,
                {"error": "auth.mode=none is blocked in public mode"},
            )
        if "*" in settings.cors_origins:
            return Response.json(
                400,
                {"error": "cors_origins=['*'] is blocked in public mode"},
            )
        if settings.rate_limit_per_min <= 0:
            return Response.json(
                400,
                {"error": "rate_limit_per_min=0 is blocked in public mode"},
            )
    save_settings(settings)
    return Response.json(200, settings.to_safe_dict())
