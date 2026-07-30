---
name: local-verify
description: >-
  Umbrella verify matrix: what to test on cloud VM vs local desktop vs Docker,
  port koppelingen, and canonical order of operations before push.
  Use for /local-verify, "how do I verify", desktop vs cloud testing, or pre-PR
  evidence planning.
---

# Local verify

Single reference for **where** to run **which** proof, and in **what order**.

## Twin chain & handoffs

| Artifact | Path | When |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/local-verify/SKILL.md` | Matrix + ordering |
| Subagent — verify | `.cursor/agents/kater-verify.md` | Read-only doctor/health/e2e/smoke lane |
| Subagent — CI fix | `.cursor/agents/ci-fixer.md` | Red checks → minimal fix loop |
| Subagent — PR gate | `.cursor/agents/pr-gate.md` | Merge-ready evaluation |
| Subagent — parallel lane | `.cursor/agents/parallel-lane.md` | One disjoint implementation lane |
| Skill — CI fix | `.cursor/skills/ci-fixer/SKILL.md` | When to delegate CI fixes |
| Skill — PR gate | `.cursor/skills/pr-gate/SKILL.md` | Merge-ready contract |
| Skill — parallel dispatch | `.cursor/skills/parallel-lanes/SKILL.md` | ~4-lane fan-out before verify |
| Child skills | `kater-gateway`, `kater-doctor`, `kater-e2e`, `kater-dashboard` | Deep slices |

Delegate an isolated verify lane to **`kater-verify`**. Use **`parallel-lanes`** when splitting implementation work; **`ci-fixer`** after push when checks fail.

## Pre-reads

1. `AGENTS.md` — Cloud vs local constraints
2. `.github/workflows/ci.yml` — CI job order
3. Catalog from hooks

## Port koppelingen (all environments)

| Port | Protocol | Role | Typical client |
| --- | --- | --- | --- |
| 9090 | HTTP SSE | MCP gateway | Cursor → `.cursor/mcp.json` → `/sse` |
| 9091 | HTTP | REST + dashboard | `curl`, browser, e2e REST checks |
| 9092 | WebSocket | Telemetry stream | Dashboard live feed, e2e WS check |

Loopback defaults: `127.0.0.1`. Docker publishes `${MCP_PORT:-9090}`, `${API_PORT:-9091}`, `${WS_PORT:-9092}`.

## Environment matrix

| Test | Cloud VM | Local desktop IDE | Docker compose |
| --- | --- | --- | --- |
| `uv sync --dev` | Yes (boot script) | Yes | N/A (image build) |
| `uv run ruff check .` | Yes | Yes | In CI / dev container |
| `uv run mypy` | Yes | Yes | In CI |
| `uv run pytest` (~100–120s) | Yes | Yes | Optional |
| `uv run kater doctor --json` | Yes | Yes | Exec into container |
| `kater serve --no-proxy` | Yes (default) | Yes | `docker compose up` |
| `curl …/health` | Yes | Yes | Host-mapped `:9091` |
| `./scripts/e2e-mcp.sh` | Yes (serve up) | Yes | After compose healthy |
| `./scripts/smoke.sh` | Yes (serve **down**) | Yes | Stop container first |
| Browser dashboard | No (use REST) | Yes — `/dashboard` | Yes — mapped port |
| Cursor MCP live tools | Optional | Yes — `kater up` | Advanced (host networking) |
| Proxy backends (29+ MCPs) | Usually `--no-proxy` | `.kater/.env` + Node | `.env` + secrets volume |
| `uvx pre-commit run --all-files` | Yes | Yes (install hooks once) | Dev machine |
| Private deployment overlay | N/A here | Optional extension repo | Documented elsewhere |

## Canonical order of operations

### A. During development (repeat)

1. **Static** — `uv run ruff check .` → `uv run mypy` → `uv run pytest`
2. **Doctor** (no server) — `uv run kater doctor --json`
3. **Serve** — `uv run kater serve --profile core --no-proxy --host 127.0.0.1`
4. **Health** — `curl -s http://127.0.0.1:9091/health`
5. **E2e** (server running) — `./scripts/e2e-mcp.sh`
6. **Stop server**
7. **Smoke** (server stopped) — `./scripts/smoke.sh`

### B. Before push / PR

1. Complete ladder A (or delegate to **`kater-verify`**)
2. **Pre-commit** — `uvx pre-commit install` (once) then `uvx pre-commit run --all-files`
3. **`gh pr checks`** / **`ci-fixer`** after push

### C. Desktop-only extras

- `uv run kater up` — writes `.cursor/mcp.json`, opens MCP koppeling to `:9090/sse`
- Manual dashboard pass — `http://127.0.0.1:9091/dashboard`
- Full proxy profile when `.kater/.env` has adapter keys

### D. Docker compose

```bash
docker compose up --build -d
curl -s http://127.0.0.1:9091/health
./scripts/e2e-mcp.sh   # against published ports
docker compose down    # before smoke if using same .kater volume
```

Compose defaults: `KATER_PUBLIC=1`, `KATER_AUTH_MODE=oauth` — not cloud-safe defaults; use for deploy-shaped testing only.

## Lint/test commands (all environments)

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

## Stop conditions

- Smoke + serve simultaneously → SQLite concurrent-writer error
- Do not commit `.kater/`, `.cursor/mcp.json`
- Cloud agents: do not claim browser-only verification without REST/e2e evidence
- SSOT is `.cursor/` only

## Return format

- Table row per environment: what ran, pass/fail, blockers
- Explicit note if desktop-only steps were skipped in cloud
- Handoff: `pr-gate` when opening PR, `ci-fixer` on red CI
