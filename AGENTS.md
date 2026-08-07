# PROJECT KNOWLEDGE BASE

**Generated:** 2026-07-11
**Commit:** 68e5d48
**Branch:** main

## OVERVIEW
Kater — developer-only MCP gateway for code agents. One curated MCP endpoint fronting 29+ upstream dev MCP servers (Native + GitHub + Sentry + Cloudflare + 29 more). `src/kater` package, Python 3.11–3.14, uv-managed, FastMCP + stdlib ThreadingHTTPServer.

## STRUCTURE
```
kater-dev-tools/
├── src/kater/        # package root
│   ├── cli.py        # Typer entry — 30+ subcommands (952 LOC god-file)
│   ├── runtime.py    # KaterRuntime: ordered lifecycle (API+WS+MCP threads)
│   ├── gateway.py    # ASGI middleware: proxies non-MCP paths to API port
│   ├── mcp_server.py # FastMCP build + AuthASGIMiddleware + proxy tool exec()
│   ├── websocket.py  # hand-rolled RFC6455 telemetry stream
│   ├── authgate.py   # AUTH SSOT (authenticate / should_proxy_to_api)
│   ├── settings.py   # SETTINGS SSOT (ListenConfig, RateLimiter, env layer)
│   ├── profiles.py   # MCP server catalog (29+ ToolSource) + visibility rules
│   ├── proxy/        # multi-backend MCP fan-out — see proxy/AGENTS.md
│   ├── api/          # stdlib REST surface, 3-file split — see api/AGENTS.md
│   ├── adapters/     # client-side MCP config rendering — see adapters/AGENTS.md
│   └── web/          # single-file HTML/CSS/JS dashboard — see web/AGENTS.md
├── tests/            # pytest, 417 tests, conftest auto-cleans .kater/
├── scripts/          # smoke.sh, e2e-mcp.sh, deploy-cloudflare.sh, systemd/
├── infra/cloudflare-mcp/  # bundled CF MCP server sub-infra
├── docs/             # deploy-local/server, cursor-setup, profiles
└── config/           # empty (generated at runtime by `kater deploy render`)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/change an MCP tool | `proxy/` or `registry.py` | native tools in registry; upstream in profiles.py |
| Change auth policy | `authgate.py` | single source of truth |
| Change bind/ports | `settings.ListenConfig` | don't read os.environ directly elsewhere |
| Add REST endpoint | `api/routes.py` + `openapi_spec._build_paths` | spec is drift-guarded by test |
| Change dashboard UI | `web/dashboard.py` | 2459 LOC single-file SPA |
| Add private server/tool | `KATER_EXTENSIONS_MODULE` hook (`extensions.py`) | never fork for org code |
| Deploy/gateway wiring | `gateway.py` + `mcp_server.py` | one-port tunnel trick |
| Secrets/credentials | `settings.apply_credentials_to_env` | stored creds → os.environ at startup |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| KaterRuntime | class | runtime.py:21 | ordered startup/shutdown, owns 3 threads |
| authenticate | fn | authgate.py | REST + MCP + WS share this one decision |
| ApiProxyMiddleware | class | gateway.py:112 | forwards non-/sse to API port (one-tunnel trick) |
| ProxyManager | class | proxy/manager.py | singleton; circuit breakers per backend |
| ToolSource | class | profiles.py | catalog entry (transport/risk/env) |
| render_dashboard | fn | web/dashboard.py:2442 | only Python fn; rest is inline HTML/CSS/JS |
| register_proxy_tools | fn | mcp_server.py | exec()-builds handlers from inputSchema |
| KaterSettings | class | settings.py | ListenConfig + env override layer |

## CONVENTIONS
- uv-only toolchain. `uv lock --check` gates CI; `pythonpath=["src","."]`.
- Ruff with bandit `S` ON by default (security-first lint). Per-file allowlists in pyproject are load-bearing — don't extend casually.
- `api/models.py` imports NOTHING from kater (intentional seam). `routes.py` imported for side-effect only.
- `kater serve` starts API(9091)+WS(9092)+MCP(9090, behind gateway middleware).

## ANTI-PATTERNS (THIS PROJECT)
- NEVER fork `kater-dev-tools` for org code — use `KATER_EXTENSIONS_MODULE` overlay (SPLIT_DECISION.md).
- NEVER expose `/sse` without `KATER_PUBLIC=1` + `KATER_AUTH_MODE`.
- NEVER commit `.kater/*` (live OAuth/SQLite), `.env`, or real keys. CI `no-org-leak.yml` blocks `chefgroep.nl`/`onlinechefgroep` outside an explicit allowlist + gitleaks full-history.
- NEVER re-flatten `api/` into `api.py` (recently split). NEVER break the OpenAPI drift-guard.
- CORS `*` blocked on public bind (cli.py:62 raises). `redirect_uri` rejects `javascript:`/`data:`/`file:`.

## UNIQUE STYLES
- Two transports, one auth function (`authgate.authenticate`) + one shared `RateLimiter`.
- Proxy invisible to REST (only reachable via MCP surface).
- MCP tool handlers synthesized at runtime via `exec()` from JSON-Schema (narrow namespace `{Any, proxy}`).
- `.opencode`/`.cursor` are user-home symlinks (gitignored) — don't commit.
- Typer commands take `--json`; `_print_json` renders.

## COMMANDS
```bash
uv sync --dev                 # install
uv run ruff check .           # lint (bandit on)
uv run mypy                   # type-check
uv run pytest -vv -x --tb=short -ra   # test (120s CI timeout)
kater serve                   # run gateway
./scripts/smoke.sh            # pre-deploy CLI matrix
./scripts/e2e-mcp.sh          # proxy E2E (needs live serve + KATER_PROXY=1)
docker compose up -d          # container (9090/9091/9092)
```

## NOTES
- God-files: web/dashboard.py (2459), cli.py (952), test_hardening.py (794), openapi_spec.py (745), api/routes.py (745), profiles.py (564), oauth.py (547).
- Storage dual-driver (SQLite default / JSONL) behind one interface; switch via settings.storage_backend.
- Telemetry avoids importing websocket (cycle) — broadcast hop lives in api/routes._ws_broadcast.
- Healthcheck port 9091; MCP 9090; WS 9092. Gateway on 9090 forwards non-/sse to 9091.
