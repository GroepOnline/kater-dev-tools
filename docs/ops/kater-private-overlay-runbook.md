# Full-use runbook — Kater Dev Tools with a private domain overlay

Status: operational pattern

This OSS repo is the gateway. Domain-specific profiles, native tools, and MCP backends can live in a private operator overlay and load through `KATER_EXTENSIONS_MODULE`. Keep private business logic, private repository names, credentials, and internal tracking metadata out of this repository.

## Goal

One Kater endpoint that agents can use for:

1. Domain search, ask, and status through a private extension overlay.
2. Ops tools when authenticated through the gateway.
3. Dev backends such as GitHub, issue tracking, and documentation through profiles.
4. Logical capability pools (`kater-routes`) and the manifest registry (`kater-capabilities`).

## Prerequisites

- Python 3.11+ with `uv`.
- Node/`npx` for stdio MCP backends.
- A cloned `kater-dev-tools` checkout plus a separately managed private extension package and reachable private data plane.
- Secrets only in local environment/configuration files, never in git.

## Bootstrap

```bash
cd kater-dev-tools
uv sync --dev

# Install the private extension package outside this repository, then:
export KATER_EXTENSIONS_MODULE=domain_overlay.extensions
export KATER_PROFILE=domain,ops

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

Expect health 200, extension profiles/tools when `KATER_EXTENSIONS_MODULE` is set, built-in capabilities such as `kater.profiles.list` and `web.search`, and overlay-provided tools in MCP `tools/list`.

## Profiles

| Combo | Use |
|---|---|
| `domain` | Private domain tools only |
| `domain,ops` | Domain + operational/dev backends |
| `domain,research` | Domain + web research backends |
| `core` | Native Kater tools only (safe default) |

High-risk backends stay disabled until explicitly enabled:

```bash
uv run kater enable github
uv run kater enable linear
uv run kater enable notion
```

## Logical routes

Pool multiple concrete tools behind one capability:

```bash
uv run kater-routes add domain.search \
  --account domain-local \
  --provider domain \
  --backend domain-local \
  --tool domain_search_hybrid \
  --scopes domain.read \
  --priority 10 \
  --quota daily:10000:0

uv run kater-routes dry-run domain.search --context local-dev --scopes domain.read
```

Fallback is infrastructure-only and must not replay business errors.

## Capability registry

```bash
uv run kater-capabilities discover \
  --profile domain,ops \
  --intent "search the private domain index" \
  --max-risk READ \
  --json

uv run kater-capabilities set-lifecycle web.search 1.0.0 revoked
```

Unmanaged `backend__tool` names keep working. Domain packages should register stable IDs such as `domain.search.hybrid` through extension `CAPABILITIES`.

## Safety boundaries

- Public edge stays REST-first and snapshot-only; do not expose raw private databases, embeddings, or unrestricted query surfaces.
- Product/data-plane access and ops-plane access remain separate capabilities.
- Do not place long-lived secrets in harness logs or agent environments.
- `KATER_PUBLIC=1` requires auth, admin key, CORS, and rate limits (`kater doctor`).

## Definition of done

- [ ] `kater up` with the extension module starts green.
- [ ] The client uses one Kater MCP server.
- [ ] Domain search/ask returns the expected cited results.
- [ ] Ops tools are available only through the authenticated control surface.
- [ ] `kater-capabilities list` shows built-ins and overlay manifests when present.
- [ ] `./scripts/e2e-mcp.sh` is green.

## Follow-on

1. Enrich discovery REST/OpenAPI where the public contract needs it.
2. Keep credentials, policy, and approvals explicit and auditable.
3. Package each private domain as a versioned extension with stable capability IDs.
4. Preserve client and harness neutrality.
