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

## Cursor Cloud specific instructions

Kater is a single Python package (`uv`-managed, Python 3.11+). The startup update script installs
`uv` (to `~/.local/bin`, already on PATH via `.bashrc`) and runs `uv sync --dev`, so deps are ready
before each session. Use `uv run <cmd>` for everything.

- **Run the app**: `uv run kater serve`. One process starts three listeners — REST API + dashboard on
  `:9091`, MCP SSE on `:9090/sse`, WebSocket telemetry on `:9092`. Defaults to loopback with
  `auth=none`; no external DB (SQLite auto-provisions under `.kater/`). Standard lint/test/build
  commands live in the README "Development" section and `.github/workflows/ci.yml`
  (`uv run ruff check .`, `uv run mypy`, `uv run pytest`, `./scripts/smoke.sh`).
- **End-to-end check**: with the server running, `./scripts/e2e-mcp.sh` validates REST + a real MCP
  client (initialize/tools) + the WebSocket handshake. Best single proof the gateway works.
- **Proxy backends are optional**: live proxying of the 29+ backend MCP servers needs `KATER_PROXY=1`,
  a profile, per-backend API keys, and Node/`npx` (present) for stdio backends. Core gateway works
  without any of this — native tools (`kater_profiles`, etc.) are always exposed.
- **Architecture**: `kater serve` is a single Python process. The dashboard (`src/kater/web/dashboard.py`)
  is a self-contained inline HTML/CSS/JS document rendered server-side; REST routes live in
  `src/kater/api/`, the MCP SSE/stdio surface is in `src/kater/proxy/` and `src/kater/mcp/`, and state
  is SQLite under `.kater/`. There is no separate frontend build step.
- **Dashboard verification**: the dashboard hydrates without a blocking confirm overlay (the old
  import-time `review_fixes.py` monkeypatch layer was removed in #94/#95). Validate the gateway via
  the REST API, the `kater` CLI, or `./scripts/e2e-mcp.sh` rather than headless GUI automation.
