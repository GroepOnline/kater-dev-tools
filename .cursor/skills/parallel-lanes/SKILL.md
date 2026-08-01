---
name: parallel-lanes
description: >-
  Dispatch parallel Cursor subagents with disjoint file scopes (~4 lanes) and a
  coordinator integrate step. Use for /parallel-lanes, multi-file refactors,
  "spawn parallel agents", or when AGENTS.md parallel rule applies.
---

# Parallel lanes

Encode the project default: **fan out independent work; never edit the same file in parallel.**

## Twin chain & handoffs

| Artifact | Path | When |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/parallel-lanes/SKILL.md` | Dispatch contract |
| Subagent | `.cursor/agents/parallel-lane.md` | One isolated lane |
| Coordinator | Parent session | Integrate, test, commit |
| After integrate | `local-verify`, `kater-verify`, `ci-fixer`, `pr-gate` | Proof + ship |

Launch **`parallel-lane`** subagent per lane. Coordinator runs **`local-verify`** ladder after all lanes return.

## Why disjoint scopes

The Edit tool locks the **entire file**, not a section. Two agents editing one file causes:

> file has been modified since read

Seen on `dashboard.py` (`_CSS` vs `_JS` lanes). **Rule:** one agent → one file set; shared file → **sequential** lanes only.

## When to parallelize

- Multi-part tasks with independent files (e.g. separate skills, API module + tests file)
- Docs/skills/agents split across workers (this repo's cloud-init pattern)
- **Not** for: same-file dashboard edits, merge conflict resolution, single-line fixes

## Dispatch template

```
AGENT A — <scope>: <goal> → ONLY <files/constants>
AGENT B — <scope>: <goal> → ONLY <files/constants>
AGENT C — <scope>: <goal> → ONLY <files/constants>
AGENT D — <scope>: <goal> → ONLY <files/constants>
(coordinator): merge summaries, conflict check, full verify, commit
```

Target **~4 agents** in flight; start the next batch when a lane completes.

Each prompt must be **self-contained**: goal, hard file allowlist, constraints ("do not touch other code"), expected return (summary + files touched).

## Example (skills expansion)

| Lane | Scope | Files |
| --- | --- | --- |
| A | Expand gateway skill | `.cursor/skills/kater-gateway/SKILL.md` |
| B | New doctor + e2e skills | `.cursor/skills/kater-doctor/`, `kater-e2e/` |
| C | Dashboard + local-verify | `.cursor/skills/kater-dashboard/`, `local-verify/` |
| D | Agents + hooks | `.cursor/agents/*.md` (sequential if same agent file) |

Coordinator: read all summaries → `rg` for accidental cross-edits → `local-verify` static ladder.

## Coordinator integrate checklist

1. Collect each lane's file list + summary
2. `git diff` / `git status` — no unexpected overlap
3. Resolve conflicts **sequentially** if two lanes touched one file (should not happen)
4. Run full verify (see `local-verify`):
   - `uv run ruff check .` → `uv run mypy` → `uv run pytest`
   - doctor → serve → health → e2e → stop → smoke
   - `uvx pre-commit run --all-files` before push
5. Single commit or ordered commits per operator preference
6. **`pr-gate`** / **`ci-fixer`** after push

## Hard rules

- Never assign the same file to two parallel agents
- If scope creeps into one file, pause and re-serialize
- Never force-push or merge without explicit approval (`pr-gate`)
- SSOT is `.cursor/` only — lanes write under `.cursor/` or their declared paths only
- Resolve repo at runtime: `gh repo view --json nameWithOwner -q .nameWithOwner`

## Stop conditions

- Lane returns "had to edit file X" that another lane owns → coordinator re-runs sequentially
- Do not parallelize verify scripts that fight over `.kater/kater.db` (one serve/smoke owner)

## Return format (per lane)

- Files written (exact paths)
- One-line outcome
- Blockers for coordinator

## Return format (coordinator)

- Lanes merged: yes/no
- Verify ladder results
- Handoff to `pr-gate` or `kater-verify` if not done inline
