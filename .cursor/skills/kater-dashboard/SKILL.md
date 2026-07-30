---
name: kater-dashboard
description: >-
  Verify the Kater web dashboard and REST API surfaces on :9091.
  Use for /kater-dashboard, dashboard hydration, /api/status, telemetry UI,
  or when REST checks matter but full MCP e2e is out of scope.
---

# Kater dashboard

The dashboard is server-rendered inline HTML in `src/kater/web/dashboard.py` — no separate frontend build.

## Twin chain & handoffs

| Artifact | Path | When |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/kater-dashboard/SKILL.md` | Dashboard + REST verify |
| Subagent | `.cursor/agents/kater-verify.md` | Full gateway lane |
| Related | `kater-e2e`, `kater-gateway` | MCP/WS proof + serve |

Dashboard-only checks do **not** replace `./scripts/e2e-mcp.sh` for MCP changes. Hand off to **`kater-e2e`** when SSE/WS touched.

## Pre-reads

1. `src/kater/web/dashboard.py` — single-file UI (Edit-tool lock: one agent per file)
2. `AGENTS.md` — validate via REST/CLI/e2e, not headless GUI automation in cloud
3. `README.md` — dashboard URL and API overview

## URLs (server running)

| Surface | URL |
| --- | --- |
| Dashboard | `http://127.0.0.1:9091/dashboard` |
| Root redirect | `http://127.0.0.1:9091/` |
| OpenAPI | `http://127.0.0.1:9091/api/spec` |
| Health | `http://127.0.0.1:9091/health` |

Serve:

```bash
uv run kater serve --profile core --no-proxy --host 127.0.0.1
```

## Verify paths

### Cloud / headless (preferred for agents)

Use REST — same data the dashboard hydrates from:

```bash
curl -s http://127.0.0.1:9091/health
curl -s http://127.0.0.1:9091/api/status
curl -s http://127.0.0.1:9091/api/catalog
curl -s http://127.0.0.1:9091/api/spec | head
```

Or run `./scripts/e2e-mcp.sh` (includes REST subset + MCP + WS).

CLI equivalents:

```bash
uv run kater status --json
uv run kater mcp list --json
uv run kater telemetry --json
```

### Local desktop IDE

1. Serve or `uv run kater up`
2. Open `http://127.0.0.1:9091/dashboard` in browser
3. Confirm: no blocking confirm overlay on load; server catalog renders; enable/disable toggles persist (SQLite `.kater/kater.db`)

WebSocket telemetry stream feeds live updates on `:9092` (dashboard client); e2e validates the upgrade handshake.

## Koppelingen

```
Browser → :9091/dashboard → REST /api/* → SQLite .kater/
Cursor  → :9090/sse (MCP) — separate from dashboard HTML
Agents  → prefer curl/e2e over GUI scraping in cloud
```

## Stop conditions

- Do not use browser automation in cloud VM as primary proof — use REST/e2e
- Concurrent edits to `dashboard.py` from parallel agents will conflict — see `parallel-lanes`
- Changing `_CSS` vs `_JS` sections still locks the whole file

## Return format

- Health + `/api/status` JSON snippets (or e2e REST pass lines)
- Desktop: manual OK/not OK for hydration (if operator tested)
- Handoff to `kater-e2e` if MCP/dashboard coupling changed
