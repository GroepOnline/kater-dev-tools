---
name: kater-dev-tools-create-skill
role: satellite
ambient: true
description: |-
  kater-dev-tools-specifieke skill-authoring-feiten. Chains up to skill-creator voor procedure, invarianten en safety gates.
use:
- "/create-skill"
extends: skill-creator
chains:
  skills:
  - skill-creator
invocable-by:
- user
- agent
- subagent
disable-model-invocation: false
context:
  project_types: []
  file_patterns: []
  tools: []
  repos: ['/home/sofie/kater-dev-tools']
  signals: []
owner: chefgroep
domain: skill-authoring
risk: read-only
last_reviewed: '2026-08-08'
---

# kater-dev-tools — skill-authoring

- Project-endpoint: `.cursor/skills/<naam>/SKILL.md` met geldige frontmatter.

Procedure, invarianten en gates: `skill-creator`.
