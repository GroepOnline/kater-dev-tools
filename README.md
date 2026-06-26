# Kater

Kater is a developer-only MCP gateway for code agents. One endpoint, one
source of truth, full self-manageable. Keep agent context small by exposing
one curated MCP surface and turning broad dev MCPs on only through profiles.

```
  Agent (Cursor / Claude / ChatGPT / API)
  │
  │  one MCP connection
  │
  ▼
┌─────────────────────────────────────┐
│            KATER GATEWAY            │
│                                     │
│  KaterRuntime (ordered lifecycle)   │
│   ├─ REST API  (RouteTable pipeline)│
│   ├─ MCP / SSE (FastMCP + authgate) │
│   └─ WebSocket (telemetry stream)   │
│                                     │
│  authgate · CORS · Rate Limit · DB  │
│  ProxyManager → stdio / SSE backends│
│                                     │
│   Native  +  GitHub + Sentry + CF   │
│   (local)   (stdio)   (SSE)  (stdio)│
│              + 29 more servers      │
└─────────────────────────────────────┘
```

## Quick Start

```bash
uv sync
kater serve
```

Open `http://localhost:9091` for the dashboard.

## What It Does

- **Unified MCP surface**: proxy 29+ MCP servers behind one endpoint
- **Profile gating**: expose only the tools relevant to the current task
- **Web dashboard**: constellation view, catalog, evals, deploy configs
- **REST API**: 25+ endpoints with OpenAPI spec at `/api/spec`
- **WebSocket**: real-time telemetry and server state changes
- **Auth**: API key or OAuth2 with PKCE (ChatGPT compatible)
- **Telemetry**: SQLite-backed tool call tracking, success rates, latency
- **Deploy**: Docker, Cloudflare Tunnel, Tailscale Funnel, systemd, K8s, stdio
- **Self-managed**: enable/disable servers at runtime, no restart needed

## CLI Commands

| Command | Description |
|---------|-------------|
| `kater serve` | Start API + MCP + WebSocket in one process |
| `kater status` | Live instance overview |
| `kater doctor` | Diagnostics + autofix |
| `kater mcp list` | Browse all 29 MCP servers |
| `kater mcp status <name>` | Server detail with launch config |
| `kater enable <name>` | Enable a server |
| `kater disable <name>` | Disable a server |
| `kater toggle <name>` | Toggle server on/off |
| `kater config --profile ops` | Render MCP config for a profile |
| `kater deploy render docker` | Generate Docker Compose config |
| `kater deploy render cloudflare --domain x.com` | Generate Cloudflare Tunnel config |
| `kater tunnel` | Show tunnel status (CF + Tailscale) |
| `kater tunnel start -p cloudflare` | Start Cloudflare Tunnel |
| `kater auth set apikey --key <key>` | Configure API key auth |
| `kater auth set oauth` | Configure OAuth mode |
| `kater init` | Bootstrap `.kater/` in a project |
| `kater telemetry` | View raw telemetry events |
| `kater evals` | Aggregated tool performance metrics |
| `kater profiles` | List profiles |
| `kater tools --profile ops` | List tools for a profile |
| `kater chains` | List tool chains |
| `kater chain run <name>` | Execute a chain |
| `kater version` | Show version |

All commands support `--json` for structured output.

## MCP Server Catalog (29+)

| Server | Transport | Profiles |
|--------|-----------|----------|
| github | stdio | ops, code |
| gitlab | stdio | ops, code |
| linear | http | ops |
| sentry | http | ops |
| exa | http | research, web |
| firecrawl | stdio | research, web |
| huggingface | http | research, cloud |
| cloudflare | stdio | cloud, ops |
| upstash | stdio | cloud, ops |
| sanity | http | content |
| notion | stdio | content, ops |
| context7 | stdio | code, research, docs |
| deepwiki | stdio | code, research, docs |
| browser | stdio | web |
| puppeteer | stdio | web |
| resend | stdio | email, content |
| slack | stdio | email, ops |
| figma | stdio | image, content |
| postgres | stdio | cloud, ops |
| sqlite | stdio | code |
| filesystem | stdio | code |
| brave-search | stdio | research, web |
| fetch | stdio | research, web |
| quiverai | http | image |
| everart | stdio | image |
| memory | stdio | reasoning |
| sequential-thinking | stdio | reasoning, research |
| time | stdio | utils |
| utrecht | sse | utrecht |

## Web Dashboard

Open `http://localhost:9091` in any browser:

- **Dashboard**: interactive constellation canvas, live telemetry stream, stats
- **Catalog**: browse all servers, toggle on/off, filter by profile
- **Evals**: tool performance tables, success rates, latency
- **Deploy**: generate configs for any platform
- **Settings**: auth mode, CORS, rate limit, storage backend

Keyboard shortcuts: `1-5` switch views, `Ctrl+K` focuses command bar.

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/status` | GET | Instance overview |
| `/api/catalog` | GET | Server catalog with grouping |
| `/api/mcp/servers` | GET | List all servers |
| `/api/mcp/servers/{name}` | GET | Server detail |
| `/api/mcp/servers/{name}/{action}` | POST | Enable/disable/toggle |
| `/api/settings` | GET/POST | View/update settings |
| `/api/telemetry` | GET | Raw events |
| `/api/evals` | GET | Aggregated metrics |
| `/api/deploy` | GET | Deployment formats |
| `/api/deploy/{format}` | GET | Render config |
| `/api/spec` | GET | OpenAPI 3.1 spec |
| `/authorize` | GET | OAuth consent page |
| `/token` | POST | OAuth token exchange |
| `/register` | POST | OAuth client registration |
| `/.well-known/oauth-authorization-server` | GET | OAuth discovery |

Full spec: `GET /api/spec`

## Deployment

### Docker

```bash
docker compose up -d
```

### Cloudflare Tunnel (ChatGPT compatible)

```bash
./scripts/deploy-cloudflare.sh kater.chefgroep.online kater
```

Creates tunnel, DNS route, config, starts Kater + cloudflared. Result:
`https://kater.chefgroep.online/sse` — paste into ChatGPT Settings → MCP.

### Tailscale Funnel

```bash
kater tunnel start -p tailscale
```

### Other formats

```bash
kater deploy render systemd    # systemd unit file
kater deploy render k8s        # Kubernetes manifests
kater deploy render stdio      # Claude Desktop config
kater deploy render sse        # Cursor/ChatGPT SSE config
```

## Development

```bash
uv sync --dev
uv run ruff check .
uv run pytest -v
./scripts/smoke.sh
```

## Architecture

```
src/kater/
├── cli.py              CLI entry point (Typer)
├── runtime.py          KaterRuntime: ordered startup/shutdown of all servers
├── serve.py            Thin wrapper over KaterRuntime
├── api.py              REST API: Request/Response pipeline + RouteTable
├── authgate.py         Single source of truth for auth policy
├── websocket.py        WebSocket server (RFC 6455)
├── mcp_server.py       MCP SSE server (FastMCP + authgate middleware)
├── proxy/              MCP Proxy Engine
│   ├── manager.py      Lifecycle + routing + circuit breaker
│   ├── base.py         BaseBackend: shared MCP session ceremony
│   ├── stdio_backend.py  subprocess transport (env-whitelisted)
│   ├── sse_backend.py    upstream SSE transport
│   ├── aggregator.py   tool registry + prefix resolution
│   └── models.py       proxy data models
├── web/dashboard.py    Web dashboard (inline HTML/CSS/JS, per-view seams)
├── profiles.py         MCP server catalog (29+)
├── settings.py         Auth, CORS, storage, ListenConfig (bind SSOT)
├── storage.py          SQLite + JSONL telemetry
├── telemetry.py        Event recording + evals
├── oauth.py            OAuth2 + PKCE (locked, atomic state)
├── tunnel.py           CF Tunnel + Tailscale
├── deploy.py           Deployment config generation
├── ansi.py             CLI formatting
└── openapi_spec.py     OpenAPI 3.1 generation (drift-guarded)
```

## Status

v0.9.0 — 248 tests, 29 MCP servers, loopback-by-default, zero external runtime deps beyond pydantic/typer/mcp.
