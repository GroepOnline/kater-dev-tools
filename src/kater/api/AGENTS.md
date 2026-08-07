# api/ — stdlib REST surface

## OVERVIEW
`/api/*`, `/health`, `/dashboard`, `/authorize`, `/token`, `/register`, `/revoke` via ThreadingHTTPServer + BaseHTTPRequestHandler. No web framework.

## STRUCTURE
- models.py  # Request/Response dataclasses, RouteTable, @route, ROUTER singleton. NO kater imports (seam).
- routes.py  # 25+ @route handlers; import = side-effect populate ROUTER. Lazy imports inside handlers.
- server.py  # single handle() pipeline (OPTIONS→match→rate-limit→auth→handler); create_api_server/serve_api.

## WHERE TO LOOK
| Task | Location |
|------|----------|
| Add endpoint | routes.py handler + openapi_spec._build_paths entry |
| Change request/response shape | models.py |
| Change CORS/CSP/HSTS/rate-limit | server.py handle() |

## CONVENTIONS
- `server.py` imports `routes.py` only to trigger registration; symbols unused directly.
- Heavy deps (oauth, websocket, openapi_spec, deploy, telemetry) imported LAZILY inside handlers → cheap module import, no cycles.
- `_get_rate_limiter()` shared with MCP/WS via `check_transport_rate_limit`.
- do_HEAD reuses handle() with synthesized GET (auth/rate-limit parity).

## ANTI-PATTERNS
- Never add kater imports to models.py (breaks the seam / import cycle).
- `/api/spec` is a hand-maintained copy of routes — MUST update both or the drift-guard test breaks.
- `/api/adapters` always uses include_secrets=False (placeholders only, no resolved keys).
