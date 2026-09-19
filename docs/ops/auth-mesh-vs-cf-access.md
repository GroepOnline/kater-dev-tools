# Mesh Auth vs Cloudflare Access (Kater)

Kater on **bc-scan-arm** (Tailscale GREEN, REST `:9091`) is reachable at the public
Kater hostname. Today that hostname is still primarily **Cloudflare Access**
(human/browser gate). **ChefGroep mesh Auth** on **chef-authvault** is GREEN (mesh listener **`:9000`**);
public Authentik is live at **`auth.chefgroep.online`** (`.nl` alias exists;
treat `.online` as canonical). Authentik already has the mesh OIDC app
**`chefgroep-kater-oidc`** (issuer slug **`kater`**). This repo does not apply
DNS or Cloudflare changes.

Operator map (canonical production URLs and redirect URIs):
[deploy-server.md](../deploy-server.md#chefgroep-mesh-auth-operator-status).

## Modes

| Mode | When | Who authenticates the browser |
| --- | --- | --- |
| **Access (edge)** | Default today on the public Kater hostname | Cloudflare Access, then optional `KATER_AUTH_MODE` |
| **Authentik (product)** | `AUTH_OIDC_ISSUER` + `AUTH_OIDC_CLIENT_ID` set | Authentik OIDC (`/authorize` → IdP → `/oidc/callback`) |
| **Local none** | Loopback / `docker-compose.dev.yml` | No gate (`KATER_AUTH_MODE=none`) |

**Prefer Authentik** whenever `AUTH_OIDC_*` is fully set. Do not run both
interactive Access login *and* Authentik on the same browser path — Access
will swallow the OIDC redirect. Keep Access as a temporary edge wrap only
until the cutover checklist below is done.

## Surfaces

| Surface | Port | Auth today | Auth target |
| --- | --- | --- | --- |
| REST + dashboard | 9091 | CF Access in front of HTTPS; Kater may use `KATER_AUTH_MODE=none` on loopback | Authentik RP via `AUTH_OIDC_*` + `chefgroep-kater-oidc`; local codes still from `/token` |
| Private MCP SSE | 9090 | Same as REST path when tunneled | Bearer / API key at Kater |
| Product MCP | 9093 | Off unless `KATER_RESOURCE_AUTH_ENABLED=1` | OAuth bearer + Auth introspection |

## Cloudflare Access (today)

Use this path when operators or agents hit the public Kater hostname in a browser
or through Access-aware tunnels **and** `AUTH_OIDC_*` is unset:

1. User authenticates at Cloudflare Access (identity provider configured in CF Zero Trust).
2. Traffic reaches Kater on bc-scan-arm after Access allows the session.
3. Kater still enforces its own `KATER_AUTH_MODE` on `/sse` and API routes unless
   configured for `none` on the loopback bind.

**Local parity without Access:** bind to loopback and disable public mode:

```bash
cp .env.example .env
./scripts/dev-boot.sh native
./scripts/dev-health.sh
```

**Docker Compose dev stack** (laptop or **Dev Containers**): `./scripts/dev-boot.sh compose`
with `docker-compose.dev.yml`. **Cursor Cloud** agent VMs often have **no Docker daemon** —
use the **native** path above instead of Compose.

## Mesh Auth / Authentik (chef-authvault)

Mesh Auth issues tokens; Kater **validates** product MCP via `KATER_RESOURCE_AUTH_*`
and **logs humans in** via `AUTH_OIDC_*` against the public issuer. Kater does
not register clients or commit secrets.

| Concern | Where it lives |
| --- | --- |
| Live mesh client id | `chefgroep-kater-oidc` (Authentik on chef-authvault) |
| Live issuer (canonical) | `https://auth.chefgroep.online/application/o/kater/` |
| Discovery | `{issuer}.well-known/openid-configuration` (200 on `.online`) |
| Redirect URI allowlist | [deploy-server.md](../deploy-server.md#chefgroep-mesh-auth-operator-status) + `config/oidc/*.example.yaml` |
| Service introspection key | Secret authority → `KATER_RESOURCE_AUTH_SERVICE_KEY` |
| Product login env | `AUTH_OIDC_*` in `.kater/.env` (after secret copy) |

Local / dev OIDC (loopback callback, no CF DNS):

```bash
# .kater/.env — secret from ChefVault, never git
AUTH_OIDC_ISSUER=https://auth.chefgroep.online/application/o/kater/
AUTH_OIDC_CLIENT_ID=chefgroep-kater-oidc
AUTH_OIDC_CLIENT_SECRET=  # ChefVault
AUTH_OIDC_REDIRECT_URI=http://127.0.0.1:9091/oidc/callback
AUTH_OIDC_SCOPES=openid
KATER_AUTH_MODE=oauth
```

```bash
uv run kater serve --profile core --no-proxy --host 127.0.0.1
./scripts/oidc-canary.sh
```

Canary proves discovery + `/oidc/login` → 302 to Authentik authorize + callback
error contract. A full code exchange needs the client secret (not in git).

Until `AUTH_OIDC_*` is wired on bc-scan-arm:

- Keep **product MCP disabled** (`KATER_RESOURCE_AUTH_ENABLED` unset or `0`) unless introspection is configured.
- Use **local dev** (`docker-compose.dev.yml` or `kater serve --no-proxy` with `KATER_AUTH_MODE=none`) when OIDC is unset.
- Store client secrets only in ChefVault / `.kater/.env` — never in git.

## Production cutover checklist (CoS / CF lane)

This PR does **not** apply Cloudflare DNS, Access apps, or tunnel config.
A human on the CF/CoS lane must:

1. **Authentik** — confirm `chefgroep-kater-oidc` redirect URIs include:
   - `http://127.0.0.1:9091/oidc/callback`
   - `http://localhost:9091/oidc/callback`
   - `https://kater.chefgroep.online/oidc/callback`
2. **bc-scan-arm env** — set `AUTH_OIDC_*` + `KATER_AUTH_MODE=oauth` from ChefVault.
   Restart Kater. `curl -sf http://127.0.0.1:9091/oidc/status` → `"enabled": true`.
3. **Cloudflare Access policy** (required so Authentik can complete the dance):
   - Bypass or disable Access on these public paths (same idea as product MCP):
     `/oidc/login`, `/oidc/callback`, `/authorize`, `/token`, `/register`,
     `/revoke`, `/.well-known/*`, `/health`, `/health/live`, `/health/ready`,
     `/oidc/status`.
   - **Preferred:** remove the Access application on the Kater hostname once
     Authentik + `KATER_AUTH_MODE=oauth` are verified, so Authentik is the only
     human gate.
   - Do **not** leave interactive Access in front of `/oidc/callback`.
4. **Do not change DNS** from this repo. Public host and auth host stay as today.
5. **Verify** loopback canary, then a real browser login on the public host
   (authorize → Authentik → callback → dashboard token). Product MCP paths
   (`/mcp`, `/.well-known/oauth-protected-resource/mcp`) stay Access-bypass
   for machine OAuth as already documented.

## Product MCP vs Access

Only these paths must reach Kater **without** an interactive Access login (machine
OAuth):

- `/mcp`
- `/.well-known/oauth-protected-resource/mcp`

After Authentik cutover, add the OIDC paths listed above. All other public paths
may remain behind Access until Access is removed. See deploy-server for tunnel routing.

## Verify

```bash
# Loopback / native (Cloud agents) or after compose on laptop
./scripts/dev-health.sh

# Product OIDC (server running; no secrets needed for authorize 302)
AUTH_OIDC_ISSUER=https://auth.chefgroep.online/application/o/kater/ \
AUTH_OIDC_CLIENT_ID=chefgroep-kater-oidc \
./scripts/oidc-canary.sh

# With gateway running (CI parity)
curl -fsS http://127.0.0.1:9091/health
./scripts/e2e-mcp.sh
```

Smoke CLI (`./scripts/smoke.sh`) still requires the server **stopped** (SQLite writer).
