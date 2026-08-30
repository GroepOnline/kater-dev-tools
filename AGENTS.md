# AGENTS.md — Kater Dev Tools

Project conventions for AI agents working in this repo. Optional desktop-only:
a maintainer may load a personal global `AGENTS.md` for Merge CLI notes — not
required in Cursor Cloud.

## Skills

Full index + environment metadata: [`.cursor/INDEX.md`](.cursor/INDEX.md)
(regenerate with `python3 scripts/generate_cursor_index.py`).

| Skill | Path | Use when |
| --- | --- | --- |
| `local-verify` | `.cursor/skills/local-verify/` | Umbrella: cloud vs desktop vs Docker verify matrix + port koppelingen |
| `kater-gateway` | `.cursor/skills/kater-gateway/` | Serve, health, smoke ladder |
| `kater-doctor` | `.cursor/skills/kater-doctor/` | `kater doctor` diagnostics / fix-plan |
| `kater-e2e` | `.cursor/skills/kater-e2e/` | `./scripts/e2e-mcp.sh` (server up) |
| `kater-dashboard` | `.cursor/skills/kater-dashboard/` | REST + dashboard on `:9091` |
| `pr-gate` | `.cursor/skills/pr-gate/` | Merge-ready PR checks and gate contract |
| `poteto-mode` | `.cursor/skills/kater-poteto-mode/` | `/poteto-mode` satellite; playbooks stay global |
| `ci-fixer` | `.cursor/skills/ci-fixer/` | Fix failing CI / lint / tests (twin of `ci-fixer` agent) |
| `parallel-lanes` | `.cursor/skills/parallel-lanes/` | Spawn ~4 disjoint-scope parallel workers |
| `create-skill` | `.cursor/skills/create-skill/` | `/create-skill` — scaffold a project skill |
| `create-subagent` | `.cursor/skills/create-subagent/` | `/create-subagent` — scaffold a project subagent |

Slash commands (thin wrappers): `.cursor/commands/*.md` — see INDEX.

SSOT is `.cursor/` only — no mirrored copies under `.agents` / `.claude` / `.codex`.
Org-pinned PR gate overlays live in the private deployment repo; see
[`docs/ops/private-cursor-overlay.md`](docs/ops/private-cursor-overlay.md).
Local/desktop verify how-to: [`docs/ops/local-desktop-verify.md`](docs/ops/local-desktop-verify.md).

## Subagents

| Agent | Path | Use when |
| --- | --- | --- |
| `kater-verify` | `.cursor/agents/kater-verify.md` | Read-only gateway/smoke/e2e/doctor proof |
| `ci-fixer` | `.cursor/agents/ci-fixer.md` | Fix failing CI / lint / tests on current PR |
| `parallel-lane` | `.cursor/agents/parallel-lane.md` | One disjoint-scope implementation lane |
| `pr-gate` | `.cursor/agents/pr-gate.md` | One-PR gate lane (CI, review, rebase) |

## Pre-commit / pre-hooks

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

Local hooks include hygiene, ruff, mypy, gitleaks, `no-org-leak`, and
`cursor-index` (`scripts/check_cursor_artifacts.sh` — catalog cache + INDEX
staleness + org-leak scan under `.cursor/`).

## Hooks

Project hooks in `.cursor/hooks.json` fetch the skills/agents catalog on new
sessions (and once per cloud conversation after the first tool use):

| Event | Cloud | Role |
| --- | --- | --- |
| `sessionStart` | no | Inject catalog + write inject marker (IDE) |
| `postToolUse` | yes | Inject catalog once per conversation (cloud substitute for sessionStart); later calls are a cheap no-op |
| `beforeSubmitPrompt` | yes | Allow prompt (`continue: true`); no context inject (schema limitation) |
| `workspaceOpen` | no | Register `.cursor/plugins/*` via `pluginPaths` |

Cloud cold-start: catalog reaches the model after the first successful
`postToolUse` inject (or when the agent runs the manual command below).

Manual refresh:

```bash
.cursor/hooks/fetch-cursor-artifacts.sh --print-markdown
```

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

## Agent taste (shared)

Canonieke agent-gedrag-taste leeft in `.agents/registry/taste.yaml` (niet in
consuming apps zoals `design-system`). Genereer tool-artefacts met:

```bash
uv run python .agents/scripts/generate-taste.py
uv run python .agents/scripts/generate-taste.py --check
```

Zie `.agents/README.md`. UI-taste blijft in `design-system/taste/`.

Kater is a single Python package (`uv`-managed, Python 3.11–3.14; VM ships 3.12). The startup update
script installs `uv` (to `~/.local/bin`, already on PATH via `.bashrc`/`.profile`) and runs
`uv sync --dev`, so deps are ready before each session. Use `uv run <cmd>` for everything.

- **Artifact catalog**: skills, agents, hooks, and ports are indexed in
  [`.cursor/INDEX.md`](.cursor/INDEX.md) (regenerate with `python3 scripts/generate_cursor_index.py`).
  In Cloud, hooks inject the catalog after the **first** `postToolUse` — not at session open. Until
  then, read INDEX or run `.cursor/hooks/fetch-cursor-artifacts.sh --print-markdown`. Use the
  **`local-verify`** skill (`/local-verify`) for the cloud vs desktop vs Docker verify matrix.
- **Auto-terminal gateway**: `.cursor/environment.json` starts
  `uv run kater serve --profile core --no-proxy --host 127.0.0.1` in a background terminal (MCP
  `:9090`, REST/dashboard `:9091`, WebSocket `:9092`). This is **not** `kater up` — it does not
  write `.cursor/mcp.json`. Install also runs `scripts/sync-chefgroep-skills.sh`
  (no-op unless `CHEFGROEP_SKILLS_REPO` or `CHEFGROEP_SKILLS_GIT_URL` is set)
  into `.cursor/plugins/chefgroep-skills/`. For live MCP tools from the
  agent session, either run
  `uv run kater up` once (writes project MCP config) or add SSE wiring yourself:
  `"url": "http://127.0.0.1:9090/sse"`. See [`docs/cursor-setup.md`](docs/cursor-setup.md#cloud-agent-mcp-wiring).
  Disable Cursor marketplace plugins `posthog` and `harness` in the user/team plugin set if
  Cloud Agents must not load those skills/commands (repo config cannot turn them off).
- **Run the app (manual)**: `uv run kater up` (init + MCP config + serve) or `uv run kater serve`.
  One process starts three
  listeners — REST API + dashboard on `:9091`, MCP SSE on `:9090/sse`, WebSocket telemetry
  on `:9092`. Defaults to loopback with `auth=none`; no external DB (SQLite auto-provisions
  under `.kater/`). Secrets in `.kater/.env` are loaded automatically; proxy backends
  auto-enable when adapter env for the active profile is present (`--proxy`/`--no-proxy`
  or `KATER_PROXY=1|0` to force). Health check: `curl -s http://127.0.0.1:9091/health`.
  Standard lint/test/build commands live in the README "Development" section and
  `.github/workflows/ci.yml` (`uv run ruff check .`, `uv run mypy`, `uv run pytest`,
  `./scripts/smoke.sh`).
- **Test suite timing**: `uv run pytest` takes ~100-120s (551 passing, a few skipped for live/network
 integrations); don't assume it hung.
- **Stop before smoke**: `./scripts/smoke.sh` must run with the server **stopped** — stop the
  auto-terminal gateway first. Smoke drives the CLI against `.kater/kater.db`; a live `kater serve`
  causes concurrent-writer `disk I/O error`. CI stops the server before smoke; do the same in Cloud.
  `./scripts/e2e-mcp.sh`, by contrast, requires the server running.
- **End-to-end check**: with the server running, `./scripts/e2e-mcp.sh` validates REST + a real MCP
  client (initialize/tools) + the WebSocket handshake. Best single proof the gateway works.
- **Core functionality without secrets**: exercisable without any adapter API keys via the CLI
  (`uv run kater status`, `kater mcp list`, `kater enable/disable <name>`) and the REST API
  (`POST /api/mcp/servers/<name>/{enable,disable,toggle}`); state persists to `.kater/kater.db` (SQLite).
- **Proxy backends**: live proxying of the 29+ backend MCP servers needs a profile, per-backend
  API keys in `.kater/.env` (or the environment), and Node/`npx` for stdio backends. With secrets
  present, proxy starts automatically; native tools (`kater_profiles`, etc.) always work.
- **Architecture**: `kater serve` is a single Python process. The dashboard (`src/kater/web/dashboard.py`)
  is a self-contained inline HTML/CSS/JS document rendered server-side; REST routes live in
  `src/kater/api/`, the MCP SSE/stdio surface is in `src/kater/proxy/` and `src/kater/mcp/`, and state
  is SQLite under `.kater/`. There is no separate frontend build step.
- **Dashboard verification**: the dashboard hydrates without a blocking confirm overlay (the old
  import-time `review_fixes.py` monkeypatch layer was removed in #94/#95). Validate the gateway via
  the REST API, the `kater` CLI, or `./scripts/e2e-mcp.sh` rather than headless GUI automation.

## Skill satellites

Deze repo's skills zijn mesh-satellites (`.cursor/skills/kater-dev-tools-*`): ci-fixer → ci-fix-loop, verify/lanes → workflow-verification-meta, create-* → skill-creator (meta-repo: chefgroep-skills). `kater-poteto-mode` → `poteto-mode` (global).

Compound Engineering overlay: `.compound-engineering/` (tracked `config.yaml`, gitignored `config.local.yaml`). Artifact root `.compound-engineering/artifacts/`. Portable skills `~/.agents/skills/ce-*`; native Cursor plugin is fallback only when this overlay is absent.
