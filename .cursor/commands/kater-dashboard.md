---
name: kater-dashboard
description: >-
  Verify the Kater web dashboard and REST API surfaces on :9091. Use for
  dashboard hydration, /api/status, telemetry UI, or when REST checks matter
  but full MCP e2e is out of scope.
---

# /kater-dashboard

Load and follow `.cursor/skills/kater-dashboard/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Dashboard and REST API checks on `:9091`
- `/api/status`, telemetry UI, server-rendered dashboard changes
- REST-only proof when MCP e2e is unnecessary

## Limits

Dashboard-only checks do **not** replace `./scripts/e2e-mcp.sh` when MCP SSE or WebSocket code changed — use `/kater-e2e` instead.

## Related

- `/kater-gateway` — serve contract and ports
- `.cursor/agents/kater-verify.md` — full gateway verify lane
