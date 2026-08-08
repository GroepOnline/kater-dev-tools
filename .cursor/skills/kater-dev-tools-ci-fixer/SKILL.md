---
name: kater-dev-tools-ci-fixer
role: satellite
ambient: true
description: |-
  kater-dev-tools-specifieke ci-ops-feiten. Chains up to groeponline-ci-fix-loop voor procedure, invarianten en safety gates.
use:
- "/ci-fixer"
- "rode checks"
extends: groeponline-ci-fix-loop
chains:
  skills:
  - groeponline-ci-fix-loop
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
domain: ci-ops
risk: read-only
last_reviewed: '2026-08-08'
---

# kater-dev-tools — ci-ops

- Twin subagent: `.cursor/agents/ci-fixer.md`.
- Fix contract: CI/lint/tests only, minimale diff; reproduceer lokaal, herbekijk checks na push.

Procedure, invarianten en gates: `groeponline-ci-fix-loop`.
