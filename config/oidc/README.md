# OIDC / OAuth client placeholders (ChefGroep Auth greenfield)

Version-controlled **templates only** — no client secrets. When Authentik (or mesh
Auth on chef-authvault) exposes providers, create matching applications from the
`*.example.yaml` files and store credentials in ChefVault / `.kater/.env`.

| File | Purpose |
| --- | --- |
| `authentik-gateway-client.example.yaml` | Future gateway/dashboard OIDC (loopback + public host) |
| `authentik-product-mcp-client.example.yaml` | Dedicated product MCP (`:9093`) resource server contract |

Operator runbook (mesh Auth vs Cloudflare Access): [docs/ops/auth-mesh-vs-cf-access.md](../../docs/ops/auth-mesh-vs-cf-access.md).

Production URLs and introspection contract are also summarized in
[docs/deploy-server.md](../../docs/deploy-server.md#dedicated-chefgroep-product-transport).
