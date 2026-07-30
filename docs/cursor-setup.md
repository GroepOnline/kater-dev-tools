# Cursor Setup

Use one Kater server in Cursor instead of enabling every dev MCP directly.

```bash
uv sync
kater up
```

That writes project `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "kater": {
      "type": "sse",
      "url": "http://127.0.0.1:9090/sse"
    }
  }
}
```

Put adapter secrets in `.kater/.env` (auto-loaded). Example for Linear on the
`ops` profile:

```bash
# .kater/.env
KATER_PROFILE=ops
LINEAR_API_KEY=lin_api_...
```

Restart `kater up` / `kater serve` after changing secrets. Proxy backends enable
automatically when the required env for the active profile is present.

## Skills and agents catalog

Project Cursor artifacts live under **`.cursor/`** (SSOT). Discover them via hooks or manually:

```bash
.cursor/hooks/fetch-cursor-artifacts.sh --print-markdown
```

That lists skills (`SKILL.md`), agents (`.md`), hook events, and plugins with a content hash. On session start and (in Cloud) after the first tool use, `.cursor/hooks.json` injects the same catalog into agent context.

| Kind | Location | Slash / invoke |
| --- | --- | --- |
| Skills | `.cursor/skills/*/SKILL.md` | e.g. `/kater-gateway`, `/create-skill` |
| Agents | `.cursor/agents/*.md` | Delegate from the agent picker |
| Rules | `.cursor/rules/*.mdc` | Always-on or glob-scoped conventions |

When `scripts/generate_cursor_index.py` is present, it writes a committed index (typically `.cursor/INDEX.md`). Regenerate after adding skills or agents:

```bash
python3 scripts/generate_cursor_index.py
bash scripts/check_cursor_artifacts.sh
```

## Hooks

`.cursor/hooks.json` wires `fetch-cursor-artifacts.sh` to:

- `sessionStart` — inject catalog at chat open
- `postToolUse` — one-shot catalog inject in Cloud (cheap no-op afterward)
- `beforeSubmitPrompt` — allow prompt (`continue: true`)
- `workspaceOpen` — register `.cursor/plugins/*` if present

Hook runtime cache (gitignored): `.cursor/hooks/.state/`.

## Pre-commit

Install once per clone so Cursor guards run before every commit:

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

The **`cursor-index`** hook runs `scripts/check_cursor_artifacts.sh` (catalog refresh, optional INDEX staleness check, no org leak under `.cursor/`). It complements **`no-org-leak`** on the full tree. See [CONTRIBUTING.md](../CONTRIBUTING.md) and [local-desktop-verify.md](ops/local-desktop-verify.md).

## Verify locally

| Check | Server | Command |
| --- | --- | --- |
| CLI smoke | **Stopped** | `./scripts/smoke.sh` |
| MCP + REST + WS | **Running** | `./scripts/e2e-mcp.sh` |
| Health probe | Running | `curl -sf http://127.0.0.1:9091/health` |
| Dashboard | Running | Open http://127.0.0.1:9091 |

Full matrix (Cloud VM vs laptop vs Docker): [local-desktop-verify.md](ops/local-desktop-verify.md).

## Cloud agent environment

`.cursor/environment.json` provisions:

- `install` — fetch catalog cache, optional index generation, `uv sync --dev`
- `start` — ensure `uv` on `PATH`; optional non-blocking health probe
- `terminals` — auto-start `uv run kater serve --profile core --no-proxy` (ports 9090/9091/9092)
- `ports` — declared MCP, API, and WebSocket ports

Catalog cold-start: hooks inject skills/agents after the first `postToolUse`. Until then use
[`.cursor/INDEX.md`](../.cursor/INDEX.md) or `fetch-cursor-artifacts.sh --print-markdown`.
Verify ordering: [`local-desktop-verify.md`](ops/local-desktop-verify.md) and `/local-verify`.

### Cloud agent MCP wiring

The auto-terminal runs **`kater serve`**, not **`kater up`**. `kater up` also writes
`.cursor/mcp.json`; the Cloud boot path skips that step.

Pick one:

1. **Run `kater up` once** in the agent shell (after deps are synced):

   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   uv run kater up --profile core --no-proxy
   ```

2. **Write MCP config yourself** (same SSE endpoint the serve terminal already exposes):

   ```json
   {
     "mcpServers": {
       "kater": {
         "type": "sse",
         "url": "http://127.0.0.1:9090/sse"
       }
     }
   }
   ```

REST/e2e proof works without MCP wiring (`curl`, `./scripts/e2e-mcp.sh`). For smoke, **stop**
the gateway terminal first — see [local-desktop-verify.md](ops/local-desktop-verify.md).

Do not commit `.kater/`, personal `.cursor/mcp.json`, or `.cursor/hooks/.state/`.
