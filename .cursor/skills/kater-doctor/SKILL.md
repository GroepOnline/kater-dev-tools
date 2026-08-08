---
name: kater-doctor
description: Run Kater doctor diagnostics, fix plans, and safe apply for MCP/Cursor wiring.
details: Use for /kater-doctor, "kater doctor", MCP config drift, Cursor mcp.json mismatches, or pre-serve environment checks.
---

# Kater doctor

Diagnostics for profiles, adapter secrets, Cursor MCP wiring, and public-deploy safety.

## Twin chain & handoffs

| Artifact | Path | When |
| --- | --- | --- |
| Skill (this) | `.cursor/skills/kater-doctor/SKILL.md` | When/why + command contract |
| Subagent | `.cursor/agents/kater-verify.md` | Full verify lane after fixes |
| Related | `kater-gateway`, `local-verify` | Serve + environment matrix |

After doctor fixes, hand off to **`kater-verify`** for serve → health → e2e. Use **`ci-fixer`** when CI doctor step fails.

## Pre-reads

1. `README.md` — doctor row in CLI table
2. `src/kater/cli.py` — `doctor` flags (`--fix-plan`, `--apply`, `--yes`)
3. `AGENTS.md` — `.kater/.env` auto-load, proxy behavior

## When to run

- Before first `kater serve` / `kater up` in a fresh checkout
- After changing profiles, `.kater/.env`, or Cursor MCP paths
- When MCP tools show `configured: false` unexpectedly
- As part of `./scripts/smoke.sh` (doctor is step 3 of smoke)
- Before public/Docker deploy (`KATER_PUBLIC=1` auth warnings)

## Commands

**Read-only report** (preferred first pass):

```bash
uv run kater doctor --json
```

**Inspect a specific Cursor MCP file**:

```bash
uv run kater doctor --json --cursor-mcp .cursor/mcp.json
```

**Proposed fixes** (no writes):

```bash
uv run kater doctor --fix-plan --json
```

**Apply Kater-owned fixes** (non-interactive):

```bash
uv run kater doctor --apply --yes --json
```

Multi-profile:

```bash
uv run kater doctor --profile core,ops --json
```

REST mirror (server running): `GET http://127.0.0.1:9091/api/doctor`

## Interpretation

- **Green / ok** — proceed to `kater-gateway` serve ladder
- **Warnings** — document; serve may still work with `--no-proxy`
- **Blocks on public deploy** — set auth (`KATER_AUTH_MODE`, API key) before exposing ports
- **Cursor MCP drift** — prefer `kater up` or doctor apply over hand-editing `.cursor/mcp.json`

## Steps

1. Run `uv run kater doctor --json`; capture verdict + issue list
2. If fixable and operator-approved: `--fix-plan --json` then `--apply --yes --json`
3. Re-run doctor until blockers cleared or explicitly accepted
4. Continue verify ladder: serve → health → `./scripts/e2e-mcp.sh` (see `kater-e2e`)

## Stop conditions

- Never `--apply --yes` without reviewing `--fix-plan` output
- Do not commit `.cursor/mcp.json` or `.kater/` artifacts doctor writes
- Missing adapter secrets are expected in cloud/core profile — do not invent keys
- SSOT is `.cursor/` only

## Return format

- Doctor verdict summary (pass/warn/block counts)
- Top 3 actionable issues + suggested command
- Whether serve/e2e is unblocked
