# CLAUDE.md — Kater Dev Tools

Developer-only MCP gateway that proxies 29+ MCP servers behind one endpoint, gated by
profiles. Python 3.11–3.14, `uv`-managed, Typer CLI, FastMCP SSE server, SQLite telemetry.

## Quick orientation

- **Entry point:** `src/kater/cli.py` (`kater` script via Typer). `kater serve` boots the
  API + MCP/SSE + WebSocket in one process (`runtime.py`).
- **Core modules:** `api.py` (REST RouteTable pipeline), `mcp_server.py` (MCP/SSE +
  authgate middleware), `proxy/` (MCP proxy engine: manager, stdio/sse/streamable_http
  backends, aggregator, registry), `profiles.py` (the 29+ server catalog — single source
  of truth for what tools exist), `authgate.py` (auth policy SSOT), `settings.py` (bind/
  CORS/storage SSOT), `oauth.py`, `telemetry.py`, `tunnel.py`, `deploy.py`, `web/dashboard.py`.
- **Layout:** `src/kater/` (library + CLI), `tests/` (417 tests mirrored per-module),
  `scripts/` (deploy/sync shell+py helpers), `infra/cloudflare-mcp/`, `docs/`, `.agents/`
  (Cursor skills: codebase-design, frontend-design, ui-ux-pro-max, happyhorse-1-0).

## Commands

```bash
uv sync --dev            # install deps + dev tooling
uv run ruff check .      # lint (E/F/I/UP/B/S/RUF; bandit security enabled)
uv run mypy              # type check (lenient, untyped third-party stubs)
uv run pytest -v         # 417 tests, testpaths=tests
./scripts/smoke.sh       # runtime smoke test
./scripts/e2e-mcp.sh     # requires `kater serve` with KATER_PROXY=1
```

## Conventions

- **Python >=3.11**, line-length 100. Ruff `select` includes bandit (`S`) for security —
  keep secrets out of code, use list-form `subprocess` argv (never shell=True), no asserts
  in prod paths. Per-file ignores are already tuned in `pyproject.toml`; match them rather
  than adding new blanket ignores.
- **Profiles are the contract.** `profiles.py` declares every proxied server + its
  profiles; new tools/mcp servers get added there first, then wired through `proxy/`.
- **SSOT discipline:** auth in `authgate.py`, bind/CORS/storage in `settings.py`, OpenAPI
  in `openapi_spec.py` (drift-guarded — keep it in sync with `api.py`).
- **Public exposure requires auth:** `KATER_PUBLIC=1` + OAuth/API-key. Loopback dev runs
  with auth disabled. See README "Deployment" + `SECURITY.md`.
- **MCP server launch commands** in `profiles.py` are operator-chosen (npx/uvx), not user
  input — don't treat them as untrusted; don't add user-controlled interpolation.

## Testing expectations

- Every module under `src/kater/` has a matching `tests/test_*.py`. Add tests alongside
  changes; proxy/stdio e2e and security/hardening tests are required to stay green.
- `test_profiles.py` / `test_profiles_extended.py` guard the catalog — keep in sync when
  editing `profiles.py`.
- `test_openapi_spec.py` guards API/OpenAPI drift.

## Notable gotchas

- `mcp_server.py` uses FastMCP + authgate middleware; middleware ordering matters.
- `proxy/stdio_backend.py` whitelists env to child processes — don't leak credentials.
- `websocket.py` uses sha1 per RFC 6455 handshake (S324 ignored on purpose).
- `.opencode` may be deleted in working tree; not tracked intentionally.
- Private extensions load via `KATER_EXTENSIONS_MODULE` (see `extensions.py`, `.env.example`).

## Reference

Full API/CLI/deploy docs in `README.md`. Ops runbooks in `docs/ops/`. Cursor setup in
`docs/cursor-setup.md`. Security policy in `SECURITY.md`.
