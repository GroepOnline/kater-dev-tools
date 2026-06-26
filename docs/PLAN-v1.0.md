# Kater v1.0 — Architectuurplan

> Status: DRAFT · Datum: 2026-06-26 · Van: v0.6.0 → v1.0.0

---

## 1. Het Probleem

Een code-agent (Cursor, Claude Desktop, ChatGPT) praat met MCP servers.
Elke MCP server voegt tools toe aan de context van de agent. Meer servers =
meer context = tragere, duurdere, slechtere antwoorden.

Daarnaast: elke MCP server apart configureren in elke client is
fragiel. Env vars, URLs, npx commands — versnipperd over .cursor/, .claude/,
.agent/ configs. Geen overzicht. Geen controle.

## 2. Wat Kater Is

Kater is **de enige MCP verbinding** die een agent nodig heeft. Eén
endpoint, één source of truth, volledig zelf beheerbaar.

```
  Agent (Cursor / Claude / ChatGPT / API)
  │
  │  één MCP verbinding (SSE of stdio)
  │
  ▼
┌─────────────────────────────────────────────┐
│                  KATER                      │
│                                             │
│  ┌─────────┐  ┌──────┐  ┌───────────────┐  │
│  │ Router  │  │ Auth │  │ Telemetry/DB  │  │
│  └────┬────┘  └──────┘  └───────────────┘  │
│       │                                     │
│   ┌───┴───┬─────┬─────┬─────┬─────┐        │
│   │       │     │     │     │     │        │
│   ▼       ▼     ▼     ▼     ▼     ▼        │
│ Native  GitHub Sentry CF  Notion ...       │
│ (local) (stdio) (SSE) (stdio) (stdio)      │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  Web Dashboard + REST API + WS       │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

Het verschil met v0.6: Kater **proxied werkelijk** naar externe MCP
servers. Nu exposed het alleen native tools. Dat is de core missende
stuk.

## 3. Wat Er Nu Is (v0.6.0)

| Laag                  | Status     | Gaps                          |
|-----------------------|------------|-------------------------------|
| CLI (25+ commands)    | Done       | Geen interactive mode         |
| REST API (21 routes)  | Done       | Geen echte MCP proxy          |
| WebSocket             | Done       | Alleen broadcast, geen RPC    |
| MCP Server            | **Partial**| Alleen native tools, geen proxy |
| Catalog (29 servers)  | Done       | Statisch, geen dynamic reg    |
| Telemetry + SQLite    | Done       | -                             |
| Auth (apikey/oauth)   | Done       | Geen JWKS validatie           |
| Deploy (6 formats)    | Done       | -                             |
| Docker                | Done       | Geen healthcheck API          |
| Web UI                | **Missing**| Bestaat niet                  |
| MCP Proxy             | **Missing**| Het belangrijkste stuk        |

## 4. Drie Kern Problemen Om Op Te Lossen

### 4A. MCP Proxy Engine (`src/kater/proxy/`)

**Doel:** Kater ontvangt tool calls van een agent en routeert ze naar
de juiste backend MCP server. De agent ziet één unified tool surface.

**Architectuur:**

```
src/kater/proxy/
├── __init__.py          # public API
├── manager.py           # ProxyManager — lifecycle van alle backends
├── stdio_backend.py     # spawn npx subprocess, JSON-RPC over stdin/stdout
├── sse_backend.py       # connect to upstream SSE MCP server
├── router.py            # route tool calls naar juiste backend
└── aggregator.py        # verzamel tool lists van alle backends
```

**Hoe het werkt:**

1. Bij opstarten: `ProxyManager.start(profile)` leest catalog
2. Voor elke enabled + configured server in profile:
   - stdio: spawn `subprocess.Popen([cmd, *args], env=..., stdin=PIPE, stdout=PIPE)`
   - sse/http: open persistent connection naar upstream URL
3. Aggregator vraagt elke backend: `tools/list` → verzamelt alle tools
4. Tool names krijgen prefix: `github__create_issue`, `sentry__search_errors`
5. Bij `tools/call`: Router kijkt op prefix, stuurt door naar juiste backend
6. Resultaat komt terug, wordt geproxyed naar agent
7. Bij afsluiten: alle subprocesses netjes terminaten

**Tech challenges:**

- stdio subprocess lifecycle management (zombies, crashes, restarts)
- async I/O voor multiple backends (threading, niet asyncio — stdlib)
- JSON-RPC 2.0 message framing over stdio (newline-delimited JSON)
- Timeout handling per backend
- Error isolation: als één backend crasht, blijven anderen werken

**Mock-first:** Eerst bouwen met een `MockBackend` die canned responses
returned. Dan pas echte subprocess spawning.

### 4B. Web Dashboard (`src/kater/web/`)

**Doel:** Een dashboard dat in de browser draait, served door de API
server. Geen build step, geen npm, geen framework. Pure HTML/CSS/JS.

**Ontwerp principles:**

1. **Zero dependencies** — geen React, geen Vue, geen Tailwind. Alles
   vanilla. CSS custom properties voor theming.
2. **Inline served** — HTML/CSS/JS wordt als string in Python ingebed
   en geserveerd op `GET /` door de API handler. Eén bestand.
3. **WebSocket-driven** — real-time updates zonder polling
4. **Dark default** — donker thema, clean, modern
5. **Mobile-first responsive** — werkt op telefoon

**Pages:**

| Route     | View                                        |
|-----------|---------------------------------------------|
| `/`       | Dashboard: status, health, quick stats      |
| `/catalog`| Browse MCP servers, toggle on/off, filter   |
| `/evals`  | Telemetry charts, tool performance tables   |
| `/deploy` | Generate configs for any platform           |
| `/settings`| Auth, CORS, storage, rate limit            |

**Layout:**

```
┌──────────────────────────────────────────┐
│ KATER                          [profile▼] │
├──────┬───────────────────────────────────┤
│      │                                   │
│ Dash │     (page content)                │
│ Catal│                                   │
│ Evals│                                   │
│ Deploy│                                   │
│ Sett │                                   │
│      │                                   │
└──────┴───────────────────────────────────┘
```

**Implementatie:**

```
src/kater/web/
├── __init__.py
├── handler.py     # serve index.html at GET /
└── assets.py      # CSS + JS als Python strings (of lees uit files)
```

CSS systeem:

```css
:root {
  --bg: #0d1117;
  --bg-elevated: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --text-dim: #8b949e;
  --accent: #2f81f7;
  --green: #3fb950;
  --red: #f85149;
  --yellow: #d29922;
  --radius: 8px;
  --font: -apple-system, system-ui, sans-serif;
}
```

### 4C. ChatGPT / Remote Compatibiliteit

**Doel:** Kater werkt met ChatGPT's "Remote MCP" feature.

**Wat ChatGPT nodig heeft:**
1. Publiek bereikbare SSE endpoint (`https://kater.chefgroep.online/sse`)
2. OAuth 2.0 met PKCE flow (authorization code)
3. `/.well-known/oauth-authorization-server` discovery
4. Tool list via SSE MCP protocol

**Wat we bouwen:**
- Cloudflare Tunnel deploy script (geen open ports op server)
- OAuth flow endpoints (`/auth/authorize`, `/auth/token`)
- `.well-known/` discovery endpoints
- Profile wordt bepaald door URL parameter: `/sse?profile=ops`

## 5. Module Structuur (v1.0)

```
src/kater/
├── __init__.py
├── cli.py              # CLI entry point (Typer)
├── serve.py            # Unified: API + MCP + WS in één proces
│
├── api.py              # REST API handler (stdlib http.server)
├── websocket.py        # WebSocket server (stdlib, RFC 6455)
├── mcp_server.py       # MCP SSE server (FastMCP)
│
├── proxy/              # ★ NIEUW: MCP Proxy Engine
│   ├── __init__.py
│   ├── manager.py      # ProxyManager — backend lifecycle
│   ├── stdio_backend.py
│   ├── sse_backend.py
│   ├── router.py
│   └── aggregator.py
│
├── web/                # ★ NIEUW: Web Dashboard
│   ├── __init__.py
│   ├── handler.py
│   └── assets.py
│
├── profiles.py         # MCP server catalog (29+ servers)
├── registry.py         # Native tool registry
├── adapters/           # External adapter detection
│   ├── external.py
│   └── utrecht.py
│
├── settings.py         # Auth, CORS, storage, overrides
├── storage.py          # SQLite + JSONL telemetry backend
├── telemetry.py        # Event recording + aggregation
│
├── deploy.py           # Deployment config generation
├── doctor.py           # Diagnostics
├── chains.py           # Tool chain definitions
├── autofix.py          # Doctor fix application
├── init.py             # .kater/ project initialization
│
├── ansi.py             # CLI formatting (tables, colors)
├── openapi_spec.py     # OpenAPI 3.1 generation
└── oauth.py            # ★ NIEUW: OAuth flow endpoints
```

## 6. Build Volgorde (Fases)

### Fase 1: MCP Proxy Engine (kernwaarde)
Zonder dit is Kater een catalogueertool, geen gateway.

1. `proxy/mock_backend.py` — canned responses voor tests
2. `proxy/stdio_backend.py` — spawn subprocess, JSON-RPC framing
3. `proxy/aggregator.py` — verzamel tools van alle backends
4. `proxy/router.py` — route tool calls op prefix
5. `proxy/manager.py` — lifecycle, health checks, restarts
6. Integreer in `mcp_server.py`: proxy tools + native tools
7. Tests: mock backend → echte npx server → error scenarios

**Acceptatie:** `kater serve --profile ops` met GitHub token gezet
exposed zowel `kater_doctor` als `github__*` tools in één MCP surface.

### Fase 2: Web Dashboard
1. `web/assets.py` — CSS systeem, JS utilities, componenten
2. `web/handler.py` — serve HTML bij `GET /`
3. Dashboard page — status + health + WS live feed
4. Catalog page — server grid met toggle knoppen
5. Evals page — tool performance tables
6. Deploy page — format selector + code preview
7. Settings page — auth/CORS/storage forms

**Acceptatie:** Open `http://localhost:9091/` in browser → volledig
dashboard. Toggle een server → direct zichtbaar. WebSocket updates
werken real-time.

### Fase 3: Remote + ChatGPT
1. `oauth.py` — authorization code flow met PKCE
2. `.well-known/` discovery endpoints
3. Cloudflare Tunnel deploy script (automated)
4. Subdomain setup: `kater.chefgroep.online`
5. SSL via Cloudflare (automatic)
6. Profile routing via URL: `/sse?profile=ops`

**Acceptatie:** ChatGPT → Settings → MCP → `https://kater.chefgroep.online/sse`
→ OAuth login → tools verschijnen in ChatGPT.

### Fase 4: Hardening + Polish
1. Interactive CLI mode (`kater interactive`)
2. Plugin system (dynamic server registration via Python entry points)
3. Backup/restore settings
4. Multi-profile MCP routing (meerdere profiles tegelijk)
5. Rate limiting per backend
6. Circuit breaker pattern voor falende backends
7. Audit log (wie heeft wat aangezet/uitgezet)
8. Proper logging (structured JSON logs)

## 7. Technische Beslissingen

| Beslissing             | Keuze         | Waarom                          |
|------------------------|---------------|---------------------------------|
| Web framework          | stdlib        | Geen dependency, draait overal  |
| MCP library            | mcp (FastMCP) | Bestaand, maintained            |
| Database               | SQLite        | Zero-config, stdlib, file-based |
| WebSocket              | stdlib        | Geen dependency                 |
| Web UI framework       | Vanilla JS    | Geen build step, geen npm       |
| CSS approach           | Custom props  | Themable, dark-first            |
| Auth                   | Bearer/OAuth  | Standaard, breed supported      |
| Python versie          | 3.11+         | match-type, StrEnum             |
| Packaging              | uv + pyproject| Snel, modern                    |

## 8. Wat Niét Te Bouwen

- Geen React/Vue/Svelte — te veel overhead voor een dashboard
- Geen Redis/Postgres dependency — SQLite is genoeg
- Geen Kubernetes operator — docker-compose is voldoende
- Geen user accounts/multi-tenancy — single-owner gateway
- Geen billing/quotas — het is een dev tool
- Geen APM/OpenTelemetry — eigen telemetry is voldoende

## 9. Bestaande Code: Behouden of Herschrijven

| Module             | Actie     | Reden                          |
|--------------------|-----------|--------------------------------|
| cli.py             | Behouden  | Werkt, 27 commands             |
| api.py             | Uitbreiden| Voeg / proxy endpoints toe     |
| mcp_server.py      | **Herschrijven** | Moet proxy integreren   |
| profiles.py        | Behouden  | Catalog is compleet            |
| registry.py        | Behouden  | Native tools werken            |
| settings.py        | Behouden  | Auth/settings werken           |
| storage.py         | Behouden  | SQLite backend is solide       |
| telemetry.py       | Behouden  | Evals werken                   |
| deploy.py          | Behouden  | 6 formats compleet             |
| websocket.py       | Uitbreiden| Voeg RPC toe naast broadcast   |
| serve.py           | Uitbreiden| Voeg proxy startup toe         |
| ansi.py            | Behouden  | CLI formatting werkt           |
| doctor.py          | Behouden  |                                |
| chains.py          | Behouden  |                                |
| openapi_spec.py    | Uitbreiden| Voeg proxy endpoints toe       |

## 10. Metrics Voor Succes

1. **Proxy werkt:** Agent ziet tools van GitHub + Sentry + native in één
   MCP verbinding
2. **Dashboard werkt:** Browser opent `localhost:9091` → volledig UI
3. **ChatGPT werkt:** Remote MCP verbinding via Cloudflare Tunnel
4. **Tests:** >200 passing, >90% coverage op proxy module
5. **Zero externe deps:** Alleen pydantic, typer, mcp
6. **Bootstrap tijd:** <2 seconden van `kater serve` tot ready
