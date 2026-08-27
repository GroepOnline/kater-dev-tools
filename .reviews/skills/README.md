# .reviews/skills

Portable mirrors of repo skills for reuse outside this repository.

`.cursor/skills/` is the repository source of truth and is coupled to the generated
Cursor index. `scripts/check_cursor_artifacts.sh` requires each mirrored skill here
to stay byte-for-byte identical to its `.cursor/skills/` source, preventing the two
locations from drifting while keeping a portable copy available.

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
