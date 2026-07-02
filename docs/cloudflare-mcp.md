# Cloudflare Global MCP — Deployment Guide

Full Cloudflare management via MCP (50+ tools) behind a Cloudflare Tunnel.

## Architecture

```
MCP client ──→ https://mcp-cf.example.com/mcp (CF Tunnel)
                    │
               host:3101 (Node MCP server)
                    │
               Cloudflare v4 API (Global API Key or token)
```

## Quick Deploy

```bash
# 1. Copy server files to your host
REMOTE_DIR=/opt/cloudflare-global-mcp
mkdir -p "${REMOTE_DIR}"
cp infra/cloudflare-mcp/* "${REMOTE_DIR}/"

# 2. Create .env (never commit!)
cat > "${REMOTE_DIR}/.env" << 'EOF'
CLOUDFLARE_EMAIL=admin@example.com
CLOUDFLARE_API_KEY=<your-global-api-key>
CLOUDFLARE_ACCOUNT_ID=<your-account-id>
PORT=3101
HOST=127.0.0.1
EOF

# 3. Install & start
cd "${REMOTE_DIR}"
npm install
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chef-cloudflare-mcp cloudflared-mcp
```

## Tunnel Setup

1. Create a tunnel via the Cloudflare dashboard or API
2. DNS CNAME: `mcp-cf.example.com` → `<tunnel-id>.cfargotunnel.com`
3. Tunnel ingress: `mcp-cf.example.com` → `http://localhost:3101`
4. Optional: WAF skip rule for the MCP hostname if your client cannot send browser headers

## Service Management

```bash
sudo systemctl status chef-cloudflare-mcp
sudo systemctl restart chef-cloudflare-mcp
journalctl -u chef-cloudflare-mcp -f

sudo systemctl status cloudflared-mcp
sudo systemctl restart cloudflared-mcp
```

## MCP Client Configuration

Streamable HTTP example:

```json
{
  "cloudflare-global": {
    "type": "streamableHttp",
    "url": "https://mcp-cf.example.com/mcp",
    "disabled": false
  }
}
```

Local stdio fallback (development):

```json
{
  "cloudflare-global-local": {
    "type": "stdio",
    "command": "node",
    "args": ["/opt/cloudflare-global-mcp/server-http.mjs"],
    "env": {
      "CLOUDFLARE_EMAIL": "admin@example.com",
      "CLOUDFLARE_API_KEY": "<key>",
      "CLOUDFLARE_ACCOUNT_ID": "<account-id>"
    },
    "disabled": true
  }
}
```

## Tool Inventory (50+ tools)

| Category | Tools |
|----------|-------|
| Universal | `cf_request` (full API bypass) |
| Accounts/Zones | `cf_accounts_list/get`, `cf_zones_list/get/find/create/delete`, `cf_zone_settings/update`, `cf_zone_purge_cache` |
| DNS | `cf_dns_list/get/create/update/delete/export/import` |
| SSL/TLS | `cf_ssl_verify/universal/universal_update` |
| Workers | `cf_workers_list`, `cf_worker_get/get_code/put/delete`, `cf_worker_subdomains/routes/route_create/route_delete` |
| Pages | `cf_pages_projects/project_get/deployments/deployment_get/domains` |
| KV | `cf_kv_namespaces/list/read/write/delete`, `cf_kv_namespace_create/delete` |
| R2 | `cf_r2_buckets/objects`, `cf_r2_bucket_create/delete`, `cf_r2_object_get/delete` |
| D1 | `cf_d1_databases/get/create/delete/query` |
| Tunnels | `cf_tunnels_list/get/create/delete/config/config_update` |
| WAF/Firewall | `cf_waf_packages/rules/rule_update`, `cf_firewall_rules/rule_create/rule_delete`, `cf_rate_limits` |
| Analytics | `cf_analytics_dashboard/colos` |
| Logs/Audit | `cf_logpush_jobs`, `cf_logs_received`, `cf_audit_logs` |
| Admin | `cf_account_members/roles`, `cf_api_tokens/verify` |
| Fleet | `cf_fleet_summary` |

## Related

- Infra: `infra/cloudflare-mcp/`
- Cloudflare MCP plugin: [cloudflare/mcp-server-cloudflare](https://github.com/cloudflare/mcp-server-cloudflare)
