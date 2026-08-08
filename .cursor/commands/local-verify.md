---
name: local-verify
description: >-
  Umbrella verify matrix: what to test on cloud VM vs local desktop vs Docker,
  port koppelingen, and canonical order of operations before push. Use for how
  do I verify, desktop vs cloud testing, or pre-PR evidence planning.
---

# /local-verify

Load and follow `.cursor/skills/kater-dev-tools-local-verify/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Planning where and how to verify before push
- Cloud VM vs local desktop vs Docker matrix
- Canonical order: lint → test → smoke (server stopped) → serve → e2e

## Child skills (deep slices)

| Slice | Command |
| --- | --- |
| Serve + ports | `/kater-gateway` |
| Doctor / wiring | `/kater-doctor` |
| MCP e2e | `/kater-e2e` |
| Dashboard REST | `/kater-dashboard` |
| Parallel implementation | `/parallel-lanes` |

Delegate an isolated verify lane to `.cursor/agents/kater-verify.md`.
