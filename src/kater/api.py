from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from kater.adapters.external import scan_adapters
from kater.chains import list_chains
from kater.deploy import list_deploy_formats, render_deploy
from kater.doctor import run_doctor
from kater.profiles import TOOL_SOURCES, get_source, list_profiles
from kater.registry import tools_for_profile
from kater.settings import (
    RateLimiter,
    check_auth,
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


def _adapter_payload(profile: str) -> dict[str, Any]:
    inventory = scan_adapters({profile})
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


ROUTES: dict[str, Any] = {}


def _register(method: str, pattern: str) -> Any:
    def decorator(func: Any) -> Any:
        ROUTES[f"{method} {pattern}"] = func
        return func

    return decorator


# ── Module-level state ─────────────────────────────────────────────

_rate_limiter: RateLimiter | None = None


def _get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        settings = load_settings()
        _rate_limiter = RateLimiter(settings.rate_limit_per_min)
    return _rate_limiter


class KaterAPIHandler(BaseHTTPRequestHandler):
    server_version = "KaterAPI/1.0"

    def _send_json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        settings = load_settings()
        origin = self.headers.get("Origin")
        allow = cors_allow_origin(settings, origin)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if allow:
            self.send_header("Access-Control-Allow-Origin", allow)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        self._send_json(code, {"error": message})

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        settings = load_settings()
        if length > settings.body_size_limit:
            raise ValueError("Request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body") from None

    def _authenticate(self) -> bool:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path in ("/health", "/authorize", "/token", "/register", "/revoke"):
            return True
        if path.startswith("/.well-known"):
            return True
        settings = load_settings()
        if settings.auth.mode == "none":
            return True
        auth_header = self.headers.get("Authorization")
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        api_key = query.get("api_key", [None])[0]
        ok, error = check_auth(settings, auth_header, api_key)
        if not ok:
            self._send_error(401, error or "Unauthorized")
            return False
        return True

    def _rate_check(self) -> bool:
        limiter = _get_rate_limiter()
        client = self.client_address[0] if self.client_address else "unknown"
        if not limiter.check(client):
            self._send_error(429, "Rate limit exceeded. Try again later.")
            return False
        return True

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        if not self._rate_check():
            return
        if not self._authenticate():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        key = f"GET {path}"
        if key in ROUTES:
            try:
                result = ROUTES[key]()
                self._send_json(200, result)
            except Exception as exc:
                self._send_error(500, str(exc))
            return
        for pattern, func in ROUTES.items():
            if pattern.startswith("GET /") and "{x}" in pattern:
                prefix = pattern.split("/{x}")[0]
                path_prefix = prefix[4:]
                if path.startswith(path_prefix + "/"):
                    param = path[len(path_prefix) + 1:]
                    try:
                        result = func(param)
                        self._send_json(200, result)
                    except Exception as exc:
                        self._send_error(500, str(exc))
                    return
        self._send_error(404, f"Not found: {path}")

    def do_POST(self) -> None:
        if not self._rate_check():
            return
        if not self._authenticate():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        key = f"POST {path}"
        if key in ROUTES:
            try:
                body = self._read_body()
            except ValueError as exc:
                self._send_error(400, str(exc))
                return
            try:
                result = ROUTES[key](body)
                code = 200
                if isinstance(result, dict) and "error" in result:
                    msg = result.get("error", "").lower()
                    if "not found" in msg or "unknown" in msg:
                        code = 404
                    else:
                        code = 400
                self._send_json(code, result)
            except Exception as exc:
                self._send_error(500, str(exc))
            return
        for pattern, func in ROUTES.items():
            if pattern.startswith("POST /") and "{x}" in pattern:
                prefix = pattern.split("/{x}")[0]
                path_prefix = prefix[5:]
                if path.startswith(path_prefix + "/"):
                    remainder = path[len(path_prefix) + 1:]
                    parts = remainder.split("/", 1)
                    param = parts[0]
                    sub = parts[1] if len(parts) > 1 else ""
                    try:
                        body = self._read_body()
                    except ValueError as exc:
                        self._send_error(400, str(exc))
                        return
                    try:
                        result = func(param, sub, body)
                        code = 200
                        if isinstance(result, dict) and "error" in result:
                            code = 400
                        self._send_json(code, result)
                    except Exception as exc:
                        self._send_error(500, str(exc))
                    return
        self._send_error(404, f"Not found: {path}")

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


# ── Public endpoints (no auth required even if enabled) ────────────


@_register("GET", "/health")
def _health() -> dict[str, Any]:
    from kater import __version__

    settings = load_settings()
    return {
        "status": "ok",
        "version": __version__,
        "auth_mode": settings.auth.mode,
    }


# ── Read endpoints ─────────────────────────────────────────────────


@_register("GET", "/api/profiles")
def _profiles() -> dict[str, Any]:
    return {"profiles": list_profiles()}


@_register("GET", "/api/tools")
def _tools() -> dict[str, Any]:
    profile = os.environ.get("KATER_PROFILE", "core")
    tools = tools_for_profile(profile)
    return {
        "profile": profile,
        "tools": [t.model_dump(exclude={"handler"}) for t in tools],
    }


@_register("GET", "/api/adapters")
def _adapters() -> dict[str, Any]:
    profile = os.environ.get("KATER_PROFILE", "core")
    return _adapter_payload(profile)


@_register("GET", "/api/doctor")
def _doctor() -> dict[str, Any]:
    profile = os.environ.get("KATER_PROFILE", "core")
    report = run_doctor(profiles={profile})
    return report.model_dump(mode="json")


@_register("GET", "/api/chains")
def _chains() -> dict[str, Any]:
    profile = os.environ.get("KATER_PROFILE", "core")
    chains = list_chains(profile)
    return {"chains": [c.model_dump(mode="json") for c in chains]}


@_register("GET", "/api/mcp/servers")
def _mcp_servers() -> dict[str, Any]:
    return _mcp_servers_payload()


@_register("GET", "/api/mcp/servers/{x}")
def _mcp_server(name: str) -> dict[str, Any]:
    source = get_source(name)
    if not source:
        return {"error": f"Unknown server: {name}"}
    settings = load_settings()
    env_present = all(os.environ.get(v) for v in source.env)
    return {
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


@_register("GET", "/api/settings")
def _get_settings() -> dict[str, Any]:
    return load_settings().to_safe_dict()


@_register("GET", "/api/deploy")
def _deploy_formats() -> dict[str, Any]:
    return {"formats": list_deploy_formats()}


@_register("GET", "/api/deploy/{x}")
def _deploy_render(fmt: str) -> dict[str, Any]:
    profile = os.environ.get("KATER_PROFILE", "core")
    return render_deploy(fmt, profile=profile)


@_register("GET", "/api/status")
def _status() -> dict[str, Any]:
    return status_overview()


@_register("GET", "/api/telemetry")
def _telemetry() -> dict[str, Any]:
    events = load_events()
    return {
        "total": len(events),
        "events": events,
    }


@_register("GET", "/api/evals")
def _evals() -> dict[str, Any]:
    return eval_summary()


@_register("GET", "/api/catalog")
def _catalog() -> dict[str, Any]:
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
    return {
        "total": len(results),
        "servers": results,
        "by_transport": _group_by(results, "transport"),
        "by_risk": _group_by(results, "risk"),
    }


def _group_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


@_register("GET", "/api/spec")
def _spec() -> dict[str, Any]:
    from kater.openapi_spec import generate_spec

    return generate_spec()


@_register("GET", "/api/export")
def _export() -> dict[str, Any]:
    settings = load_settings()
    safe_auth = settings.auth.model_dump()
    if safe_auth.get("api_keys"):
        safe_auth["api_keys"] = len(safe_auth["api_keys"])
    return {
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
    }


# ── Mutation endpoints ─────────────────────────────────────────────


@_register("POST", "/api/chains/run")
def _chain_run(body: dict[str, Any]) -> dict[str, Any]:
    name = body.get("name", "")
    profile = body.get("profile", os.environ.get("KATER_PROFILE", "core"))
    chains = list_chains(profile)
    for c in chains:
        if c.name == name:
            result = {
                "chain": c.name,
                "description": c.description,
                "profile": profile,
                "steps": [
                    {"step": i + 1, "tool": s.tool, "reason": s.reason}
                    for i, s in enumerate(c.steps)
                ],
            }
            record_chain_run(c.name, steps=len(c.steps), profile=profile)
            return result
    record_chain_run(name, steps=0, success=False, profile=profile, error="not_found")
    return {"error": f"Chain '{name}' not found for profile '{profile}'."}


@_register("POST", "/api/mcp/servers/{x}")
def _server_action(name: str, action: str, body: dict[str, Any]) -> dict[str, Any]:
    source = get_source(name)
    if not source:
        return {"error": f"Unknown server: {name}"}
    settings = load_settings()
    if action == "enable":
        settings.set_server_enabled(name, True)
        save_settings(settings)
        record_server_toggle(name, action, True)
        _ws_broadcast("server_enabled", {"name": name})
        return {"name": name, "enabled": True}
    if action == "disable":
        settings.set_server_enabled(name, False)
        save_settings(settings)
        record_server_toggle(name, action, False)
        _ws_broadcast("server_disabled", {"name": name})
        return {"name": name, "enabled": False}
    if action == "toggle":
        current = settings.is_server_enabled(name, default=True)
        settings.set_server_enabled(name, not current)
        save_settings(settings)
        record_server_toggle(name, action, not current)
        _ws_broadcast(
            "server_toggled", {"name": name, "enabled": not current}
        )
        return {"name": name, "enabled": not current}
    return {"error": f"Unknown action: {action}"}


def _ws_broadcast(event_type: str, data: dict[str, Any]) -> None:
    try:
        from kater.websocket import broadcast_event

        broadcast_event({"type": event_type, **data, "ts": time.time()})
    except ImportError:
        pass


@_register("POST", "/api/settings")
def _update_settings(body: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    if "auth" in body:
        settings.auth = type(settings.auth).model_validate(body["auth"])
    if "cors_origins" in body:
        settings.cors_origins = body["cors_origins"]
    if "rate_limit_per_min" in body:
        settings.rate_limit_per_min = int(body["rate_limit_per_min"])
    if "default_profile" in body:
        settings.default_profile = body["default_profile"]
    save_settings(settings)
    return settings.to_dict()


@_register("GET", "/")
def _dashboard() -> dict[str, Any]:
    return {"_serve_html": True}


_original_get = KaterAPIHandler.do_GET


def _patched_do_get(self) -> None:
    parsed = urlparse(self.path)
    path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query)

    if path == "/" or path == "/dashboard":
        from kater.web import render_dashboard

        html = render_dashboard().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html)
        return

    if path == "/.well-known/oauth-authorization-server":
        base = _base_url(self)
        from kater.oauth import discovery_metadata

        self._send_json(200, discovery_metadata(base))
        return

    if path == "/.well-known/oauth-protected-resource":
        base = _base_url(self)
        from kater.oauth import resource_metadata

        self._send_json(200, resource_metadata(base))
        return

    if path == "/authorize":
        _handle_authorize(self, query)
        return

    _original_get(self)


def _base_url(handler: Any) -> str:
    host = handler.headers.get("Host", "localhost:9091")
    scheme = "https" if handler.headers.get("X-Forwarded-Proto") == "https" else "http"
    return f"{scheme}://{host}"


def _handle_authorize(handler: Any, query: dict[str, list[str]]) -> None:
    from kater.oauth import (
        create_auth_code,
        get_client,
        render_consent_page,
        validate_redirect_uri,
    )

    client_id = query.get("client_id", [""])[0]
    redirect_uri = query.get("redirect_uri", [""])[0]
    challenge = query.get("code_challenge", [""])[0]
    method = query.get("code_challenge_method", ["S256"])[0]
    scope = query.get("scope", [""])[0]
    state = query.get("state", [None])[0]
    profile = query.get("profile", ["core"])[0]
    approve = query.get("approve", [""])[0]

    client = get_client(client_id)
    if not client:
        handler._send_json(400, {"error": "invalid_client"})
        return

    if not validate_redirect_uri(client, redirect_uri):
        handler._send_json(400, {"error": "invalid_redirect_uri"})
        return

    if approve == "1":
        code = create_auth_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=challenge,
            code_challenge_method=method,
            scope=scope,
            state=state,
            profile=profile,
        )
        sep = "&" if "?" in redirect_uri else "?"
        location = f"{redirect_uri}{sep}code={code}"
        if state:
            location += f"&state={state}"
        handler.send_response(302)
        handler.send_header("Location", location)
        handler.end_headers()
        return

    if approve == "0":
        sep = "&" if "?" in redirect_uri else "?"
        handler.send_response(302)
        handler.send_header(
            "Location",
            f"{redirect_uri}{sep}error=access_denied",
        )
        handler.end_headers()
        return

    base = _base_url(handler)
    authorize_self = (
        f"{base}/authorize?response_type=code"
        f"&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method={method}"
        f"&profile={profile}"
    )
    if scope:
        authorize_self += f"&scope={scope}"

    html = render_consent_page(
        client_name=client.client_name,
        redirect_uri=redirect_uri,
        state=state,
        authorize_url=authorize_self,
        profile=profile,
    ).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(html)))
    handler.end_headers()
    handler.wfile.write(html)


_original_post = KaterAPIHandler.do_POST


def _patched_do_post(self) -> None:
    parsed = urlparse(self.path)
    path = parsed.path.rstrip("/") or "/"

    if path == "/token":
        _handle_token(self)
        return

    if path == "/register":
        _handle_register(self)
        return

    if path == "/revoke":
        _handle_revoke(self)
        return

    _original_post(self)


def _handle_token(handler: Any) -> None:
    from kater.oauth import exchange_code

    length = int(handler.headers.get("Content-Length", 0))
    body_raw = handler.rfile.read(length).decode("utf-8") if length else ""
    params: dict[str, str] = {}
    if handler.headers.get("Content-Type", "").startswith("application/json"):
        import json as _json

        params = _json.loads(body_raw) if body_raw else {}
    else:
        for pair in body_raw.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                from urllib.parse import unquote

                params[unquote(k)] = unquote(v)

    grant = params.get("grant_type", "")
    if grant != "authorization_code":
        handler._send_json(400, {"error": "unsupported_grant_type"})
        return

    code = params.get("code", "")
    client_id = params.get("client_id", "")
    verifier = params.get("code_verifier", "")

    token = exchange_code(code, client_id, verifier)
    if not token:
        handler._send_json(400, {"error": "invalid_grant"})
        return

    handler._send_json(200, token)


def _handle_register(handler: Any) -> None:
    from kater.oauth import register_client

    length = int(handler.headers.get("Content-Length", 0))
    body_raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    import json as _json

    body = _json.loads(body_raw) if body_raw else {}
    client = register_client(
        client_name=body.get("client_name", ""),
        redirect_uris=body.get("redirect_uris", []),
    )
    handler._send_json(201, {
        "client_id": client.client_id,
        "client_secret": client.client_secret,
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
    })


def _handle_revoke(handler: Any) -> None:
    from kater.oauth import revoke_token

    length = int(handler.headers.get("Content-Length", 0))
    body_raw = handler.rfile.read(length).decode("utf-8") if length else ""
    params: dict[str, str] = {}
    for pair in body_raw.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v

    token = params.get("token", "")
    revoke_token(token)
    handler._send_json(200, {"revoked": True})


KaterAPIHandler.do_GET = _patched_do_get
KaterAPIHandler.do_POST = _patched_do_post


def create_api_server(host: str = "0.0.0.0", port: int = 9091) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), KaterAPIHandler)


def serve_api(host: str = "0.0.0.0", port: int = 9091) -> None:
    server = create_api_server(host, port)
    server.serve_forever()
