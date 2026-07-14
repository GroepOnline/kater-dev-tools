# Cursor Setup

Use one Kater server in Cursor instead of enabling every dev MCP directly.

```bash
uv sync
kater up
```

That writes project `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "kater": {
      "type": "sse",
      "url": "http://127.0.0.1:9090/sse"
    }
  }
}
```

Put adapter secrets in `.kater/.env` (auto-loaded). Example for Linear on the
`ops` profile:

```bash
# .kater/.env
KATER_PROFILE=ops
LINEAR_API_KEY=lin_api_...
```

Restart `kater up` / `kater serve` after changing secrets. Proxy backends enable
automatically when the required env for the active profile is present.
