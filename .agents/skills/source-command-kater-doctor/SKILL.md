---
name: "source-command-kater-doctor"
description: "Run Kater doctor diagnostics, fix plans, and safe apply for MCP/Codex wiring. Use for kater doctor, MCP config drift, Codex mcp.json mismatches, or pre-serve environment checks."
---

# source-command-kater-doctor

Use this skill when the user asks to run the migrated source command `kater-doctor`.

## Command Template

# /kater-doctor

Load and follow `.cursor/skills/kater-doctor/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Profile, adapter secret, or Codex MCP wiring drift
- Pre-serve environment checks
- `--fix-plan` / `--apply` doctor workflows

## Related handoffs

| Need | Command / artifact |
| --- | --- |
| Serve + health after fixes | `/kater-gateway` |
| Full verify lane | `.cursor/agents/kater-verify.md` |
| Environment matrix | `/local-verify` |
| CI doctor step failed | `/ci-fixer` |
