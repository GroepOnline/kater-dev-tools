# Mesh Auth vs Cloudflare Access (Kater)

Kater on **bc-scan-arm** (Tailscale GREEN, REST `:9091`) is already reachable at
**kater.chefgroep.online** behind **Cloudflare Access** (human/browser gate).
**Product Auth** via Authentik on **chef-authvault** is greenfield; the mesh Auth
issuer will listen on **`:9000`** until the public `auth.chefgroep.online` contract
is cut over.

This document is the operator map for **today** vs **target** — no DNS changes
from this repo.

## Surfaces

| Surface | Port | Auth today | Auth target |
| --- | --- | --- | --- |
| REST + dashboard | 9091 | CF Access in front of HTTPS; Kater may use `KATER_AUTH_MODE=none` on loopback | Optional gateway OIDC (`KATER_OAUTH_*`) |
| Private MCP SSE | 9090 | Same as REST path when tunneled | Bearer / API key at Kater |
| Product MCP | 9093 | Off unless `KATER_RESOURCE_AUTH_ENABLED=1` | OAuth bearer + Auth introspection |

## Cloudflare Access (today)

Use this path when operators or agents hit **kater.chefgroep.online** in a browser
or through Access-aware tunnels:

1. User authenticates at Cloudflare Access (identity provider configured in CF Zero Trust).
2. Traffic reaches Kater on bc-scan-arm after Access allows the session.
3. Kater still enforces its own `KATER_AUTH_MODE` on `/sse` and API routes unless
   configured for `none` on the loopback bind.

**Local parity without Access:** bind to loopback and disable public mode:

```bash
cp .env.example .env
./scripts/dev-boot.sh native
# or: ./scripts/dev-boot.sh compose
./scripts/dev-health.sh
```

## Mesh Auth / Authentik (greenfield, chef-authvault `:9000`)

ChefGroep Auth will issue tokens and register OAuth clients (ChatGPT product MCP,
future dashboard OIDC). Kater only **validates** tokens for the product listener
(`KATER_RESOURCE_AUTH_*`); it does not register clients or store provider secrets
in git.

| Concern | Where it lives |
| --- | --- |
| OAuth client IDs, redirect URIs, PKCE | Authentik on chef-authvault (templates in `config/oidc/`) |
| Service introspection key | Secret authority → `KATER_RESOURCE_AUTH_SERVICE_KEY` |
| Issuer / JWKS URLs | `KATER_RESOURCE_AUTH_ISSUER`, gateway `KATER_OAUTH_*` in `.env` |
| Redirect URI allowlist | `config/oidc/*.example.yaml` (local loopback + `kater.chefgroep.online`) |

Until providers exist:

- Keep **product MCP disabled** (`KATER_RESOURCE_AUTH_ENABLED` unset or `0`).
- Use **local dev** compose override (`docker-compose.dev.yml`) or `kater serve --no-proxy` with `KATER_AUTH_MODE=none`.
- Do **not** commit client secrets; copy placeholders from `config/oidc/` into Authentik when ready.

When mesh Auth is up on `:9000`, point staging `.env` at the HTTPS issuer hostname
(documented in `config/oidc/authentik-product-mcp-client.example.yaml`). Production
values match [deploy-server.md](../deploy-server.md#dedicated-chefgroep-product-transport).

## Product MCP vs Access

Only these paths must reach Kater **without** an interactive Access login (machine
OAuth):

- `/mcp`
- `/.well-known/oauth-protected-resource/mcp`

All other public paths may remain behind Access. See deploy-server for tunnel routing.

## Verify

```bash
# Loopback / compose dev
./scripts/dev-health.sh

# With gateway running (CI parity)
curl -fsS http://127.0.0.1:9091/health
./scripts/e2e-mcp.sh
```

Smoke CLI (`./scripts/smoke.sh`) still requires the server **stopped** (SQLite writer).
