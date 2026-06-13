# Local Docker Deploy

```bash
cp .env.example .env
docker compose up --build
```

Cursor MCP snippet:

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

Change `KATER_PROFILE` in `.env` when a task needs a broader profile.
