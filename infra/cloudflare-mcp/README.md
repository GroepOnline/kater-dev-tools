# Cloudflare Global MCP — Infrastructure

Server files for a Cloudflare Global MCP server (HTTP/Streamable transport behind Cloudflare Tunnel).

## Files

- `tools.mjs` — Shared tool definitions (50+ Cloudflare tools)
- `server-http.mjs` — HTTP/Streamable transport for remote access
- `package.json` — Node.js dependencies
- `systemd/*.service` — Example systemd units for the MCP server and tunnel

## Deploy

Replace `REMOTE_HOST` and paths with your deployment host.

```bash
REMOTE_HOST=your-server
REMOTE_DIR=/opt/cloudflare-global-mcp

# Copy files to host (including systemd units)
scp *.mjs package.json systemd/*.service "${REMOTE_HOST}:${REMOTE_DIR}/"

# Install and enable services on the remote host
ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && npm install && \
  sudo cp systemd/*.service /etc/systemd/system/ && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable --now chef-cloudflare-mcp cloudflared-mcp"
```

## Tunnel

Create a Cloudflare Tunnel that routes `mcp-cf.example.com` → `http://localhost:3101` (or your chosen port).

## Reference

- Docs: `docs/cloudflare-mcp.md`
