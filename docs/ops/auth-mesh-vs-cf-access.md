# Mesh Auth vs Cloudflare Access (Kater)

Kater on **bc-scan-arm** (Tailscale GREEN, REST `:9091`) is reachable at the public
Kater hostname behind **Cloudflare Access** (human/browser gate). **ChefGroep mesh Auth**
on **chef-authvault** has **greenfield smoke GREEN** on **`:9000`**; CoS **GO’d** public
**public auth hostname** Cloudflare apply (**in flight**; see deploy-server). Authentik already has
the mesh OIDC app **`chefgroep-kater-oidc`**. Public issuer cutover is **in progress** —
there is still **no public Vault** endpoint. This repo does not apply DNS or CF changes.

Operator map (canonical production URLs and redirect URIs):
[deploy-server.md](../deploy-server.md#chefgroep-mesh-auth-operator-status).

## Surfaces

| Surface | Port | Auth today | Auth target |
| --- | --- | --- | --- |
| REST + dashboard | 9091 | CF Access in front of HTTPS; Kater may use `KATER_AUTH_MODE=none` on loopback | Gateway OIDC via `chefgroep-kater-oidc` (`KATER_OAUTH_*`) when wired |
| Private MCP SSE | 9090 | Same as REST path when tunneled | Bearer / API key at Kater |
| Product MCP | 9093 | Off unless `KATER_RESOURCE_AUTH_ENABLED=1` | OAuth bearer + Auth introspection |

## Cloudflare Access (today)

Use this path when operators or agents hit the public Kater hostname in a browser
or through Access-aware tunnels:

1. User authenticates at Cloudflare Access (identity provider configured in CF Zero Trust).
2. Traffic reaches Kater on bc-scan-arm after Access allows the session.
3. Kater still enforces its own `KATER_AUTH_MODE` on `/sse` and API routes unless
   configured for `none` on the loopback bind.

**Local parity without Access:** bind to loopback and disable public mode:

```bash
cp .env.example .env
./scripts/dev-boot.sh native
./scripts/dev-health.sh
```

**Docker Compose dev stack** (laptop or **Dev Containers**): `./scripts/dev-boot.sh compose`
with `docker-compose.dev.yml`. **Cursor Cloud** agent VMs often have **no Docker daemon** —
use the **native** path above instead of Compose.

## Mesh Auth / Authentik (chef-authvault)

Mesh Auth issues tokens; Kater **validates** (product listener via `KATER_RESOURCE_AUTH_*`)
and will consume gateway OIDC once `KATER_OAUTH_*` points at the public issuer. Kater does
not register clients or commit secrets.

| Concern | Where it lives |
| --- | --- |
| Live mesh client id | `chefgroep-kater-oidc` (Authentik on chef-authvault) |
| Redirect URI allowlist | [deploy-server.md](../deploy-server.md#chefgroep-mesh-auth-operator-status) + `config/oidc/*.example.yaml` |
| Service introspection key | Secret authority → `KATER_RESOURCE_AUTH_SERVICE_KEY` |
| Issuer / JWKS | `KATER_RESOURCE_AUTH_ISSUER`, gateway `KATER_OAUTH_*` in `.env` (after public cutover) |

Until public issuer HTTPS is live and Kater env is wired:

- Keep **product MCP disabled** (`KATER_RESOURCE_AUTH_ENABLED` unset or `0`) unless introspection is configured.
- Use **local dev** (`docker-compose.dev.yml` or `kater serve --no-proxy` with `KATER_AUTH_MODE=none`).
- Store client secrets only in ChefVault / `.kater/.env` — never in git.

After cutover, mirror issuer URLs in `config/oidc/authentik-product-mcp-client.example.yaml` and
[deploy-server.md](../deploy-server.md#dedicated-chefgroep-product-transport).

## Product MCP vs Access

Only these paths must reach Kater **without** an interactive Access login (machine
OAuth):

- `/mcp`
- `/.well-known/oauth-protected-resource/mcp`

All other public paths may remain behind Access. See deploy-server for tunnel routing.

## Verify

```bash
# Loopback / native (Cloud agents) or after compose on laptop
./scripts/dev-health.sh

# With gateway running (CI parity)
curl -fsS http://127.0.0.1:9091/health
./scripts/e2e-mcp.sh
```

Smoke CLI (`./scripts/smoke.sh`) still requires the server **stopped** (SQLite writer).
