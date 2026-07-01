# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Reporting a vulnerability

Please **do not** open public GitHub issues for security problems.

Email security reports to the repository maintainers via GitHub private security advisories:
https://github.com/OnlineChefGroep/kater-dev-tools/security/advisories/new

Include:

- Description of the issue and impact
- Steps to reproduce
- Affected version/commit
- Suggested fix (if any)

We aim to acknowledge reports within 72 hours.

## Deployment security

Kater exposes MCP tools over HTTP/SSE. Treat a public instance like an API gateway:

1. **Never expose `/sse` without auth.** Set `KATER_PUBLIC=1` and `KATER_AUTH_MODE=oauth` or `apikey`.
2. **Use OAuth for ChatGPT Remote MCP** — built-in PKCE flow at `/authorize` and `/token`.
3. **Use API keys for Cursor/agents** — `Authorization: Bearer <key>` on MCP and REST requests.
4. **Enable rate limiting** — `KATER_RATE_LIMIT=60` (default when public). Applied to REST, MCP `/sse`, and WebSocket; `X-Forwarded-For` is honored only from loopback/private proxy peers or with `KATER_TRUST_PROXY=1`.
5. **Restrict CORS** — avoid `*` on public deployments; set `KATER_CORS_ORIGINS`.
6. **Keep adapter secrets in env** — never commit `.env`; Kater redacts secrets in API/MCP tool responses.
7. **Bind to loopback behind a tunnel** — Cloudflare Tunnel or Tailscale; do not expose raw ports.
8. **Set an admin key** — `KATER_ADMIN_KEY` separates tool usage from settings changes. In public mode, settings mutations are blocked without it.
9. **Keep client registration closed** — public `/register` is disabled unless `KATER_ALLOW_DYNAMIC_REGISTRATION=1` and `KATER_REGISTRATION_TOKEN` is set. Prefer pre-seeded first-party clients/admin bootstrap over anonymous runtime registration.
10. **Dashboard key** — `KATER_DASHBOARD_KEY` is an optional shortcut that bypasses OAuth token validation for a browser dashboard session in `oauth` mode. Leave unset unless you need it.

OAuth `redirect_uri` values must be `https` (or `http` for loopback per RFC 8252); dangerous schemes (`javascript:`, `data:`) are rejected at registration.

Run `kater doctor` before going live — it flags public deployments without auth.
