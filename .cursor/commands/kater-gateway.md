---
name: kater-gateway
description: >-
  Start, configure, and verify the Kater MCP gateway locally or in cloud.
  Use for kater serve, kater up, gateway health, port wiring, or when an agent
  must prove the gateway works without adapter secrets.
---

# /kater-gateway

Load and follow `.cursor/skills/kater-gateway/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Start or restart the gateway (`kater serve`, `kater up`)
- Health checks on REST (:9091), MCP SSE (:9090), WebSocket (:9092)
- Prove core gateway wiring without adapter API keys

## Related handoffs

| Need | Command / artifact |
| --- | --- |
| Post-change verify lane | `.cursor/agents/kater-verify.md` |
| Full e2e MCP proof | `/kater-e2e` |
| Environment diagnostics | `/kater-doctor` |
| CI red on gateway paths | `/ci-fixer` |
