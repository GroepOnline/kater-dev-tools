# Edge, Postgres, and Upstash Refresh Runbook

Use this runbook for CHE-322 when public edge artifacts are stale, the deployed
host is missing `DATABASE_URL`, or the Upstash MCP/cache path fails writes.

The live probe from 2026-07-02 found:

- Public edge artifacts still reported a 2026-06-16 `generated_at` value.
- `DATABASE_URL` was missing from the deployed `.env` on `sofie` / `bc-scan-2`.
- `utrecht-pg` on `bc-scan-2:5432` accepted connections.
- Upstash `SET` failed with HTTP 400.

Do not paste real connection strings, tunnel tokens, Redis credentials, API keys,
private IPs, or provider config into Git, GitHub, or Linear. Keep secrets in the
remote host environment or the secret manager used by the deployment.

## Gates

The ticket is complete only when all gates pass:

1. Public edge artifacts expose a fresh `generated_at` timestamp.
2. Readiness reports database availability as `db_ready: true`.
3. Upstash cache roundtrip succeeds with a write followed by a read.

## Inputs

Confirm these values before changing production:

| Item | Expected source |
| --- | --- |
| Edge host | Public Kater or app domain behind Cloudflare |
| App host | `sofie` or `bc-scan-2`, whichever currently serves the edge |
| Postgres DSN | Secret manager or remote-only `.env`; never commit it |
| Upstash credentials | Secret manager or remote-only `.env`; never commit them |
| Artifact command | Project deploy command or existing artifact refresh script |

## Preflight

Run local checks from a clean branch before touching the host:

```bash
git status --short --branch
uv run kater doctor
```

On the remote host, confirm the app directory and service name:

```bash
ssh <app-host> 'pwd; systemctl list-units --type=service | grep -E "kater|chef|mcp|edge"'
```

## Configure Postgres

On the remote host, verify Docker can see the Postgres container and that the app
environment has a `DATABASE_URL` key without printing the value:

```bash
ssh <app-host> '
  docker ps --format "{{.Names}}\t{{.Ports}}" | grep utrecht-pg
  cd <app-dir>
  test -f .env
  grep -q "^DATABASE_URL=" .env
'
```

If `DATABASE_URL` is missing, add it through the approved secret channel. Use a
remote-only edit or secret sync; do not write the value into a local file that may
be committed.

```bash
ssh <app-host> '
  cd <app-dir>
  umask 077
  cp .env ".env.backup.$(date -u +%Y%m%dT%H%M%SZ)"
  # Add DATABASE_URL=<secret value> via the approved operator path.
  grep -q "^DATABASE_URL=" .env
'
```

Restart the service only after the environment is present:

```bash
ssh <app-host> '
  sudo systemctl daemon-reload
  sudo systemctl restart <app-service>
  sudo systemctl status --no-pager <app-service>
'
```

## Refresh Edge Artifacts

From the remote app directory, run the existing artifact generation and deploy
flow for the public edge. If the project has no single refresh command, use the
same command sequence as the last successful deploy and record it in Linear.

```bash
ssh <app-host> '
  cd <app-dir>
  git fetch --all --prune
  git status --short --branch
  # Run the project-specific artifact refresh/deploy command here.
'
```

Verify the public response exposes a fresh timestamp:

```bash
curl -fsS https://<edge-host>/<artifact-path> | jq -r ".generated_at"
```

The returned timestamp must be newer than the stale 2026-06-16 value observed in
the live probe.

## Fix Upstash Cache

Confirm Upstash credentials are present without printing their values:

```bash
ssh <app-host> '
  cd <app-dir>
  grep -q "^UPSTASH_EMAIL=" .env
  grep -q "^UPSTASH_API_KEY=" .env
'
```

If the deployed app uses Redis REST variables instead of the Upstash MCP account
API variables, verify the expected variable names in the app code before editing
the environment. A 400 on `SET` usually means the request shape, endpoint, or
token pairing does not match the Upstash API being called.

Run a non-sensitive roundtrip using the app's existing cache command or endpoint:

```bash
# Replace with the app-specific cache probe.
curl -fsS https://<edge-host>/<cache-probe-path>
```

The probe should perform one write and one read, returning success without
including secret values in the response.

## Readiness Verification

Check health first, then the authenticated readiness/status endpoint used by the
deployment:

```bash
curl -fsS https://<edge-host>/health | jq .
curl -fsS -H "Authorization: Bearer <operator-token>" https://<edge-host>/<readyz-path> | jq .
```

Pass criteria:

- `/health` returns `status: ok`.
- Readiness includes `db_ready: true`.
- Cache probe confirms write/read success.
- Public artifact `generated_at` is fresh.

## Linear Closeout

Comment on CHE-322 with:

- Host touched and service restarted, without secrets or private addresses.
- The artifact `generated_at` value observed after refresh.
- The readiness result, including `db_ready: true`.
- The cache roundtrip result.
- Any follow-up PR or deploy reference.
