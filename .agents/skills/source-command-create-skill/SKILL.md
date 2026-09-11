---
name: "source-command-create-skill"
description: "Scaffold a Codex Agent Skill under .cursor/skills/<name>/SKILL.md with valid frontmatter, twin-chain hookup to a subagent when needed, and a short verify pass. Use when adding or upgrading a reusable workflow skill."
---

# source-command-create-skill

Use this skill when the user asks to run the migrated source command `create-skill`.

## Command Template

# /create-skill

Load and follow `.cursor/skills/kater-dev-tools-create-skill/SKILL.md`.

Do not invent a parallel procedure. Prefer the skill SSOT under `.cursor/`.

## When to use

- Adding a new reusable agent workflow
- Upgrading or splitting an existing skill
- Pairing with `/create-subagent` for the twin chain (skill owns sequence; subagent owns one lane)

## SSOT

| Artifact | Path |
| --- | --- |
| Skill (this command) | `.cursor/skills/kater-dev-tools-create-skill/SKILL.md` |
| Twin subagent skill | `.cursor/skills/create-subagent/SKILL.md` |
| Subagent output | `.cursor/agents/<name>.md` |

Keep skills and agents under `.cursor/` only — no mirrored copies elsewhere.
