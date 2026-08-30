# .reviews

Human/agent review notes, continual-learning findings, and session logs for
this repository.

This folder is deliberately **separate from `.agents/`**. Per `AGENTS.md`, the
SSOT for agent skills is `.cursor/` and `.agents/` is scoped narrowly to the
agent-taste registry/eval loop (`.agents/README.md`). Review write-ups and
session logs are a different kind of artifact, so they live here instead of
polluting that registry.

## Layout

| Path | Role |
|---|---|
| `README.md` | this file |
| `continual-learning.md` | durable, cross-session lessons worth remembering |
| `sessions/` | per-session logs (one file per working session) |
| `pr-<n>-review.md` | review notes scoped to a specific PR |

## When to write here

- **`continual-learning.md`** — a lesson that will still matter next month
  (e.g. "workflow text is asserted by a plain-text regression test, so any
  `uses:` bump must be mirrored in the test").
- **`sessions/YYYY-MM-DD-<slug>.md`** — what was done in a single session, what
  broke, and what to pick up next time.
- **`pr-<n>-review.md`** — findings and decisions specific to one PR.

## Relationship to agent-taste

If a lesson is really about *how agents should behave* (not repo-specific
trivia), promote it into the taste loop instead:

```bash
uv run python .agents/scripts/taste-signal.py add --signal "…" --plane agent-taste
```

See `.agents/README.md` for that loop.
