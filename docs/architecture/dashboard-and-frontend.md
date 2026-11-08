# Dashboard and frontend architecture

Status: current production shape (Kater ≥ v1.1.1, September 2026)
Audience: operators and contributors wondering why the operator cockpit is
Python + inline JS, and how that sits next to Kater Studio.

## TL;DR

- **Kater’s MCP gateway path is Python** and always has been. That is the product.
- **The operator dashboard is an operator cockpit**, not the agent hot path. It is
  one server-rendered document: `src/kater/web/dashboard.py` (HTML/CSS/JS embedded
  in Python strings).
- **Kater Studio** (`studio/`) is a separate React/Vite *presentation* client.
  Build-time output is deterministic static assets in `src/kater/web/studio_dist/`,
  packaged into the Python wheel. There is no Node frontend in production.
- **Splitting the operator dashboard to a “mooie” SPA does not make MCP faster.**
  Agents talk to `:9090/sse` (repo default) or `:9090/mcp`. The dashboard on
  `:9091` is optional human UI.
- **You do not lose gateway speed** by keeping the embedded operator UI. A second
  live frontend toolchain on the control plane would add build/deploy complexity
  and API↔UI drift risk.

Studio already covers the “separate presentation client” case without moving the
gateway off Python.

## Process model (one binary, three listeners)

`kater serve` / `kater up` starts **one Python process** (`KaterRuntime`):

| Listener | Default port | Role | Hot path for agents? |
|----------|--------------|------|----------------------|
| MCP (legacy SSE + streamable HTTP) | 9090 | Tool calls, proxy aggregation | **Yes** |
| REST API | 9091 | `/api/*`, OpenAPI, dashboard HTML, Studio static | No (humans) |
| WebSocket | 9092 | Live telemetry / state broadcasts | No (dashboard polish) |

Cursor / local clients typically use one of:

```json
{ "url": "http://127.0.0.1:9090/sse" }
```

or streamable HTTP:

```json
{ "type": "http", "url": "http://127.0.0.1:9090/mcp" }
```

Opening the dashboard or Studio in a browser does not load for MCP clients.

## What is Python vs what is Node

| Component | Language | Notes |
|-----------|----------|-------|
| Gateway, authgate, proxy manager, telemetry DB | Python | Core |
| Native `kater_*` tools (doctor, pr_gate, browser router, …) | Python | Core |
| Operator dashboard + its client JS | Python emits HTML; JS runs **in the browser** | No npm build |
| Kater Studio | TypeScript / React / Vite **at build time** | `uv run npm --prefix studio …`; output is static files in the wheel |
| Proxied MCP backends (GitHub, context7, …) | Often **Node** via `npx` | Child processes; not Kater UI |
| Dashboard JS unit tests | Node subprocess | Extracts `<script>` snippets only in CI |
| Production Docker image | Python + **Node runtime** | Node is for spawning stdio MCPs, not serving a live SPA |

`studio/package.json` exists for the Studio *build*. It is not a production
Node server.

## Why embedded operator dashboard (design intent)

1. **Zero live frontend supply chain on the gateway** — no Vite/webpack at serve
   time, no “dashboard build failed so ops is blind”.
2. **Same deploy artifact** — `uv sync && kater serve` or one Docker image;
   dashboard and Studio dist ship with the API they were built against.
3. **Operator scope** — dense ops UI (catalog toggles, tunnel, credentials).
   Not a customer-facing product surface.
4. **API already exists** — both UIs are clients of `/api/*`. The backend is
   already “headless-capable”; the UI choice is independent of MCP performance.

Historical note: v1.0.0 shipped gateway + REST + WS + embedded dashboard
together. Later work (dashboard rebuild, Connect OAuth, Studio) improved the
same process rather than introducing a second production runtime.

## Speed and tech — what you would and would not lose

### You would **not** lose (MCP / agent path)

- MCP latency, proxy fan-out, circuit breakers, profile gating — unchanged.
- Single-port tunneling (`gateway.py` proxies `/api` and `/dashboard` on 9090 for
  Cloudflare) — can stay; any extra UI still hits the same REST API.
- CLI + `--json` automation — unchanged.

### You would **not** gain much (agent path)

- Agents do not render the dashboard or Studio. A React rewrite does not shrink
  tool schemas or context cost on the MCP wire.
- First paint of `:9091` can improve with a CDN — irrelevant to Cursor calling
  `kater_doctor`.

### You **would** pay (if you added a *live* SPA next to Studio)

| Cost | Embedded + Studio dist (today) | Extra live SPA |
|------|--------------------------------|----------------|
| Deploy steps | One Python wheel / image | Python + extra host / CORS / second pipeline |
| API drift | Tests + OpenAPI; Studio is a build-time snapshot | Need a second contract lane |
| Auth / OAuth / WS | Same origin | CORS, cookie domains, WS URL config |
| Cold start on laptop | Already running with gateway | Extra `npm run dev` unless you only use the baked dist |

### Browser UX — honest tradeoff

The embedded dashboard is the ops cockpit. Studio is the presentation client
when you want a component tree. Both are still served by the Python process.
That is a **maintainability** split, not a gateway throughput argument.

## When more frontend work *is* worth it

Prefer extending **Studio** (and regenerating `studio_dist/`) when:

- Multiple engineers work on UI weekly, not only gateway/Python.
- You want shared tokens/components across ChefGroep products.
- Operator-dashboard features outgrow safe editing of a large Python string.
- You need richer routing or component libraries beyond vanilla JS.

Keep **MCP and REST in Python**. Do not introduce a second production Node
server. Generate TS types from `openapi_spec.py` to prevent drift (today
partially guarded by `tests/test_dashboard.py`).

## What we are not planning to do

- Rewrite the gateway in Node/TS “for speed” — the bottleneck is proxied MCP
  backends and network, not Python request handling on localhost.
- Put secrets or adapter env in a frontend bundle — credentials stay server-side
  (`/api/mcp/servers/{name}/credentials`, `.kater/.env`).
- Treat Studio as a live `npm run dev` dependency in production.

## Related docs

- [`docs/plans/dashboard-rebuild-no-slop.md`](../plans/dashboard-rebuild-no-slop.md) — API/UI contract table
- [`docs/architecture/kater-control-plane-wave.md`](kater-control-plane-wave.md) — capability routing (MCP hot path)
- [`README.md`](../../README.md) — ports, quick start, dashboard feature list
