# OIDC / OAuth client placeholders (ChefGroep Auth)

Version-controlled **templates only** — no client secrets. Mesh Authentik already
registers **`chefgroep-kater-oidc`** on chef-authvault (smoke GREEN); public
issuer cutover is in flight. Store credentials in ChefVault / `.kater/.env`.
HTTPS redirect URIs live in [deploy-server.md](../../docs/deploy-server.md#chefgroep-mesh-auth-operator-status).

| File | Purpose |
| --- | --- |
| `authentik-gateway-client.example.yaml` | Future gateway/dashboard OIDC (loopback + public host) |
| `authentik-product-mcp-client.example.yaml` | Dedicated product MCP (`:9093`) resource server contract |

Operator runbook (mesh Auth vs Cloudflare Access): [docs/ops/auth-mesh-vs-cf-access.md](../../docs/ops/auth-mesh-vs-cf-access.md).

Production URLs and introspection contract are also summarized in
[docs/deploy-server.md](../../docs/deploy-server.md#dedicated-chefgroep-product-transport).
