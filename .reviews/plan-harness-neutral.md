# Plan — harness-neutral agent layer + repo context

Agreed split: this PR (#49) stays scoped; the de-`.cursor`-ification is a
separate, dedicated PR. This file records both so the next session can pick up.

## Decisions

1. **De-`.cursor`-ification is a separate PR.** `.cursor/` is deeply wired into
   CI/tests/pre-commit, so ripping it out here would blow up PR #49's scope and
   turn several green tests red.
2. **This PR only adds harness-neutral, CI-safe artifacts:** a repo context file
   (`docs/ARCHITECTURE.md`) and the promoted `pr-review-log` skill.
3. **Index regeneration is manual.** `scripts/generate_cursor_index.py` cannot be
   run in the review sandbox, so after any `.cursor/skills/` change the maintainer
   runs it locally before commit (see Verification).

## Why `.cursor/` is not free to remove (evidence)

- `tests/test_cursor_skills.py` asserts specific skills/agents exist under
  `.cursor/skills/` and `.cursor/agents/`, are cross-linked, and have valid
  frontmatter (e.g. `tests/test_cursor_skills.py:92-121`).
- The `validate` job runs the guard: `.github/workflows/ci.yml:103-104`
  (`bash scripts/check_cursor_artifacts.sh`), which runs
  `scripts/generate_cursor_index.py --check` (`scripts/check_cursor_artifacts.sh:26-34`).
- Same guard in pre-commit: `.pre-commit-config.yaml:59-63`.
- The catalog auto-injection is Cursor-lifecycle-specific via `.cursor/hooks.json`
  (`AGENTS.md` Hooks table), but the `SKILL.md`/agent files themselves are plain
  Markdown+YAML any harness can read.

## This PR — scope (CI-safe)

- [x] `docs/ARCHITECTURE.md` — first whole-repo context/overview doc. Plain MD,
      not scanned by the `validate` JSON/YAML check (`.github/workflows/ci.yml:49-70`
      covers only `*.json` and `.github/**/*.yml`).
- [x] Promote `pr-review-log` to `.cursor/skills/pr-review-log/SKILL.md` with a
      cross-link, keeping the portable copy under `.reviews/skills/` as the
      harness-neutral source.

## Next PR — de-`.cursor`-ification (harness-neutral)

Goal: `.cursor/` holds only Cursor-specific *config* (e.g.
`.cursor/environment.json`, `.cursor/hooks.json`); skills/agents/rules become a
harness-neutral source that any tool (Cursor, Claude, Codex, CodeRabbit, …) can
consume, with thin per-harness adapters generated from it.

Proposed shape:

1. **Neutral SSOT.** Move skill/agent bodies to a tool-agnostic tree
   (e.g. `agents/skills/*/SKILL.md`, `agents/subagents/*.md`) — plain MD+YAML,
   no Cursor path assumptions in the frontmatter.
2. **Config stays harness-specific.** `.coderabbit.yaml`, `.reviews/agent-config.yaml`,
   `.cursor/environment.json`, `.cursor/hooks.json` remain; they are config, not content.
3. **Generator emits adapters.** Rework `scripts/generate_cursor_index.py` into a
   generator that reads the neutral SSOT and emits per-harness views
   (`.cursor/…`, and optionally `.claude/…`, `.codex/…`) as generated artifacts.
4. **Update the guards/tests together:**
   - `tests/test_cursor_skills.py` → point at the neutral SSOT (or add a neutral
     twin) so the contract survives the move.
   - `scripts/check_cursor_artifacts.sh` → check neutral SSOT + generated views.
   - `.pre-commit-config.yaml:59-63` and `.github/workflows/ci.yml:103-104` → run
     the reworked generator/guard.
5. **Docs.** Update `AGENTS.md`, `CONTRIBUTING.md`, and `docs/ARCHITECTURE.md`
   to describe the neutral SSOT + adapters instead of "SSOT is `.cursor/` only".

Risk: touches tests + generator + CI + pre-commit at once — keep it its own PR
with green `tests/test_cursor_skills.py` before/after.

## Verification

```bash
# after promoting the skill locally:
python3 scripts/generate_cursor_index.py            # regenerate INDEX + .index.yaml
bash scripts/check_cursor_artifacts.sh              # guard must pass
uv run pytest tests/test_cursor_skills.py tests/test_ci_workflow_changes.py
```
