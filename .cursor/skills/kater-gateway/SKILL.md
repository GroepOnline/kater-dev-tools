---
name: kater-gateway
description: >-
  Start, configure, and verify the Kater MCP gateway locally or in cloud.
  Use for /kater-gateway, "kater serve", "kater up", gateway health, port
  wiring, or when an agent must prove the gateway works without adapter secrets.
---

# Kater gateway

Operator skill for the single-process gateway (REST + MCP SSE + WebSocket telemetry).

## Twin chain & handoffs

| Artifact | Path | When |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/kater-gateway/SKILL.md` | Serve + wiring contract |
| Subagent | `.cursor/agents/kater-verify.md` | Isolated verify lane after code changes |
| Related skills | `kater-e2e`, `kater-doctor`, `local-verify` | Deeper verify slices |

Hand off to **`kater-verify`** subagent for post-change proof; **`ci-fixer`** when CI fails on gateway paths; **`pr-gate`** before merge.

## Pre-reads

1. `AGENTS.md` (Cloud section — smoke vs live server, SQLite lock)
2. `README.md` Quick Start
3. Catalog from hooks (or `.cursor/hooks/fetch-cursor-artifacts.sh --print-markdown`)

Resolve repo at runtime — never hardcode org slugs:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

## Ports & koppelingen

| Surface | URL / port | Consumer |
| --- | --- | --- |
| MCP SSE | `http://127.0.0.1:9090/sse` | Cursor MCP (via `.cursor/mcp.json`) |
| REST + dashboard | `http://127.0.0.1:9091` | `curl`, browser, `./scripts/e2e-mcp.sh` |
| Health | `http://127.0.0.1:9091/health` | CI, smoke preflight, doctor |
| WebSocket telemetry | `ws://127.0.0.1:9092` | Dashboard live feed, e2e handshake |

## Serve

**Cloud-safe default** — core profile, no proxy backends (no adapter secrets):

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync --dev
uv run kater serve --profile core --no-proxy --host 127.0.0.1
```

**Desktop IDE one-shot** — init + write gitignored Cursor MCP config + serve:

```bash
uv run kater up
```

`kater up` writes `.cursor/mcp.json` (gitignored). Point Cursor at the SSE URL above.

Health check:

```bash
curl -s http://127.0.0.1:9091/health
```

## Verify ladder

Run in this order (see `local-verify` for environment matrix):

1. **Lint/test** (no server): `uv run ruff check .`, `uv run mypy`, `uv run pytest`
2. **Doctor** (no server): `uv run kater doctor --json` → skill `kater-doctor`
3. **Serve + health** → this skill
4. **E2e** (server **running**): `./scripts/e2e-mcp.sh` → skill `kater-e2e`
5. **Smoke** (server **stopped**): `./scripts/smoke.sh` → broad CLI regression
6. **Pre-commit** (before push): `uvx pre-commit install` then `uvx pre-commit run --all-files`

## CLI shortcuts

```bash
uv run kater status
uv run kater mcp list
uv run kater enable <name>    # persists to .kater/kater.db
uv run kater disable <name>
uv run kater config --profile core
```

Proxy backends need secrets in `.kater/.env` and Node/`npx` for stdio adapters. With `--no-proxy`, native tools still work; proxied servers report `configured: false`.

## Stop conditions

- Do not commit `.kater/` or `.cursor/mcp.json` (runtime outputs).
- `./scripts/smoke.sh` while `kater serve` is up → SQLite concurrent-writer / disk I/O error; **stop serve first**.
- `./scripts/e2e-mcp.sh` requires a live server on `:9091`.
- Do not invent adapter API keys; report missing config from doctor/status JSON.
- SSOT is `.cursor/` only — never copy skills into `.agents` / `.claude` / `.codex`.

## Return format

- Serve: ports 9090/9091/9092 + health JSON snippet
- Verify: exit codes for smoke/e2e/pytest + one-line pass/fail per step
- Handoff note if delegating to `kater-verify` or `ci-fixer`
