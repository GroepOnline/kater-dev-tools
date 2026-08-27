# .reviews/skills

Portable, repo-agnostic skills kept **outside** `.cursor/skills/` on purpose.

`.cursor/skills/` is coupled to a generated index (`.cursor/INDEX.md`,
`.cursor/skills/.index.yaml` via `scripts/generate_cursor_index.py`) and guarded
in CI by `scripts/check_cursor_artifacts.sh` and `tests/test_cursor_skills.py`.
Skills here have no such coupling, so they can be copied into any repo as a
starting point.

## How to reuse a skill elsewhere

1. Copy the skill folder into the target repo's skill location:
   ```bash
   cp -r .reviews/skills/pr-review-log <target>/.cursor/skills/pr-review-log
   ```
2. If the target repo generates a Cursor index, regenerate it so the guards pass:
   ```bash
   cd <target> && python3 scripts/generate_cursor_index.py
   ```
3. Optionally add a thin `/slash` wrapper under `.cursor/commands/` and list the
   skill in that repo's `AGENTS.md` Skills table.

The `SKILL.md` frontmatter already matches the `.cursor/` skill format
(`name`, `description`, `details`, `use`, ...), so promotion is a copy + index
regen — no reformatting needed. `name` must equal the folder name, which
`tests/test_cursor_skills.py` enforces once the skill lives under `.cursor/`.

## Skills

| Skill | Path | Use when |
| --- | --- | --- |
| `pr-review-log` | `.reviews/skills/pr-review-log/SKILL.md` | Review a PR, fix root-cause bugs, write review + continual-learning + session log |
