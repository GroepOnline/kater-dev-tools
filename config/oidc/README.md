# OIDC / OAuth client placeholders (ChefGroep Auth)

Version-controlled **templates only** — no client secrets. Mesh Authentik already
registers **`chefgroep-kater-oidc`** on chef-authvault (smoke GREEN). Public
issuer HTTPS is live at `auth.chefgroep.online` (`.nl` is a mesh alias). Store
credentials in ChefVault / `.kater/.env`.

Canonical issuer (Authentik app slug `kater`, not the client-id slug):

`https://auth.chefgroep.online/application/o/kater/`

HTTPS redirect URIs live in [deploy-server.md](../../docs/deploy-server.md#chefgroep-mesh-auth-operator-status).

| File | Purpose |
| --- | --- |
| `authentik-gateway-client.example.yaml` | Gateway/dashboard OIDC RP (`AUTH_OIDC_*`, `/oidc/callback`) |
| `authentik-product-mcp-client.example.yaml` | Dedicated product MCP (`:9093`) resource server contract |

When `AUTH_OIDC_ISSUER` + `AUTH_OIDC_CLIENT_ID` are set, Kater prefers Authentik
as the product login gate (`/authorize` → IdP → `/oidc/callback`). Cloudflare
Access is the edge fallback until the cutover checklist in
[auth-mesh-vs-cf-access.md](../../docs/ops/auth-mesh-vs-cf-access.md) is applied.
This repo does not apply Cloudflare DNS.

Verify (no secrets required for the authorize redirect):

```bash
./scripts/oidc-canary.sh
```

Operator runbook: [docs/ops/auth-mesh-vs-cf-access.md](../../docs/ops/auth-mesh-vs-cf-access.md).
Production URLs and introspection contract:
[docs/deploy-server.md](../../docs/deploy-server.md#dedicated-chefgroep-product-transport).
