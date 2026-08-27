# Architecture & repo context

Whole-repo overview for humans and any AI agent/harness. Harness-neutral: plain
Markdown, no tool-specific assumptions. For agent operating conventions see
[`AGENTS.md`](../AGENTS.md); for behavior/config see
[`.reviews/agent-config.yaml`](../.reviews/agent-config.yaml).

## What Kater is

Kater is a single Python package (`uv`-managed, Python 3.11–3.14) that runs an
MCP gateway. `kater serve` is **one process** exposing three listeners:

| Surface | Port | Notes |
| --- | --- | --- |
| MCP SSE | `:9090` (`/sse`) | Model Context Protocol surface |
| REST API + dashboard + health | `:9091` | `GET /health`, dashboard UI |
| WebSocket telemetry | `:9092` | live telemetry |

Defaults to loopback with `auth=none`; state is SQLite under `.kater/` (no
external DB). Secrets in `.kater/.env` load automatically. Profiles: `core`
(cloud-safe, no proxy) and `ops` (dev backends). Source: `AGENTS.md`,
`.cursor/INDEX.md` Environment table.

## Source layout (`src/kater/`)

| Path | Role |
| --- | --- |
| `src/kater/web/dashboard.py` | Self-contained inline HTML/CSS/JS dashboard, server-rendered (no separate frontend build) |
| `src/kater/api/` | REST routes |
| `src/kater/proxy/`, `src/kater/mcp/` | MCP SSE/stdio surface + proxy to backend MCP servers |
| `src/kater/pr_control.py` | PR gate verdicts / reason codes |
| `src/kater/openapi_spec.py` | OpenAPI spec generation (snapshot-checked in CI) |

Source of truth for this section: `AGENTS.md` Architecture note
(`AGENTS.md:153-156`) and the `validate` job in `.github/workflows/ci.yml`.

## Repo control planes

Three distinct planes; do not conflate them:

| Plane | Location | Purpose |
| --- | --- | --- |
| Agent skills/agents | `.cursor/` | Cursor control plane (skills, agents, rules, hooks, generated INDEX). SSOT **today**; see `.reviews/plan-harness-neutral.md` for the planned harness-neutral move. |
| Agent-taste | `.agents/` | Behavioral taste registry + eval loop only (`.agents/README.md`) |
| Reviews / logs / config | `.reviews/` | Review notes, continual-learning, session logs, `agent-config.yaml`, portable skills |

## CI / quality gates

`.github/workflows/ci.yml` runs on `ubuntu-latest` and aggregates required jobs
into a single `gate` check: `validate`, `lint-type`, `unit` (3.11–3.14 matrix),
`integration`, `e2e`, `package`, `security-pr`, `coverage`.

Non-obvious guards that trip agents:

- **Workflow text tests.** `.github/workflows/*.yml` is asserted as plain-text
  substrings in `tests/test_ci_workflow_changes.py` (pinned SHAs, `runs-on`,
  comment markers). YAML edits can break tests without any YAML error.
- **Cursor artifact guard.** `.github/workflows/ci.yml:103-104` runs
  `scripts/check_cursor_artifacts.sh`, which runs
  `scripts/generate_cursor_index.py --check`. Adding/renaming a `.cursor` skill
  without regenerating the index fails the `validate` job. Same guard in
  `.pre-commit-config.yaml`.
- **Org-leak scan.** No org handle / production domain under `.cursor/`.

Other workflows: `.github/workflows/release.yml` (tag/dispatch release),
`.github/workflows/agent-taste-eval.yml` (nightly taste gate),
`.github/workflows/no-org-leak.yml` (org-leak scan), `.github/workflows/automerge.yml`
(Dependabot auto-merge). All on `ubuntu-latest`.

## Verify (local == CI)

```bash
uv run ruff check . && uv run mypy && uv run pytest   # ~100-120s
uv run pytest tests/test_ci_workflow_changes.py       # after any .github/workflows/*.yml edit
bash scripts/check_cursor_artifacts.sh                # after any .cursor/ edit
```

`./scripts/smoke.sh` runs with the server **stopped**; `./scripts/e2e-mcp.sh`
runs with it **started**.

## Docs map

| Doc | Topic |
| --- | --- |
| [`AGENTS.md`](../AGENTS.md) | Agent operating mode, guardrails, skills/subagents |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Contributor workflow, pre-commit, release policy |
| [`docs/release.md`](release.md) | Release / version bump process |
| [`docs/cursor-setup.md`](cursor-setup.md) | Cursor MCP wiring |
| [`docs/ops/local-desktop-verify.md`](ops/local-desktop-verify.md) | Local/desktop verify matrix |
| [`docs/ops/private-cursor-overlay.md`](ops/private-cursor-overlay.md) | Org-pinned overlays (private repo) |
| [`.reviews/README.md`](../.reviews/README.md) | Review notes, continual-learning, session logs |
