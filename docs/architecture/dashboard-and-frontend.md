# Dashboard and frontend architecture

Status: current production shape (Kater ≥ v1.0.0, June 2026)  
Audience: operators and contributors wondering why the UI is “Python + inline JS”
instead of a separate React/Vite app.

## TL;DR

- **Kater’s MCP gateway path is Python** and always has been. That is the product.
- **The dashboard is an operator cockpit**, not the agent hot path. It is one
  server-rendered document: `src/kater/web/dashboard.py` (~4.5k lines of HTML/CSS/JS
  embedded in Python strings).
- **Splitting to a “mooie” SPA does not make MCP faster.** Agents talk to
  `:9090/mcp` (or `/sse`). The dashboard on `:9091` is optional human UI.
- **You do not lose gateway speed** by keeping the embedded UI. You *would* add
  build/deploy complexity, API↔UI drift risk, and a second frontend toolchain.

A separate frontend is a valid *later* choice when design velocity or team size
justify it — not because the current stack is slow for agents.

## Process model (one binary, three listeners)

`kater serve` / `kater up` starts **one Python process** (`KaterRuntime`):

| Listener | Default port | Role | Hot path for agents? |
|----------|--------------|------|----------------------|
| MCP (streamable HTTP + legacy SSE) | 9090 | Tool calls, proxy aggregation | **Yes** |
| REST API | 9091 | `/api/*`, OpenAPI, dashboard HTML | No (humans + dashboard JS) |
| WebSocket | 9092 | Live telemetry / state broadcasts | No (dashboard polish) |

Cursor on laptop typically uses only:

```json
{ "type": "http", "url": "http://127.0.0.1:9090/mcp" }
```

via `kater-forward`. Opening the dashboard in a browser does not load for MCP
clients.

## What is Python vs what is Node

| Component | Language | Notes |
|-----------|----------|-------|
| Gateway, authgate, proxy manager, telemetry DB | Python | Core |
| Native `kater_*` tools (doctor, pr_gate, browser router, …) | Python | Core |
| Dashboard document + its client JS | Python emits HTML; JS runs **in the browser** | No npm build |
| Proxied MCP backends (GitHub, context7, …) | Often **Node** via `npx` | Child processes; not Kater UI |
| Dashboard JS unit tests | Node subprocess | Extracts `<script>` snippets only in CI |
| Production Docker image | Python + **Node runtime** | Node is for spawning stdio MCPs, not serving SPA |

There has **never** been a `package.json` frontend app in this repository.

## Why embedded dashboard (design intent)

1. **Zero frontend supply chain on the gateway** — no Vite/webpack, no npm audit
   surface on the control plane, no “dashboard build failed so ops is blind”.
2. **Same deploy artifact** — `uv sync && kater serve` or one Docker image; dashboard
   ships with the version of the API it was written against.
3. **Operator scope** — dense ops UI (catalog toggles, tunnel, credentials, evals).
   Not a customer-facing product surface; Signaal-grade polish lives elsewhere
   (ChefApp, Vault, OpenCodex).
4. **API already exists** — the dashboard is a client of `/api/*`. The backend is
   already “headless-capable”; the UI choice is independent of MCP performance.

Historical note: v1.0.0 (2026-06-26) shipped gateway + REST + WS + embedded dashboard
together. Later work (e.g. dashboard rebuild, Connect OAuth) improved the same
module rather than introducing a SPA repo.

## Speed and tech — what you would and would not lose

### You would **not** lose (MCP / agent path)

- MCP latency, proxy fan-out, circuit breakers, profile gating — unchanged.
- Single-port tunneling (`gateway.py` proxies `/api` and `/dashboard` on 9090 for
  Cloudflare) — can stay; SPA would still hit the same REST API.
- CLI + `--json` automation — unchanged.

### You would **not** gain much (agent path)

- Agents do not render the dashboard. A React rewrite does not shrink tool schemas
  or context cost on the MCP wire.
- First paint of `:9091` can improve with a SPA + CDN — irrelevant to Cursor
  calling `kater_doctor`.

### You **would** pay (operator / engineering path)

| Cost | Embedded (today) | Separate SPA |
|------|------------------|--------------|
| Deploy steps | One Python wheel / image | Python + frontend build + static hosting or bundled assets |
| API drift | Tests assert dashboard JS paths match `RouteTable` | Need OpenAPI client gen + CI contract tests |
| Auth / OAuth / WS | Same origin, ticket flow in one doc | CORS, cookie domains, WS URL config |
| Design iteration | Edit one file; easy to grep | Component tree, design tokens, separate PR lane |
| Cold start on laptop | Already running with gateway | Extra `npm run dev` or rebuild on change |

### Browser UX — honest tradeoff

The embedded dashboard **can** look good (see dashboard rebuild plan); it is harder
to reach ChefBar/Signaal-level component reuse than in a shared TS design system.
That is a **design-system and maintainability** argument, not a gateway throughput
argument.

## When a separate frontend *is* worth it

Consider a SPA (or ChefApp room) when **most** of these are true:

- Multiple engineers work on UI weekly, not only gateway/Python.
- You want shared tokens/components with Signaal v3 across ChefGroep products.
- Dashboard features outgrow safe editing of a 5k-line Python string (already a
  maintainability pressure point).
- You need offline/PWA, complex routing, or rich component libraries beyond
  vanilla JS.

Recommended split if you go there:

```
kater serve (Python)          kater-dashboard (TS SPA, optional)
  :9090/mcp  ← agents           fetch /api/*, wss telemetry
  :9091/api  ← REST only        static assets via nginx or embedded dist/
```

Keep **MCP and REST in Python**. Replace only the HTML/JS presentation layer.
Generate TS types from `openapi_spec.py` to prevent drift (today partially guarded
by `tests/test_dashboard.py`).

## What we are not planning to do

- Rewrite the gateway in Node/TS “for speed” — the bottleneck is proxied MCP
  backends and network, not Python request handling on localhost.
- Put secrets or adapter env in a frontend bundle — credentials stay server-side
  (`/api/mcp/servers/{name}/credentials`, `.kater/.env`).

## Related docs

- [`docs/plans/dashboard-rebuild-no-slop.md`](../plans/dashboard-rebuild-no-slop.md) — API/UI contract table
- [`docs/architecture/kater-control-plane-wave.md`](kater-control-plane-wave.md) — capability routing (MCP hot path)
- [`README.md`](../../README.md) — ports, quick start, dashboard feature list
