---
name: kater-doctor
description: >-
  Run Kater doctor diagnostics, fix plans, and safe apply for MCP/Cursor wiring.
  Use for kater doctor, MCP config drift, Cursor mcp.json mismatches, or
  pre-serve environment checks.
---

# /kater-doctor

Load and follow `.cursor/skills/kater-doctor/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Profile, adapter secret, or Cursor MCP wiring drift
- Pre-serve environment checks
- `--fix-plan` / `--apply` doctor workflows

## Related handoffs

| Need | Command / artifact |
| --- | --- |
| Serve + health after fixes | `/kater-gateway` |
| Full verify lane | `.cursor/agents/kater-verify.md` |
| Environment matrix | `/local-verify` |
| CI doctor step failed | `/ci-fixer` |
