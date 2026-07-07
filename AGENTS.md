# AGENTS.md — Kater Dev Tools

Project conventions for AI agents working in this repo. The user's global
`C:\Users\joep\AGENTS.md` holds the Merge CLI section and is loaded alongside this file.

## Parallel Working (Default)

For any non-trivial multi-part task, dispatch **parallel subagents** rather than doing the work
sequentially in the main session. Keep ~4 agents in flight; re-dispatch the next batch as soon as
prior agents finish.

### Hard rule: disjoint file scope per agent
The Edit tool locks the **ENTIRE file**, not a section. Two agents editing the same file will crash
with "file has been modified since read" (seen repeatedly during the dashboard redesign — e.g. `_CSS`
vs `_JS` in `dashboard.py`). Therefore:
- Each agent gets its own file(s) / disjoint constant scope.
- If two units MUST touch the same file, run them **sequentially**, not in parallel.

### Dispatch template
```
AGENT A — <scope>: <what to build/edit>   → only <files/constants>
AGENT B — <scope>: <what to build/edit>   → only <files/constants>
AGENT C — <scope>: <what to build/edit>   → only <files/constants>
(coordinator): run tests/linters/audits after all return, fix crossover, commit
```
Each agent prompt must be self-contained: focused scope, clear goal, constraints ("do not touch other
code"), and expected output (summary of root cause + changes). After return: review summaries, check
for cross-agent conflicts, run the full test suite, then integrate.
