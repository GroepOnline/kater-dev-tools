# Cursor Setup

Use one Kater server in Cursor instead of enabling every dev MCP directly.

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

Keep task-specific tools behind `KATER_PROFILE` and restart the container when
switching profile.
