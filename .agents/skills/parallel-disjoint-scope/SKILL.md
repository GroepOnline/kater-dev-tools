---
name: parallel-disjoint-scope
description: Use when dispatching multiple subagents that edit files in parallel — prevents "file has been modified since read" crashes from the Edit tool locking the whole file, not just the changed section.
---

# Parallel Dispatch With Disjoint File Scope

## Overview

The Edit tool locks the **ENTIRE file** for the duration of a write, not just the section you changed.
Two agents editing *different sections of the same file* in parallel will collide: the second writer
sees `File has been modified since read` and its edit fails. Parallel dispatch is still the right call
for throughput — but each agent must own a **disjoint file (or disjoint constant) scope**.

## When to Use

- Dispatching 2+ subagents to do non-trivial work (build, audit, redesign, refactor).
- Any task where agents will call Edit/Write on shared files.
- You want ~4 agents in flight for throughput (see global/AGENTS.md *Parallel Working*).

**Do NOT use** to justify letting two agents touch one file "because they edit different parts" — they
can't. Either split the file or run them sequentially.

## RED baseline (proven failure)

Two agents were told to edit `SECTION_A` vs `SECTION_B` of the same scratch file in parallel. Agent B
won the race; Agent A then hit:

> `Error: <tool_use_error>File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.</tool_use_error>`

Disjoint *sections* are not enough. Disjoint **files** are required.

## Core Pattern

Before dispatching, partition the work so no two agents share a file:

```
AGENT A — tokens + CSS          → only src/x/theme.py  (_CSS constant)
AGENT B — markup / views        → only src/x/views.py  (_HTML/_VIEW constants)
AGENT C — JS layer              → only src/x/views.py  (_JS constant)   # SAME FILE AS B → NOT PARALLEL
```

If two units must touch the same file (e.g. `_CSS` and `_JS` both live in `dashboard.py`), run them
**sequentially**, not in parallel. The dispatcher (coordinator) reads the file fresh after each agent
and re-partitions if needed.

### Safe partition strategies
- **By file:** one file per agent (ideal).
- **By disjoint constant in different files:** fine.
- **By disjoint constant in the SAME file:** NOT safe — serialize.
- **Append-only / new files:** safe to parallelize (Write to a unique path each).

## Dispatch Template (self-contained prompt)

Each agent prompt must carry its full context — agents do not inherit your session:

```
AGENT <N> — <scope>:
  Goal: <what to build/edit>
  Files: <only these exact paths/constants>
  Constraints: do NOT read or touch any other file
  Output: summary of root cause + changes made
```

The coordinator runs tests/linters/audits after all agents return, checks for cross-agent conflicts,
then integrates and commits.

## Common Mistakes

- "They edit different sections, so parallel is fine." → Crash. Edit locks the whole file.
- Letting agents guess file paths. → Give exact paths/constants in the prompt.
- Assuming the slower agent will just retry. → It reports the error and stops; the work is lost.
- Putting `_CSS` + `_JS` + markup in one file and dispatching 3 parallel agents. → Serialize or split.

## Red Flags — STOP and Re-partition

- Two agents target the same file path (even different constants).
- An agent reports `File has been modified since read`.
- You find yourself saying "they won't overlap."

All of these mean: the partition is wrong. Give each agent a file no other agent touches, or run them
one at a time.

**No "retry / Read-fresh" workaround:** Do NOT tell an agent to catch `File has been modified since
read` and re-Read-then-Edit. That turns a safe partition into a race: the loser's intermediate state is
lost, and retries waste turns. If a collision happens, the partition was wrong — re-partition or
serialize. The error is a signal to fix the dispatch, never to retry the edit.
