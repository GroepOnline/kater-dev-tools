# Implementation record: Kater dashboard rebuild (no slop)

Branch: `cursor/dashboard-rebuild-no-slop-fed0`
Status: complete; the full test suite passed before this documentation review.

## Delivered outcome

A **working** operator cockpit for the MCP gateway now provides live status, catalog
toggles, evals, deploy configs, settings — wired to the real API. No runtime
monkeypatch layer. Design quality should feel like a serious exchange/control
surface: sharp, dense, readable, not AI-slop SaaS.

## Original diagnosis

1. **Broken JS** in `src/kater/web/dashboard.py`: `trackedTimeout` is missing
   (orphan body after `trackedRAF`). The live page only “works” because
   `review_fixes.py` string-patches the module at import time.
2. **API/UI drift**: dashboard JS calls paths/shapes that don’t match routes:
   - `/api/servers/{name}/set` → real: `/api/mcp/servers/{name}/{enable|disable}`
   - `/api/tunnel/toggle` → real: `/api/tunnel/{provider}/start|stop`
   - `/api/deploy/config` → real: `/api/deploy` + `/api/deploy/{format}`
   - `/api/command`, `/api/credentials/save` → do not exist
   - settings save uses wrong field names + `PUT` (route is `POST`)
   - status metrics read non-existent keys (`tools.total`, etc.)
3. **Half-applied redesign**: brutalist CSS + uppercase copy in source, then
   runtime sentence-case patches. Constellation canvas referenced but not driven.
4. **API review gaps** still live only in the patch layer:
   - events not newest-first
   - backends swallow errors instead of 503 + `backends` alias

These issues were resolved in source; the patch shim was removed.

## Implemented dashboard behavior

The shipped composition is an industrial control plane (not cream/serif or
purple glow).

| View | Behavior |
|------|----------|
| Dashboard | Metrics from `/api/status`, tunnels via `/api/tunnel` + start/stop, backend health, recent calls, live WS feed |
| Catalog | `/api/catalog` + profile filter; enable/disable via real MCP routes; detail drawer; credentials → `/api/mcp/servers/{name}/credentials` |
| Evals | `/api/evals` per-tool table |
| Deploy | `/api/deploy` tabs → `/api/deploy/{format}` + copy |
| Settings | `/api/settings` GET/POST with correct field names |

It retains first-party OAuth (`kater-dashboard` → `/authorize`), the WS ticket flow,
ARIA tabs, confirm dialogs, sentence-case operator copy, reduced-motion.

The `cmd-input` is a local command/navigation palette. It opens views, requests
a local refresh, and shows help; it never calls or pretends to call an API
command endpoint. The `constellation-canvas` is a functional, responsive backend
topology map: it redraws from `/api/backends` health data and on viewport resize,
placing the gateway at the center and up to 16 backends around it.

Broken/orphan JS, the fake `/api/command` contract, and the runtime patch
dependency were removed.

## Dashboard endpoint contracts

All `/api/*` routes below are protected according to the configured auth mode.
Unless a row says otherwise, a missing or invalid credential returns
`401 {"error": ...}`, malformed handler input returns `400 {"error": ...}`, and
an unexpected server exception returns `500 {"error":"Internal server error"}`.
The dashboard sends JSON POST bodies and treats every non-2xx response as an
error.

| Method | Path | Request payload/query | Key success response fields | Endpoint-specific error behavior |
|--------|------|-----------------------|-----------------------------|----------------------------------|
| GET | `/api/status` | None | `version`, `profile`, `servers.{total,enabled,disabled,configured,missing_env}`, `telemetry.{tool_calls,errors,success_rate}` | Common errors only |
| GET | `/api/backends` | None | `backends` and compatibility alias `servers`, each with `name`, `healthy`, `running`, `tool_count`, `latency_ms`, `breaker_state`, `enabled`, `configured`, `missing_env`; plus `totals` | Backend status collection failure returns 503 with a stable `error: "backend_status_unavailable"` and generic `message`, empty `backends`/`servers`, and available `totals`; exception details remain server-side only |
| GET | `/api/events` | Query: `limit` (1–1000, default 50), optional `since` (Unix timestamp or ISO-8601), `name`, `success=true\|false`; dashboard uses `limit=50` | `total`, newest-first `events[]` containing `id`, `type`, `name`, `timestamp`, `duration_ms`, `success`, `profile`, `metadata` | Invalid `limit` or `since` returns 400 |
| GET | `/api/tunnel` | None | `cloudflare`, `tailscale`, `available.{cloudflare,tailscale}`, `suggested_domain`, `client_configs`; provider status includes `running`, `url`, and related status data | Common errors only |
| POST | `/api/tunnel/{provider}/start` | `{}`; `provider` is `cloudflare` or `tailscale` | `provider`, `name`, `url`, `running`, `error`, `pid` | Unknown provider returns 400; startup exceptions return 500 |
| POST | `/api/tunnel/{provider}/stop` | `{}`; `provider` is `cloudflare` or `tailscale` | `provider`, `stopped`, `running` (false) | Unknown provider returns 400; stop exceptions return 500 |
| GET | `/api/profiles` | None | `profiles[]` | Common errors only |
| GET | `/api/catalog` | Optional query: `q`, `profile`, `transport`, `risk`; dashboard loads all and applies its visible filters locally | `total`, `servers[]` with `name`, `description`, `transport`, `risk`, `profiles`, `env_required`, `env_configured`, `enabled`, `homepage`, `context_cost`; `by_transport`, `by_risk` | Common errors only |
| POST | `/api/mcp/servers/{name}/{action}` | `{}`; dashboard uses `action=enable` or `disable` | `name`, `enabled` | Unknown/hidden server returns 404; unknown action returns 400 |
| POST | `/api/mcp/servers/{name}/credentials` | `{"env":{"DECLARED_VAR":"value"}}`; only environment names declared by that server are accepted | `name`, `env_configured`, `applied[]` | Unknown/hidden server returns 404; missing/non-object `env` or undeclared credential name returns 400 |
| GET | `/api/evals` | None | `time_span_s`, `tool_calls.{unique_tools,per_tool}`, `summary.{total_tool_calls,total_errors,overall_success_rate}`; each `per_tool` entry has `total`, `success`, `failed`, `success_rate`, `avg_duration_ms` | Common errors only |
| GET | `/api/deploy` | None | `formats[]`, each with `name` and `description` | Common errors only |
| GET | `/api/deploy/{format}` | `format` is `stdio`, `sse`, `docker`, `cloudflare`, `systemd`, or `k8s`; active `KATER_PROFILE` is used | Rendered JSON with `format`, `description`, and format-specific configuration (`mcpServers`, `compose`, `environment`/`steps`/`tunnel_config`, `unit_file`/`install_steps`, or `manifests`) | An unknown format currently returns HTTP 200 with an `error` field listing available formats |
| GET | `/api/settings` | None | Safe settings object including `auth` (API keys represented as a count), `default_profile`, `cors_origins`, `rate_limit_per_min`, `storage_backend`, host/port fields, and masked server credentials | Common errors only |
| POST | `/api/settings` | JSON fields used by the dashboard: `auth: {"mode": ...}`, `default_profile`, `cors_origins` (string array), `rate_limit_per_min` (integer), `storage_backend` (`sqlite` or `jsonl`) | Updated safe settings object, same shape as GET | Returns 403 when an admin credential is required; 400 for invalid field types/values or unsafe public settings (`auth.mode=none`, wildcard CORS, or zero rate limit) |
| POST | `/api/ws-ticket` | `{}` | `ticket`, `expires_in`; ticket is passed to the WebSocket `/ws?ticket=...` connection | Common errors only |

## Completed implementation phases

- **API solidification:** events are filtered, limited, and returned newest-first.
  Backends return `{backends, servers, totals}` and surface collection failures
  as 503; `_events` and `_backends` remain re-exported from `kater.api`.
- **Dashboard rewrite:** all five views use the contracts above in one native
  module, including OAuth, ticketed WebSocket updates, confirmations, keyboard
  navigation, local command palette, and topology rendering.
- **Cleanup:** `review_fixes.py` was deleted, `web/__init__.py` directly exports
  `render_dashboard`, and tests assert the native implementation without patch
  markers.
- **Verification:** lint, the full test suite, and smoke coverage are the release
  gates.

## Verification commands

```bash
uv run ruff check .
uv run pytest -v
./scripts/smoke.sh

# With `kater serve` running. Set AUTH_HEADER when auth is enabled, for example:
# AUTH_HEADER='Authorization: Bearer <token>'
curl -fsS http://localhost:9091/health |
  python -c 'import json,sys; d=json.load(sys.stdin); assert d["status"] == "ok"'
test "$(curl -fsS -o /dev/null -w '%{http_code}' http://localhost:9091/)" = 200
curl -fsS -H "${AUTH_HEADER:-}" http://localhost:9091/api/backends |
  python -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d["backends"], list) and isinstance(d["totals"], dict)'
curl -fsS -H "${AUTH_HEADER:-}" 'http://localhost:9091/api/events?limit=50' |
  python -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d["events"], list) and isinstance(d["total"], int)'
```

## Out of scope

- New MCP backends / profile catalog changes
- Auth/OAuth protocol changes
- Cloudflare/tunnel infra
- Dependabot / unrelated open PRs (#93 topbar CSS can land separately)

## Completion criteria

- `kater serve` → dashboard loads without import-time string surgery
- All five views hydrate from real endpoints
- Enable/disable, tunnel start/stop, settings save, deploy copy work
- The full test suite passes; no `review_fixes` module remains
