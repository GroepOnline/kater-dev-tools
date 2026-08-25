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
from kater.authgate import capability_allowed, resolve_request_identity
from kater.automations import get_engine
from kater.browser.models import BrowserAction
from kater.browser.policy import PolicyViolation
from kater.browser.providers import BrowserUnavailableError, probe_providers
from kater.browser.session import (
    SessionLimitError,
    UnknownSessionError,
    get_manager,
)
from kater.capabilities.wiring import computer_status, get_computer_connector
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
    persisted_env_keys,
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


def _catalog_admin_denied(req: Request) -> Response | None:
    """Fail closed unless the caller holds the operator admin credential."""
    from kater.settings import check_admin

    settings = load_settings()
    if not check_admin(req.header("authorization"), settings):
        return Response.json(403, {"error": "admin credential required for catalog mutations"})
    return None


def _secret_persist_denied(req: Request) -> Response | None:
    """Admin gate plus deny-default local settings persist policy."""
    denied = _catalog_admin_denied(req)
    if denied:
        return denied
    from kater.secret_persist import connect_secret_decision

    decision = connect_secret_decision(load_settings())
    if not decision.allowed:
        return Response.json(403, decision.as_error())
    return None


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
        servers.append(_server_doc(source, settings, include_mcp=True))
    return {"total": len(servers), "servers": servers}


def _server_doc(
    source: Any,
    settings: Any | None = None,
    *,
    include_mcp: bool = False,
    include_context_cost: bool = False,
) -> dict[str, Any]:
    from kater.connect import public_oauth, source_is_configured

    settings = settings or load_settings()
    oauth = public_oauth(source, settings)
    doc: dict[str, Any] = {
        "name": source.name,
        "description": source.description,
        "transport": source.transport.value,
        "risk": source.risk.value,
        "profiles": sorted(source.profiles),
        "env_required": source.env,
        "env_configured": source_is_configured(source, settings),
        "homepage": source.homepage,
        "enabled": settings.is_server_enabled(source.name, default=True),
        "oauth": oauth,
        "connections": (oauth or {}).get("connections") or [],
    }
    if include_mcp:
        doc["mcp"] = source.mcp.model_dump() if source.mcp else None
    if include_context_cost:
        doc["context_cost"] = source.context_cost
    return doc


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


@route("GET", "/health/live", public=True)
def _health_live(_: Request) -> Response:
    from kater import __version__

    # Liveness: the process/API responds. Optional providers must not fail this,
    # and neither must settings I/O -- a transiently unreadable config file must
    # not make an orchestrator conclude the process is dead.
    try:
        auth_mode = load_settings().auth.mode
    except Exception:
        auth_mode = "unknown"
    return Response.json(
        200,
        {"status": "ok", "version": __version__, "auth_mode": auth_mode},
    )


def _mcp_listener_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    """Bounded TCP connect against the MCP SSE listener.

    The MCP surface runs on its own port and can be down while the API is up, so
    readiness must observe it instead of assuming it. Kept to a short timeout so
    /health/ready stays cheap.
    """
    import ipaddress
    import socket

    target = host
    try:
        # A wildcard bind is not connectable; probe it over loopback instead.
        if not host or ipaddress.ip_address(host).is_unspecified:
            target = "127.0.0.1"
    except ValueError:
        pass
    try:
        with socket.create_connection((target, port), timeout=timeout):
            return True
    except OSError:
        return False


@route("GET", "/health/ready", public=True)
def _health_ready(_: Request) -> Response:
    from pathlib import Path

    from kater import __version__

    components: dict[str, dict[str, str]] = {"api": {"status": "ok"}}
    degraded = False
    unhealthy = False

    # Readiness must report on settings failures rather than 500 out of the probe.
    settings = None
    try:
        settings = load_settings()
        auth_mode = settings.auth.mode
        components["settings"] = {"status": "ok"}
    except Exception as exc:
        auth_mode = "unknown"
        components["settings"] = {
            "status": "unavailable",
            "reason": f"settings_load_failed:{type(exc).__name__}",
        }
        unhealthy = True

    if settings is not None and _mcp_listener_reachable(settings.host, settings.mcp_port):
        components["mcp"] = {"status": "ok"}
    else:
        components["mcp"] = {
            "status": "unavailable",
            "reason": "mcp_listener_unreachable",
        }
        degraded = True

    # UTRECHT_REPO_PATH is optional in current live env; when unset the Utrecht
    # CLI tools degrade, but the gateway itself remains up. Report that clearly.
    utrecht_path = os.environ.get("UTRECHT_REPO_PATH")
    if utrecht_path and not Path(utrecht_path).expanduser().exists():
        components["utrecht"] = {
            "status": "unavailable",
            "reason": "repository_provider_unavailable",
        }
        degraded = True
    elif utrecht_path:
        components["utrecht"] = {"status": "ok"}
    else:
        components["utrecht"] = {
            "status": "degraded",
            "reason": "UTRECHT_REPO_PATH_unset_optional",
        }
        degraded = True

    fleet_path = os.environ.get("UTRECHT_FLEET_INVENTORY_PATH")
    if not fleet_path:
        components["fleet_cache"] = {
            "status": "degraded",
            "reason": "UTRECHT_FLEET_INVENTORY_PATH_unset_optional",
        }
        degraded = True
    elif not Path(fleet_path).expanduser().exists():
        components["fleet_cache"] = {
            "status": "unavailable",
            "reason": "fleet_inventory_missing",
        }
        degraded = True
    else:
        components["fleet_cache"] = {"status": "ok"}

    # CI health is remote (ubuntu@bc-scan-2); this endpoint only reports whether
    # the SSH target env is configured, not a live probe (to keep /ready cheap).
    if os.environ.get("UTRECHT_CI_HEALTH_SSH_TARGET") and os.environ.get(
        "UTRECHT_CI_HEALTH_REMOTE_REPO"
    ):
        components["ci_health"] = {"status": "ok", "reason": "env_configured_not_probed"}
    else:
        components["ci_health"] = {
            "status": "unavailable",
            "reason": "ci_health_env_missing",
        }
        degraded = True

    status = "unhealthy" if unhealthy else "degraded" if degraded else "ok"

    return Response.json(
        200,
        {
            "status": status,
            "service": "kater",
            "version": __version__,
            "auth_mode": auth_mode,
            "components": components,
        },
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
        f"{_CONSENT_COOKIE}={consent_nonce}; Path=/authorize; HttpOnly; SameSite=Lax; "
        f"Max-Age={_CONSENT_TTL_SECONDS}"
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
    return Response.json(200, _server_doc(source, settings, include_mcp=True))


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
            {"error": f"Unknown format '{fmt}'. Available: {', '.join(sorted(known))}"},
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
    from kater.connect import source_is_configured

    per_server: dict[str, dict[str, bool]] = {}
    for source in __import__("kater.profiles", fromlist=["all_tool_sources"]).all_tool_sources():
        if source.transport == "native":
            continue
        env_present = source_is_configured(source, settings)
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
        results.append(_server_doc(source, settings, include_context_cost=True))
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


def _pr_transport_error(exc: Exception) -> Response:
    from kater.github_transport import github_error_payload

    return Response.json(502, github_error_payload(exc))


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
    repo = (req.query1("repo") or "").strip()
    try:
        return Response.json(200, pr_list_tool(state=state, limit=limit, repo=repo))
    except RuntimeError as exc:
        return _pr_transport_error(exc)


@route("GET", "/api/pr/{number}/status")
def _pr_status(req: Request) -> Response:
    from kater.pr_control import pr_status_tool

    try:
        number = int(req.params.get("number") or "")
    except (ValueError, TypeError):
        return Response.json(400, {"error": "invalid pr number"})
    repo = (req.query1("repo") or "").strip()
    try:
        return Response.json(200, pr_status_tool(number, repo=repo))
    except RuntimeError as exc:
        return _pr_transport_error(exc)


@route("GET", "/api/pr/{number}/gate")
def _pr_gate(req: Request) -> Response:
    from kater.pr_control import pr_gate_tool

    try:
        number = int(req.params.get("number") or "")
    except (ValueError, TypeError):
        return Response.json(400, {"error": "invalid pr number"})
    expected = (req.query1("expected_head_sha") or "").strip()
    repo = (req.query1("repo") or "").strip()
    try:
        return Response.json(200, pr_gate_tool(number, expected_head_sha=expected, repo=repo))
    except RuntimeError as exc:
        return _pr_transport_error(exc)


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
    repo = str(body.get("repo", "") or req.query1("repo") or "")
    try:
        return Response.json(
            200,
            pr_merge_tool(number, expected_head_sha=expected, actor=actor, repo=repo),
        )
    except MergeRejected as exc:
        return Response.json(409, {"error": str(exc), "rejected": True})
    except RuntimeError as exc:
        return _pr_transport_error(exc)


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
            from kater.connectors.auth import redact_text
            from kater.connectors.chain_guard import assert_chain_runnable
            from kater.connectors.errors import ConnectorError

            try:
                assert_chain_runnable(c.steps, profile=profile)
            except ConnectorError as exc:
                record_chain_run(
                    c.name,
                    steps=len(c.steps),
                    success=False,
                    profile=profile,
                    error=exc.code,
                )
                payload = exc.as_dict()
                payload["message"] = redact_text(str(payload.get("message") or exc))
                return Response.json(409, payload)
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


# ── connector catalog (behind the 17 native tools) ─────────────────


def _connector_error_response(exc: Exception) -> Response:
    """Map a ConnectorError to an admin-safe, redacted HTTP response."""
    from kater.connectors.auth import redact_text
    from kater.connectors.errors import ConnectorError

    if not isinstance(exc, ConnectorError):
        return Response.json(500, {"error": "connector_error", "message": "internal error"})
    status = {
        "connector_not_found": 404,
        "duplicate_connector": 409,
        "auth_missing": 409,
        "policy_blocked": 403,
        "capability_missing": 404,
        "invalid_connector": 400,
    }.get(exc.code, 409)
    payload = exc.as_dict()
    payload["message"] = redact_text(str(payload.get("message") or exc))
    return Response.json(status, payload)


@route("GET", "/api/connectors")
def _connectors_list(req: Request) -> Response:
    from kater.connectors.registry import inventory
    from kater.connectors.seed import seed_builtin_connectors

    profile = req.query1("profile") or "core"
    seed_builtin_connectors()
    views = [view.as_dict() for view in inventory(profile)]
    return Response.json(200, {"profile": profile, "total": len(views), "connectors": views})


@route("POST", "/api/connectors/{connector_id}/{action}")
def _connector_action(req: Request) -> Response:
    denied = _catalog_admin_denied(req)
    if denied:
        return denied
    connector_id = req.params["connector_id"]
    action = req.params["action"]
    try:
        body = req.json or {}
    except ValueError:
        return Response.json(400, {"error": "invalid JSON body"})
    from kater.connectors.errors import ConnectorError
    from kater.connectors.models import PermissionLevel
    from kater.connectors.seed import seed_builtin_connectors

    seed_builtin_connectors()
    try:
        if action == "validate":
            from kater.connectors.registry import validate

            return Response.json(200, validate(connector_id).as_dict())
        if action == "enable":
            from kater.connectors.registry import enable

            profile = str(body.get("profile") or "core")
            level_raw = str(body.get("level") or "read").strip().lower()
            try:
                level = PermissionLevel(level_raw)
            except ValueError:
                return Response.json(400, {"error": f"invalid level: {level_raw!r}"})
            return Response.json(200, enable(connector_id, profile=profile, level=level).as_dict())
        if action == "disable":
            from kater.connectors.registry import disable

            return Response.json(200, disable(connector_id).as_dict())
        if action == "invoke":
            from kater.connectors.registry import invoke

            capability_id = str(body.get("capability") or "")
            if not capability_id:
                return Response.json(400, {"error": "body must include 'capability'"})
            arguments = body.get("arguments") or {}
            if not isinstance(arguments, dict):
                return Response.json(400, {"error": "'arguments' must be an object"})
            profile = str(body.get("profile") or "core")
            result = invoke(connector_id, capability_id, arguments, profile=profile)
            return Response.json(200, result)
    except ConnectorError as exc:
        return _connector_error_response(exc)
    return Response.json(400, {"error": f"Unknown action: {action}"})


@route("POST", "/api/mcp/servers/{name}/credentials")
def _server_credentials(req: Request) -> Response:
    # Store the credentials a server needs to connect. Only env vars the server
    # actually declares (including OAuth client/token keys) are accepted.
    # Persist to gitignored .kater/settings.json is deny-default.
    denied = _secret_persist_denied(req)
    if denied:
        return denied
    name = req.params["name"]
    source = _visible_source(name)
    if not source:
        return Response.json(404, {"error": f"Unknown server: {name}"})

    body = req.json
    env = body.get("env")
    if not isinstance(env, dict):
        return Response.json(400, {"error": "Body must include an 'env' object."})

    from kater.connect import (
        declared_credential_keys,
        source_is_configured,
        upsert_connection,
    )

    declared = declared_credential_keys(source)
    for key in env:
        if key not in declared:
            return Response.json(400, {"error": f"{name} does not use credential '{key}'."})

    settings = load_settings()
    override = settings.server_overrides.get(name) or ServerOverride()
    applied: list[str] = []
    cleaned: dict[str, str] = {}
    cleared: set[str] = set()
    for key, value in env.items():
        text = str(value or "").strip()
        if text:
            override.env[key] = text
            _remember_runtime_env(key, text)
            applied.append(key)
            cleaned[key] = text
        else:
            override.env.pop(key, None)
            cleared.add(key)
    settings.server_overrides[name] = override
    label = str(body.get("label") or "").strip()
    token_key = source.oauth.token_env if source.oauth else None
    if token_key and cleaned.get(token_key):
        upsert_connection(settings, name, cleaned, label=label or "manual")
    elif cleared:
        # Empty fields clear that env key only. Account removal is DELETE.
        _forget_runtime_env(cleared)
    save_settings(settings)

    env_present = source_is_configured(source, settings)
    try:
        get_proxy().sync_source(source)
    except Exception:
        from kater.api.server import _log

        _log.exception("failed to sync %s after credentials", name)
    _ws_broadcast("server_credentials", {"name": name, "env_configured": env_present})
    return Response.json(200, {"name": name, "env_configured": env_present, "applied": applied})


@route("POST", "/api/mcp/servers/{name}/oauth/start")
def _server_oauth_start(req: Request) -> Response:
    denied = _catalog_admin_denied(req)
    if denied:
        return denied
    name = req.params["name"]
    source = _visible_source(name)
    if not source or not source.oauth:
        return Response.json(404, {"error": f"{name} does not support OAuth connect."})

    from kater.connect import oauth_client_configured, resolve_oauth_client
    from kater.connect_policy import (
        ConnectOriginError,
        connect_secret_decision,
        resolve_connect_base_url,
    )
    from kater.mcp_oauth import redirect_uri, slack_app_manifest, start_authorize

    settings = load_settings()
    try:
        base = resolve_connect_base_url(req.base_url, settings)
    except ConnectOriginError as exc:
        return Response.json(400, {"error": exc.reason})
    decision = connect_secret_decision(settings)
    if not decision.allowed:
        return Response.json(403, decision.as_error())

    callback = redirect_uri(base)
    if not oauth_client_configured(source):
        setup: dict[str, Any] = {
            "redirect_uri": callback,
            "client_id_env": source.oauth.client_id_env,
            "client_secret_env": source.oauth.client_secret_env,
        }
        if source.oauth.provider == "slack":
            setup["manifest"] = slack_app_manifest(callback, source)
        elif source.oauth.provider == "microsoft":
            setup["notes"] = (
                "Register a Microsoft Entra app (public client + PKCE). "
                f"Redirect URI: {callback}. Scopes: " + " ".join(source.oauth.scopes)
            )
        return Response.json(
            409,
            {
                "error": "oauth_app_missing",
                "message": (
                    f"Create a {source.oauth.provider} app once, then paste "
                    f"{source.oauth.client_id_env} via Connect."
                ),
                "setup": setup,
            },
        )

    body = req.json if req.raw_body else {}
    label = str(body.get("label") or "").strip()
    client_id, _secret = resolve_oauth_client(source)
    try:
        started = start_authorize(source, client_id=client_id, base_url=base, label=label)
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, started)


_oauth_runtime_env: set[str] = set()


def _remember_runtime_env(key: str, value: str) -> None:
    """Record a credential the gateway itself wrote into the process env."""
    os.environ[key] = value
    _oauth_runtime_env.add(key)
    persisted_env_keys.add(key)


def _forget_runtime_env(keys: set[str]) -> None:
    """Drop gateway-written credentials; leave systemd/secret-manager env alone."""
    for key in keys:
        if key in _oauth_runtime_env or key in persisted_env_keys:
            os.environ.pop(key, None)
            _oauth_runtime_env.discard(key)
            persisted_env_keys.discard(key)


@route("GET", "/api/mcp/oauth/callback", public=True)
def _mcp_oauth_callback(req: Request) -> Response:
    from urllib.parse import urlencode

    from kater.connect import resolve_oauth_client, upsert_connection
    from kater.connect_policy import (
        ConnectOriginError,
        connect_secret_decision,
        resolve_connect_base_url,
        safe_catalog_url,
    )
    from kater.mcp_oauth import (
        abandon_pending,
        callback_html,
        consume_callback,
        peek_pending,
        redirect_uri,
    )

    settings = load_settings()
    error = (req.query1("error") or "").strip()
    catalog = safe_catalog_url(req.base_url, settings)
    if error:
        page = callback_html(
            server="",
            label="",
            catalog_url=catalog + "&filter=needs",
            error=error,
        )
        return Response.html(400, page)

    state = (req.query1("state") or "").strip()
    code = (req.query1("code") or "").strip()
    if not state or not code:
        return Response.html(
            400,
            callback_html(server="", label="", catalog_url=catalog, error="missing code"),
        )

    preview = peek_pending(state)
    server_name = str(preview.get("server") or "")
    source = _visible_source(server_name) if server_name else None
    pending_redirect = str(preview.get("redirect_uri") or "")
    catalog = safe_catalog_url(req.base_url, settings, pending_redirect=pending_redirect or None)
    if not source or not source.oauth:
        page = callback_html(
            server=server_name or "unknown",
            label="",
            catalog_url=catalog,
            error="unknown OAuth session",
        )
        return Response.html(400, page)

    decision = connect_secret_decision(settings)
    if not decision.allowed:
        abandon_pending(state)
        page = callback_html(
            server=source.name,
            label="",
            catalog_url=catalog,
            error="secret storage is not enabled",
        )
        return Response.html(403, page)

    try:
        base = resolve_connect_base_url(
            req.base_url, settings, pending_redirect=pending_redirect or None
        )
    except ConnectOriginError:
        abandon_pending(state)
        page = callback_html(
            server=source.name,
            label="",
            catalog_url=catalog,
            error="invalid connect origin",
        )
        return Response.html(400, page)
    expected_callback = redirect_uri(base)
    if pending_redirect and pending_redirect != expected_callback:
        abandon_pending(state)
        page = callback_html(
            server=source.name,
            label="",
            catalog_url=catalog,
            error="oauth redirect mismatch",
        )
        return Response.html(400, page)

    client_id, client_secret = resolve_oauth_client(source)
    try:
        result = consume_callback(
            state=state,
            code=code,
            client_id=client_id,
            client_secret=client_secret,
            token_url=source.oauth.token_url,
            pkce=source.oauth.pkce,
        )
    except ValueError as exc:
        page = callback_html(
            server=source.name,
            label="",
            catalog_url=catalog,
            error=str(exc),
        )
        return Response.html(400, page)

    env = {source.oauth.token_env: result["access_token"]}
    if result.get("refresh_token") and source.oauth.refresh_env:
        env[source.oauth.refresh_env] = result["refresh_token"]
    extra = result.get("extra") or {}
    if extra.get("team_id"):
        env["SLACK_TEAM_ID"] = str(extra["team_id"])
    had_connections = bool(
        settings.server_overrides.get(source.name)
        and settings.server_overrides[source.name].connections
    )
    conn = upsert_connection(
        settings,
        source.name,
        env,
        label=str(result.get("label") or extra.get("team") or ""),
        extra=extra,
    )
    if not had_connections:
        _remember_runtime_env(source.oauth.token_env, result["access_token"])
    save_settings(settings)
    try:
        get_proxy().sync_source(source)
    except Exception:
        from kater.api.server import _log

        _log.exception("failed to sync %s after oauth callback", source.name)
    qs = urlencode({"view": "catalog", "server": source.name, "connected": conn.id})
    dest = safe_catalog_url(
        req.base_url, settings, pending_redirect=pending_redirect or None, query=qs
    )
    page = callback_html(
        server=source.name,
        label=conn.label,
        catalog_url=dest,
    )
    return Response.html(200, page)


@route("GET", "/api/mcp/servers/{name}/connections")
def _server_connections(req: Request) -> Response:
    source = _visible_source(req.params["name"])
    if not source:
        return Response.json(404, {"error": f"Unknown server: {req.params['name']}"})
    from kater.connect import public_oauth

    oauth = public_oauth(source) or {"connections": []}
    return Response.json(200, {"name": source.name, "connections": oauth.get("connections") or []})


@route("DELETE", "/api/mcp/servers/{name}/connections/{conn_id}")
def _server_connection_delete(req: Request) -> Response:
    denied = _catalog_admin_denied(req)
    if denied:
        return denied
    name = req.params["name"]
    source = _visible_source(name)
    if not source:
        return Response.json(404, {"error": f"Unknown server: {name}"})
    from kater.connect import list_connections, remove_connection, source_is_configured

    settings = load_settings()
    conn_id = req.params["conn_id"]
    existing = next((c for c in list_connections(source, settings) if c.id == conn_id), None)
    removed = remove_connection(settings, name, conn_id, source)
    if not removed:
        return Response.json(404, {"error": "Unknown connection"})
    forget = set(existing.env) if existing else set()
    forget |= set(source.env)
    if source.oauth:
        forget.add(source.oauth.token_env)
        if source.oauth.refresh_env:
            forget.add(source.oauth.refresh_env)
    override = settings.server_overrides.get(name)
    remaining = {key for conn in (override.connections if override else []) for key in conn.env}
    _forget_runtime_env(forget - remaining)
    if override and override.connections:
        for key, value in override.connections[0].env.items():
            if value:
                _remember_runtime_env(key, value)
    save_settings(settings)
    try:
        get_proxy().sync_source(source)
    except Exception:
        from kater.api.server import _log

        _log.exception("failed to sync %s after disconnect", name)
    return Response.json(
        200,
        {
            "name": name,
            "removed": req.params["conn_id"],
            "env_configured": source_is_configured(source, settings),
        },
    )


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
    settings = load_settings().model_copy(deep=True)
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


# ── Native browser lane ────────────────────────────────────────────


def _truthy_query(req: Request, key: str) -> bool:
    raw = (req.query1(key) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _capability_denied(capability_id: str) -> Response:
    return Response.json(
        403,
        {
            "error": f"capability {capability_id!r} denied: not in context allowlist",
            "code": "capability_denied",
            "capability_id": capability_id,
        },
    )


def _require_capability(req: Request, capability_id: str) -> Response | None:
    identity = resolve_request_identity(req)
    if not capability_allowed(capability_id, identity.allowed_capabilities):
        return _capability_denied(capability_id)
    return None


# Errors from the browser lane that map to a 400 Bad Request response.
_BROWSER_400_ERRORS = (SessionLimitError, BrowserUnavailableError, PolicyViolation, ValueError)


@route("GET", "/api/browser/providers")
def _browser_providers(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_providers"):
        return denied
    return Response.json(200, {"providers": [info.to_dict() for info in probe_providers()]})


@route("GET", "/api/browser/sessions")
def _browser_list_sessions(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_sessions"):
        return denied
    manager = get_manager()
    live_only = _truthy_query(req, "live_only")
    return Response.json(
        200,
        {
            "sessions": [s.to_dict() for s in manager.list_sessions(live_only=live_only)],
            "stats": manager.stats(),
        },
    )


@route("POST", "/api/browser/sessions")
def _browser_create_session(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_open"):
        return denied
    try:
        body = req.json
    except ValueError:
        return Response.json(400, {"error": "malformed JSON body"})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "JSON body must be an object"})
    try:
        width = int(body.get("width") or 1280)
        height = int(body.get("height") or 800)
        session = get_manager().create(
            label=body.get("label"),
            profile=str(body.get("profile") or "core"),
            viewport=(width, height),
        )
    except _BROWSER_400_ERRORS as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, {"session": session.to_dict()})


@route("GET", "/api/browser/sessions/{session_id}")
def _browser_get_session(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_sessions"):
        return denied
    session_id = req.params["session_id"]
    session = get_manager().get(session_id)
    if session is None:
        return Response.json(404, {"error": f"unknown session: {session_id}"})
    return Response.json(200, session.to_dict())


@route("DELETE", "/api/browser/sessions/{session_id}")
def _browser_close_session(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_close"):
        return denied
    session_id = req.params["session_id"]
    try:
        session = get_manager().close(session_id)
    except UnknownSessionError:
        return Response.json(404, {"error": f"unknown session: {session_id}"})
    except _BROWSER_400_ERRORS as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, {"session": session.to_dict()})


@route("POST", "/api/browser/sessions/{session_id}/act")
def _browser_act(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_act"):
        return denied
    session_id = req.params["session_id"]
    try:
        body = req.json
    except ValueError:
        return Response.json(400, {"error": "malformed JSON body"})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "JSON body must be an object"})
    payload = {k: v for k, v in body.items() if k != "session_id"}
    manager = get_manager()
    if manager.get(session_id) is None:
        return Response.json(404, {"error": f"unknown session: {session_id}"})
    try:
        action = BrowserAction.from_dict(payload)
        result = manager.act(session_id, action)
    except UnknownSessionError:
        return Response.json(404, {"error": f"unknown session: {session_id}"})
    except _BROWSER_400_ERRORS as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, result.to_dict())


@route("POST", "/api/browser/sessions/{session_id}/screenshot")
def _browser_screenshot(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_screenshot"):
        return denied
    session_id = req.params["session_id"]
    try:
        body = req.json
    except ValueError:
        return Response.json(400, {"error": "malformed JSON body"})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "JSON body must be an object"})
    manager = get_manager()
    if manager.get(session_id) is None:
        return Response.json(404, {"error": f"unknown session: {session_id}"})
    try:
        result = manager.screenshot(session_id, full_page=bool(body.get("full_page", False)))
    except UnknownSessionError:
        return Response.json(404, {"error": f"unknown session: {session_id}"})
    except _BROWSER_400_ERRORS as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, result.to_dict())


@route("GET", "/api/browser/stats")
def _browser_stats(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_sessions"):
        return denied
    return Response.json(200, get_manager().stats())


@route("DELETE", "/api/browser/sessions")
def _browser_close_all(req: Request) -> Response:
    if denied := _require_capability(req, "kater_browser_close"):
        return denied
    try:
        closed = get_manager().close_all()
    except _BROWSER_400_ERRORS as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, {"closed": closed})


# ── Automations ────────────────────────────────────────────────────


@route("GET", "/api/automations")
def _automations_list(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.list"):
        return denied
    engine = get_engine()
    engine.ensure_defaults()
    items = [item.to_dict() for item in engine.list()]
    return Response.json(200, {"automations": items, "total": len(items)})


@route("GET", "/api/automations/{id}")
def _automations_get(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.get"):
        return denied
    automation = get_engine().get(req.params["id"])
    if automation is None:
        return Response.json(404, {"error": "automation not found"})
    return Response.json(200, automation.to_dict())


@route("POST", "/api/automations")
def _automations_upsert(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.upsert"):
        return denied
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    name = str(body.get("name") or "").strip()
    kind = str(body.get("kind") or "").strip()
    if not name or not kind:
        return Response.json(400, {"error": "name and kind are required"})
    config = body.get("config")
    if config is not None and not isinstance(config, dict):
        return Response.json(400, {"error": "config must be an object"})
    try:
        automation = get_engine().upsert(
            id=str(body["id"]) if body.get("id") else None,
            name=name,
            kind=kind,
            enabled=bool(body.get("enabled", True)),
            schedule_seconds=int(body.get("schedule_seconds") or 0),
            config=config if isinstance(config, dict) else None,
        )
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    _ws_broadcast(
        "automation_upsert",
        {"id": automation.id, "kind": automation.kind, "enabled": automation.enabled},
    )
    return Response.json(200, automation.to_dict())


@route("POST", "/api/automations/{id}/run")
def _automations_run(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.run"):
        return denied
    automation_id = req.params["id"]
    try:
        result = get_engine().run_now(automation_id)
    except KeyError:
        return Response.json(404, {"error": "automation not found"})
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, result.to_dict())


@route("POST", "/api/automations/{id}/enable")
def _automations_enable(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.enable"):
        return denied
    automation = get_engine().set_enabled(req.params["id"], True)
    if automation is None:
        return Response.json(404, {"error": "automation not found"})
    _ws_broadcast("automation_enabled", {"id": automation.id})
    return Response.json(200, automation.to_dict())


@route("POST", "/api/automations/{id}/disable")
def _automations_disable(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.disable"):
        return denied
    automation = get_engine().set_enabled(req.params["id"], False)
    if automation is None:
        return Response.json(404, {"error": "automation not found"})
    _ws_broadcast("automation_disabled", {"id": automation.id})
    return Response.json(200, automation.to_dict())


@route("PATCH", "/api/automations/{id}")
def _automations_patch(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.update"):
        return denied
    automation_id = req.params["id"]
    engine = get_engine()
    existing = engine.get(automation_id)
    if existing is None:
        return Response.json(404, {"error": "automation not found"})
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    if "enabled" in body and len(body) == 1:
        automation = engine.set_enabled(automation_id, bool(body["enabled"]))
        if automation is None:
            return Response.json(404, {"error": "automation not found"})
        _ws_broadcast("automation_upserted", {"automation": automation.to_dict()})
        return Response.json(200, automation.to_dict())
    name = str(body["name"]).strip() if body.get("name") is not None else existing.name
    kind = str(body["kind"]).strip() if body.get("kind") is not None else existing.kind
    config = body.get("config", existing.config)
    if config is not None and not isinstance(config, dict):
        return Response.json(400, {"error": "config must be an object"})
    try:
        automation = engine.upsert(
            id=automation_id,
            name=name,
            kind=kind,
            enabled=bool(body.get("enabled", existing.enabled)),
            schedule_seconds=(
                existing.schedule_seconds
                if body.get("schedule_seconds") is None
                else int(body["schedule_seconds"])
            ),
            config=config if isinstance(config, dict) else existing.config,
        )
    except (TypeError, ValueError) as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(200, automation.to_dict())


@route("DELETE", "/api/automations/{id}")
def _automations_delete(req: Request) -> Response:
    if denied := _require_capability(req, "kater.automations.delete"):
        return denied
    automation_id = req.params["id"]
    if not get_engine().delete(automation_id):
        return Response.json(404, {"error": "automation not found"})
    _ws_broadcast("automation_deleted", {"id": automation_id})
    return Response.json(200, {"deleted": True, "id": automation_id})


# ── Computer lane (guest HTTP connector) ───────────────────────────


@route("GET", "/api/computer")
def _computer_status(req: Request) -> Response:
    payload = computer_status()
    identity = resolve_request_identity(req)
    if identity.allowed_capabilities is not None:
        allowed_ids = [
            cap_id
            for cap_id in payload["capability_ids"]
            if capability_allowed(cap_id, identity.allowed_capabilities)
        ]
        payload = {
            **payload,
            "capability_ids": allowed_ids,
            "capability_count": len(allowed_ids),
        }
    return Response.json(200, payload)


@route("GET", "/api/computer/capabilities")
def _computer_capabilities(req: Request) -> Response:
    connector = get_computer_connector()
    if connector is None:
        return Response.json(200, {"tools": [], "total": 0})
    tools = connector.list_tools()
    identity = resolve_request_identity(req)
    if identity.allowed_capabilities is not None:
        tools = [
            tool
            for tool in tools
            if capability_allowed(str(tool["name"]), identity.allowed_capabilities)
        ]
    return Response.json(200, {"tools": tools, "total": len(tools)})


@route("POST", "/api/computer/invoke")
def _computer_invoke(req: Request) -> Response:
    connector = get_computer_connector()
    if connector is None:
        return Response.json(503, {"error": "computer connector is not configured"})
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    if not isinstance(body, dict):
        return Response.json(400, {"error": "body must be a JSON object"})
    capability_id = body.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id.strip():
        return Response.json(400, {"error": "capability_id is required"})
    capability_name = capability_id.strip()
    # Mirror ProxyManager.call_tool: a scoped context token may only invoke
    # capabilities on its allowlist. An absent/empty allowlist is unrestricted.
    identity = resolve_request_identity(req)
    if not capability_allowed(capability_name, identity.allowed_capabilities):
        return Response.json(
            403,
            {
                "error": f"capability {capability_name!r} denied: not in context allowlist",
                "code": "capability_denied",
                "capability_id": capability_name,
            },
        )
    arguments = {key: value for key, value in body.items() if key != "capability_id"}
    result = connector.call(capability_name, arguments)
    return Response.json(200, result)


# Fabric lane (capability discovery + remote contexts). Side-effect import.
from kater.api import fabric_routes as _fabric_routes  # noqa: E402, F401
