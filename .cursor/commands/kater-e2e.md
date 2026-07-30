---
name: kater-e2e
description: >-
  End-to-end gateway proof: REST, MCP SSE initialize/tools, WebSocket handshake.
  Use for e2e-mcp.sh, prove MCP works, or post-change gateway validation while
  the server is running.
---

# /kater-e2e

Load and follow `.cursor/skills/kater-e2e/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Best single proof the gateway works (`./scripts/e2e-mcp.sh`)
- Post-change validation when MCP SSE or WebSocket paths changed
- Server must already be running (opposite of smoke)

## Prerequisites

Run `/kater-gateway` first if the server is not up. Hand off to `.cursor/agents/kater-verify.md` for an isolated verify lane.

## Related

- `/local-verify` — canonical order before push
- `/pr-gate` — expects e2e green when gateway paths changed
