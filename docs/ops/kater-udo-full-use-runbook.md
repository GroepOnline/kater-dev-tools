# Full-use runbook — Kater Dev Tools × Utrecht Data OS

Status: operational (Spoor A)  
Plan: [Notion](https://app.notion.com/p/39decd7f1c1a8182aaa1d29b36446c1d) · Linear CHE-649 / CHE-659 / CHE-664

This OSS repo is the **gateway**. Utrecht-specific profiles, native tools and
MCP backends live in a private operator overlay
and load through `KATER_EXTENSIONS_MODULE`. Do not put UDO business logic here.

## Goal

One Kater endpoint that Cursor/agents can use for:

1. UDO search / ask / status (Plane A — local or Tailscale fleet)
2. Ops tools when authenticated (Plane C — origin `/mcp`)
3. Dev backends (GitHub, Linear, Notion, …) via profiles
4. Logical capability pools (`kater-routes`) and manifest registry (`kater-capabilities`)

## Prerequisites

- Python 3.11+ with `uv`
- Node/`npx` for stdio MCP backends
- Cloned `kater-dev-tools` + private `utrecht-katermcp` + reachable `utrecht-data-os` data plane
- Secrets only in `.kater/.env` (never git)

## Bootstrap

```bash
cd kater-dev-tools
uv sync --dev

# Install/overlay utrecht-katermcp per its DEPLOYMENT.md, then:
export KATER_EXTENSIONS_MODULE=utrecht_kater.extensions
export KATER_PROFILE=utrecht,ops

# Recommended for anything beyond loopback:
# export KATER_AUTH_MODE=apikey
# export KATER_API_KEY=...
# export KATER_ADMIN_KEY=...

uv run kater up
```

`kater up` writes `.cursor/mcp.json` pointing at the local SSE gateway.

## Health checks

```bash
curl -s http://127.0.0.1:9091/health
uv run kater doctor
uv run kater status
uv run kater mcp list
uv run kater-capabilities list --json
./scripts/e2e-mcp.sh
```

Expect:

- Health 200
- Extension profiles/tools visible when `KATER_EXTENSIONS_MODULE` is set
- Built-in capabilities such as `kater.profiles.list` and `web.search` listed
- MCP `tools/list` includes UDO tools from the overlay (names depend on overlay version)

## Profiles

| Combo | Use |
|---|---|
| `utrecht` | UDO tools only |
| `utrecht,ops` | UDO + GitHub/Linear/Notion/Cloudflare/… |
| `utrecht,research` | UDO + web research backends |
| `core` | Native Kater tools only (safe default) |

High-risk backends stay disabled until:

```bash
uv run kater enable github
uv run kater enable linear
uv run kater enable notion
```

## Logical routes (optional)

After CHE-693, pool multiple concrete tools behind one capability:

```bash
uv run kater-routes add udo.search \
  --account udo-local \
  --provider utrecht \
  --backend utrecht-local \
  --tool utrecht_search_hybrid \
  --scopes udo.read \
  --priority 10 \
  --quota daily:10000:0

uv run kater-routes dry-run udo.search --context local-dev --scopes udo.read
```

Fallback is infrastructure-only (never replays business errors).

## Capability registry (CHE-659)

```bash
uv run kater-capabilities discover \
  --profile utrecht,ops \
  --intent "search utrecht parking" \
  --max-risk READ \
  --json

uv run kater-capabilities set-lifecycle web.search 1.0.0 revoked
# Revoked managed capabilities disappear from discovery and fail invocation.
```

Unmanaged `backend__tool` names keep working. Domain packages (UDO) should
register stable IDs such as `udo.search.hybrid` via extension `CAPABILITIES`
(CHE-664).

## Safety boundaries

- Public edge stays REST-first snapshot-only — never full DuckDB/embeddings/raw
- Plane A (product index) ≠ Plane C (ops jobs/locks/cancel)
- No long-lived secrets in harness logs or Computer env
- `KATER_PUBLIC=1` requires auth, admin key, CORS and rate limits (`kater doctor`)

## Definition of Done (Spoor A)

- [ ] `kater up` with extensions module starts green
- [ ] Cursor uses one Kater MCP server
- [ ] UDO search/ask returns cited public results
- [ ] Ops tools only via authenticated Plane C
- [ ] `kater-capabilities list` shows builtins (+ overlay manifests when present)
- [ ] `./scripts/e2e-mcp.sh` green

## Follow-on (Spoor B)

1. CHE-659 remainder — richer discovery REST/OpenAPI (this PR is the foundation)
2. CHE-660 — credentials, policy, approvals
3. CHE-664 — package UDO as versioned domain extension (`udo.*` IDs)
4. M1/M3 — Computer + harness neutrality
