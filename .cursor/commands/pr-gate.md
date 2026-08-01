---
name: pr-gate
description: >-
  Evaluate and fix one PR until merge-ready using Kater PR gate rules and gh.
  Use for pr gate, merge-ready checks, or when CI/review threads block merge.
  Delegate lane work to the pr-gate subagent.
---

# /pr-gate

Load and follow `.cursor/skills/pr-gate/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Merge-ready evaluation on the current PR
- CI or review threads block merge
- Gate verdict needed (`PASS`, `WARN`, `BLOCK`) on recorded head SHA

## Twin chain

| Artifact | Path | Role |
| --- | --- | --- |
| Skill (this command) | `.cursor/skills/pr-gate/SKILL.md` | When/why, gate contract |
| Subagent | `.cursor/agents/pr-gate.md` | One-PR gate lane execution |

For isolated gate lane work, dispatch the `pr-gate` subagent. Merge remains operator-gated.
