---
name: parallel-lanes
description: >-
  Dispatch parallel Cursor subagents with disjoint file scopes (~4 lanes) and a
  coordinator integrate step. Use for multi-file refactors, spawn parallel agents,
  or when AGENTS.md parallel rule applies.
---

# /parallel-lanes

Load and follow `.cursor/skills/kater-dev-tools-parallel-lanes/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Multi-file refactors or independent workstreams
- Default project rule: fan out ~4 lanes; coordinator integrates
- **Hard rule:** disjoint file scopes — never edit the same file in parallel

## Twin chain

| Role | Path |
| --- | --- |
| Skill (dispatch contract) | `.cursor/skills/kater-dev-tools-parallel-lanes/SKILL.md` |
| One lane subagent | `.cursor/agents/parallel-lane.md` |
| Coordinator | Parent session — integrate, test, commit |

After all lanes return, run `/local-verify` before push.
