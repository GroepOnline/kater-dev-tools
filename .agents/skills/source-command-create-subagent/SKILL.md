---
name: "source-command-create-subagent"
description: "Scaffold a focused Codex subagent at .cursor/agents/<name>.md with YAML frontmatter and a strict return contract. Use when a skill needs context-isolated lane work, parallel specialists, or independent verification. Pair with /create-skill for the twin chain."
---

# source-command-create-subagent

Use this skill when the user asks to run the migrated source command `create-subagent`.

## Command Template

# /create-subagent

Load and follow `.cursor/skills/kater-dev-tools-create-subagent/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Context-isolated execution lane
- Parallel specialist work (with `/parallel-lanes`)
- Independent verification after a skill defines the contract

## Twin chain

| Side | Path | Owns |
| --- | --- | --- |
| Skill | `.cursor/skills/<name>/SKILL.md` | When/why, sequencing, merge/report |
| Subagent | `.cursor/agents/<name>.md` | One focused execution lane |

If no skill exists yet, run `/create-skill` next and cross-link both files.
