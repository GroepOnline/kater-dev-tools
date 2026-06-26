from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from kater.adapters.external import scan_adapters
from kater.chains import list_chains
from kater.deploy import list_deploy_formats, render_deploy
from kater.doctor import run_doctor
from kater.profiles import TOOL_SOURCES, get_source, list_profiles
from kater.registry import tools_for_profile
from kater.settings import (
    RateLimiter,
    cors_allow_origin,
    load_settings,
    save_settings,
)
from kater.telemetry import (
    eval_summary,
    load_events,
    record_chain_run,
    record_server_toggle,
    status_overview,
)
from kater.tunnel import start_cloudflared, start_tailscale_funnel

# ── Request / Response: the seam between the stdlib server and app logic ──


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    raw_body: bytes
    client_ip: str
    base_url: str
    params: dict[str, str] = field(default_factory=dict)

    def query1(self, key: str, default: str | None = None) -> str | None:
        return self.query.get(key, [default])[0]

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    @property
    def json(self) -> dict[str, Any]:
        if not self.raw_body:
            return {}
        try:
            return json.loads(self.raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body") from None

    @property
    def form(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for pair in self.raw_body.decode("utf-8").split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                out[unquote(k)] = unquote(v)
        return out

    @property
    def json_or_form(self) -> dict[str, Any]:
        ctype = self.header("content-type") or ""
        return self.json if ctype.startswith("application/json") else self.form


@dataclass
class Response:
    status: int = 200
    payload: Any = None
    body: bytes | None = None
    content_type: str = "application/json; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def json(cls, status: int, payload: Any) -> Response:
        return cls(status=status, payload=payload)

    @classmethod
    def html(cls, status: int, markup: str) -> Response:
        return cls(
            status=status,
            body=markup.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )

    @classmethod
    def redirect(cls, location: str) -> Response:
        return cls(status=302, body=b"", content_type="text/plain", headers={"Location": location})

    def encoded(self) -> bytes:
        if self.body is not None:
            return self.body
        return json.dumps(self.payload, ensure_ascii=False, indent=2).encode("utf-8")


# ── Route table: one dispatch mechanism for every endpoint ──────────


@dataclass(frozen=True)
class Route:
    method: str
    pattern: str
    handler: Callable[[Request], Response]
    public: bool = False
    rate_limit: bool = True


class RouteTable:
    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, route: Route) -> None:
        self._routes.append(route)

    def match(self, method: str, path: str) -> tuple[Route, dict[str, str]] | None:
        target = _segments(path)
        exact: tuple[Route, dict[str, str]] | None = None
        param: tuple[Route, dict[str, str]] | None = None
        for route in self._routes:
            if route.method != method:
                continue
            pat = _segments(route.pattern)
            if len(pat) != len(target):
                continue
            captured: dict[str, str] = {}
            ok = True
            has_param = False
            for p, t in zip(pat, target, strict=True):
                if p.startswith("{") and p.endswith("}"):
                    captured[p[1:-1]] = t
                    has_param = True
                elif p != t:
                    ok = False
                    break
            if not ok:
                continue
            if has_param:
                param = param or (route, captured)
            else:
                exact = (route, captured)
        return exact or param


def _segments(path: str) -> list[str]:
    stripped = path.strip("/")
    return stripped.split("/") if stripped else []


ROUTER = RouteTable()


def route(method: str, pattern: str, *, public: bool = False) -> Callable[..., Any]:
    def decorator(func: Callable[[Request], Response]) -> Callable[[Request], Response]:
        ROUTER.add(Route(method, pattern, func, public=public))
        return func

    return decorator


# ── Payload builders (unchanged domain logic) ──────────────────────


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
    settings = load_settings()
    servers = []
    for source in TOOL_SOURCES:
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


# ── Rate limiter (module-level) ────────────────────────────────────

_rate_limiter: RateLimiter | None = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        settings = load_settings()
        _rate_limiter = RateLimiter(settings.rate_limit_per_min)
    return _rate_limiter


def _reset_rate_limiter() -> None:
    # Called after settings change so a new rate_limit_per_min takes effect
    # immediately instead of being pinned to the value at first request.
    global _rate_limiter
    _rate_limiter = None


# ── The pipeline: one function decides every request ───────────────


def handle(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response.json(200, {"ok": True})

    matched = ROUTER.match(request.method, request.path)
    if matched is None:
        return Response.json(404, {"error": f"Not found: {request.path}"})

    matched_route, params = matched
    request.params = params

    if matched_route.rate_limit and not _get_rate_limiter().check(request.client_ip):
        return Response.json(429, {"error": "Rate limit exceeded. Try again later."})

    if not matched_route.public:
        from kater.authgate import AuthContext, authenticate

        decision = authenticate(
            AuthContext(
                settings=load_settings(),
                authorization_header=request.header("authorization"),
                query_api_key=request.query1("api_key"),
                path=request.path,
            )
        )
        if not decision.allowed:
            return Response.json(401, {"error": decision.error or "Unauthorized"})

    try:
        return matched_route.handler(request)
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    except Exception as exc:  # noqa: BLE001 - surface as 500, never crash the thread
        return Response.json(500, {"error": str(exc)})


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

    client = get_client(client_id)
    if not client:
        return Response.json(400, {"error": "invalid_client"})
    if not validate_redirect_uri(client, redirect_uri):
        return Response.json(400, {"error": "invalid_redirect_uri"})

    if approve == "1":
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
        location = f"{redirect_uri}{sep}code={code}"
        if state:
            location += f"&state={state}"
        return Response.redirect(location)

    if approve == "0":
        sep = "&" if "?" in redirect_uri else "?"
        return Response.redirect(f"{redirect_uri}{sep}error=access_denied")

    authorize_self = (
        f"{req.base_url}/authorize?response_type=code"
        f"&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method={method}"
        f"&profile={profile}"
    )
    if scope:
        authorize_self += f"&scope={scope}"

    return Response.html(
        200,
        render_consent_page(
            client_name=client.client_name,
            redirect_uri=redirect_uri,
            state=state,
            authorize_url=authorize_self,
            profile=profile,
        ),
    )


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
    )
    if not token:
        return Response.json(400, {"error": "invalid_grant"})
    return Response.json(200, token)


@route("POST", "/register", public=True)
def _register_client(req: Request) -> Response:
    from kater.oauth import register_client

    body = req.json
    try:
        client = register_client(
            client_name=body.get("client_name", ""),
            redirect_uris=body.get("redirect_uris", []),
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


@route("GET", "/api/mcp/servers")
def _mcp_servers(_: Request) -> Response:
    return Response.json(200, _mcp_servers_payload())


@route("GET", "/api/mcp/servers/{name}")
def _mcp_server(req: Request) -> Response:
    source = get_source(req.params["name"])
    if not source:
        return Response.json(200, {"error": f"Unknown server: {req.params['name']}"})
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
    profile = os.environ.get("KATER_PROFILE", "core")
    return Response.json(200, render_deploy(req.params["format"], profile=profile))


@route("GET", "/api/status")
def _status(_: Request) -> Response:
    return Response.json(200, status_overview())


@route("GET", "/api/telemetry")
def _telemetry(_: Request) -> Response:
    events = load_events()
    return Response.json(200, {"total": len(events), "events": events})


@route("GET", "/api/evals")
def _evals(_: Request) -> Response:
    return Response.json(200, eval_summary())


@route("GET", "/api/catalog")
def _catalog(_: Request) -> Response:
    settings = load_settings()
    results = []
    for source in TOOL_SOURCES:
        if source.transport == "native":
            continue
        env_ok = all(os.environ.get(v) for v in source.env)
        results.append(
            {
                "name": source.name,
                "description": source.description,
                "transport": source.transport.value,
                "risk": source.risk.value,
                "profiles": sorted(source.profiles),
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


@route("GET", "/api/export")
def _export(_: Request) -> Response:
    settings = load_settings()
    safe_auth = settings.auth.model_dump()
    if safe_auth.get("api_keys"):
        safe_auth["api_keys"] = len(safe_auth["api_keys"])
    return Response.json(
        200,
        {
            "version": settings.version,
            "default_profile": settings.default_profile,
            "auth": safe_auth,
            "server_overrides": {
                k: v.model_dump() for k, v in settings.server_overrides.items()
            },
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
    source = get_source(name)
    if not source:
        return Response.json(400, {"error": f"Unknown server: {name}"})
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


@route("POST", "/api/settings")
def _update_settings(req: Request) -> Response:
    body = req.json
    settings = load_settings()
    if "auth" in body:
        auth_patch = body["auth"]
        if not isinstance(auth_patch, dict):
            return Response.json(400, {"error": "auth must be an object"})
        # Merge instead of rebuild: only fields the client actually sent are
        # overwritten. A partial patch (e.g. just {"mode"}) can no longer wipe
        # api_keys / OAuth config — fixing a silent data-loss bug where every
        # Save from the dashboard reset the whole AuthConfig.
        current = settings.auth.model_dump()
        current.update({k: v for k, v in auth_patch.items() if k in current})
        settings.auth = type(settings.auth).model_validate(current)
    if "cors_origins" in body:
        settings.cors_origins = body["cors_origins"]
    if "rate_limit_per_min" in body:
        settings.rate_limit_per_min = int(body["rate_limit_per_min"])
        _reset_rate_limiter()
    if "default_profile" in body:
        settings.default_profile = body["default_profile"]
    save_settings(settings)
    return Response.json(200, settings.to_dict())


# ── Stdlib adapter: translate HTTP <-> Request/Response ────────────


def _base_url(handler: BaseHTTPRequestHandler) -> str:
    host = handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host", "localhost:9091")
    scheme = "https" if handler.headers.get("X-Forwarded-Proto") == "https" else "http"
    return f"{scheme}://{host}"


class KaterAPIHandler(BaseHTTPRequestHandler):
    server_version = "KaterAPI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _build_request(self, method: str) -> Request | None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = b""
        if length:
            if length > load_settings().body_size_limit:
                self._write(Response.json(400, {"error": "Request body too large"}))
                return None
            raw = self.rfile.read(length)
        return Request(
            method=method,
            path=path,
            query=parse_qs(parsed.query),
            headers={k.lower(): v for k, v in self.headers.items()},
            raw_body=raw,
            client_ip=self.client_address[0] if self.client_address else "unknown",
            base_url=_base_url(self),
        )

    def _dispatch(self, method: str) -> None:
        request = self._build_request(method)
        if request is None:
            return
        self._write(handle(request))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_OPTIONS(self) -> None:
        self._write(Response.json(200, {"ok": True}))

    def _write(self, response: Response) -> None:
        body = response.encoded()
        origin = self.headers.get("Origin")
        allow = cors_allow_origin(load_settings(), origin)
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(body)))
        if allow:
            self.send_header("Access-Control-Allow-Origin", allow)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)


def create_api_server(host: str = "127.0.0.1", port: int = 9091) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), KaterAPIHandler)


def serve_api(host: str = "127.0.0.1", port: int = 9091) -> None:
    server = create_api_server(host, port)
    server.serve_forever()
