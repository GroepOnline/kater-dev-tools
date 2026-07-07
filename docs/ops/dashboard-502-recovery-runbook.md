# Dashboard / WS 502 Bad Gateway Recovery Runbook

Use this runbook when the live Kater dashboard at `https://kater.chefgroep.online`
returns a Cloudflare **502 Bad Gateway** (Ray ID shown on the error page, e.g.
Amsterdam edge). The API, dashboard, and `/ws` WebSocket are all served through a
Cloudflare Tunnel (`cloudflared`) to the local Kater server.

A 502 means the Cloudflare edge is healthy but the origin returned no valid
response: either the Kater server (`kater serve`), the `cloudflared` tunnel
process, or the tunnel token is down/expired. It does **not** indicate a code
or dashboard-redesign problem (neither CHE-457 nor CHE-322 is involved) — the
server is simply unreachable.

Do not paste real connection strings, tunnel tokens, Redis credentials, API keys,
private IPs, or provider config into Git, GitHub, or Linear. Keep secrets in the
remote host environment or the secret manager used by the deployment.

## Architecture (for context)

- **API server**: stdlib `ThreadingHTTPServer` on `:9091` (per
  `src/kater/runtime.py` / `api.py`). Serves `/dashboard`, `/api/*`,
  `/api/ws-ticket`, and the `GET /health` probe.
- **MCP/WS server**: a separate `uvicorn` process (`build_sse_app` in
  `mcp_server.py`). This is the process that actually handles the `/ws`
  WebSocket upgrade.
- Both are booted together by `kater serve` (the runtime starts the API server
  and the uvicorn WS server together).
- **Tunnel**: provisioned by `scripts/deploy-cloudflare.sh` and
  `scripts/provision-cloudflare-tunnel.sh`; runs as a user systemd unit
  `kater-cloudflared.service`. The deploy script gates tunnel start on a passing
  `http://127.0.0.1:9091/health` check (`deploy-cloudflare.sh`).

## Inputs

Confirm these values before changing production:

| Item | Expected source |
| --- | --- |
| Edge host | `kater.chefgroep.online` (Cloudflare Tunnel) |
| App host | `jan` or `sofie` via Tailscale SSH |
| Domain | `kater.chefgroep.online` |
| `CLOUDFLARE_ACCOUNT_ID` | Secret manager / remote env; needed only to re-provision a tunnel |
| Local API port | `127.0.0.1:9091` |

## Quick Triage on the Host

SSH in via Tailscale, then run the four checks below in order.

```bash
ssh jan   # or: ssh sofie
```

1. **Is the API server alive?**

   ```bash
   curl -sf http://127.0.0.1:9091/health && echo API_OK || echo API_DOWN
   ```

2. **Is the tunnel alive?**

   ```bash
   systemctl --user status kater-cloudflared.service
   ```

3. **Tunnel error log (if down or unhealthy):**

   ```bash
   journalctl --user -u kater-cloudflared -n 50 --no-pager
   ```

4. **Which Kater processes are running?**

   ```bash
   ps aux | grep -E "kater|uvicorn|cloudflared"
   ```

## Failure Modes and Fixes

### API server down (`health` fails → `API_DOWN`)

The combined `kater serve` process (API + uvicorn WS server) is not running.
Restart it via the unit/systemd that launches `kater serve`:

```bash
# Restart whichever unit boots `kater serve` on this host.
systemctl --user restart kater.service      # if a kater.service unit exists
# Otherwise, re-run the deployment entrypoint for the host.
```

If no dedicated unit exists, re-run the host's serve command (the same command
used at boot). After restart, confirm health returns `API_OK`.

### Health OK but `/ws` still 502

The API server is up, but the **uvicorn WS/MCP server** (the `/ws` backend) is
not. Because runtime boots API + uvicorn together, a partially-up state means the
combined serve died midway. Restart the combined serve the same way as above:

```bash
systemctl --user restart kater.service      # restarts API + uvicorn together
```

Then verify `/health` and a WebSocket ticket roundtrip from the host.

### `cloudflared` dead (tunnel unit down)

The Kater server is fine but the tunnel process died. Restart the tunnel unit:

```bash
systemctl --user restart kater-cloudflared.service
systemctl --user status --no-pager kater-cloudflared.service
```

If the unit will not stay up, re-run the deploy script, which re-checks `/health`
before starting the tunnel:

```bash
cd <app-dir>
bash scripts/deploy-cloudflare.sh
```

### Tunnel token expired (re-provision)

A 502 that persists after restarting both services, with tunnel logs showing
auth/token errors, means the Cloudflare tunnel token/credentials expired.
Re-provision the tunnel (requires `CLOUDFLARE_ACCOUNT_ID` in the environment):

```bash
cd <app-dir>
export CLOUDFLARE_ACCOUNT_ID=<secret-from-manager>
bash scripts/provision-cloudflare-tunnel.sh
uv run kater tunnel config -p cloudflare --domain kater.chefgroep.online
systemctl --user restart kater-cloudflared.service
```

## Verification

After the fix, confirm locally then via the edge:

```bash
# Local API health
curl -sf http://127.0.0.1:9091/health && echo API_OK || echo API_DOWN

# Edge health through the tunnel
curl -fsS https://kater.chefgroep.online/health
```

Then load `https://kater.chefgroep.online/dashboard` in a browser and open the
app's WebSocket-backed feature. Confirm there is **no 502** and the dashboard
loads normally.

Pass criteria:

- `http://127.0.0.1:9091/health` returns `API_OK`.
- `https://kater.chefgroep.online/health` responds successfully.
- `/dashboard` renders with no Cloudflare 502.
- `/ws` upgrade succeeds (no 502 in the browser/network log).

## Prevention

- The systemd units should set `Restart=always` so both `kater serve` and
  `kater-cloudflared.service` auto-recover from crashes. Confirm after a fix:
  ```bash
  systemctl --user show kater-cloudflared.service -p Restart
  ```
- `scripts/deploy-cloudflare.sh` already gates tunnel start on a passing
  `/health` check, preventing a tunnel from coming up against a dead origin.
- Monitor `/health` externally so a downed origin is caught before users hit a
  502.

## Record

Comment on the related ticket with: the host touched, the service/unit restarted,
the deduced failure mode (API down / uvicorn down / tunnel dead / token expired),
and the verification result (health OK, dashboard loads, no 502). Do not include
secrets, private IPs, or tokens.
