---
name: kater-e2e
description: End-to-end gateway proof: REST, MCP SSE initialize/tools, WebSocket handshake.
details: Use for /kater-e2e, e2e-mcp.sh, "prove MCP works", or post-change gateway validation while the server is running.
---

# Kater e2e

Best single proof the gateway works: `./scripts/e2e-mcp.sh` exercises REST, real MCP client, and WS.

## Twin chain & handoffs

| Artifact | Path | When |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/kater-e2e/SKILL.md` | E2e contract + prerequisites |
| Subagent | `.cursor/agents/kater-verify.md` | Automated verify lane |
| Related | `kater-gateway`, `local-verify` | Serve order + environment matrix |

Use **`parallel-lane`** subagent only for disjoint code paths; e2e itself is sequential after serve. **`pr-gate`** expects e2e green when gateway paths changed.

## Pre-reads

1. `scripts/e2e-mcp.sh` — exact checks
2. `AGENTS.md` — e2e requires running server (opposite of smoke)
3. Skill `kater-gateway` — serve command and ports

## Prerequisites

Server **must be running** on loopback:

```bash
uv run kater serve --profile core --no-proxy --host 127.0.0.1
```

Preflight:

```bash
curl -s http://127.0.0.1:9091/health
```

If health fails, do not run e2e — fix serve first (`kater-doctor` → `kater-gateway`).

## Run e2e

```bash
./scripts/e2e-mcp.sh
```

What it validates (see script for full list):

| Check | Target |
| --- | --- |
| REST | `/health`, `/api/status`, `/api/catalog`, `/api/spec` on `:9091` |
| MCP SSE | `http://127.0.0.1:9090/sse` — initialize + tools/list |
| WebSocket | `:9092` — HTTP upgrade handshake |

## Order of operations (with siblings)

```
doctor (stopped) → serve → health → e2e (running) → stop serve → smoke (stopped)
```

Never run `./scripts/smoke.sh` while serve is up (SQLite lock). Never run e2e while stopped.

## Environment notes

| Where | E2e |
| --- | --- |
| Cloud VM | Default: `--no-proxy` serve + e2e (no adapter secrets) |
| Local desktop | Optional `KATER_PROXY=1` + `.kater/.env` for proxied backends |
| Docker compose | `docker compose up` then hit published `9091/9090/9092` (see `local-verify`) |

## Stop conditions

- Exit non-zero → capture `[FAIL]` lines; do not claim gateway verified
- REST-only pass is insufficient — MCP + WS must pass
- Do not skip e2e when changing `src/kater/proxy/`, `src/kater/mcp/`, or API routes

## Return format

- Exit code + per-check ok/FAIL summary from script output
- Serve profile used (`core --no-proxy` vs ops/proxy)
- Next step: smoke (after stop) or `ci-fixer` / `kater-verify`
