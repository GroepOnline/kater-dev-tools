# Kater hardened pod (systemd)

Run Kater as a hardened container that bootstraps ChefVault secrets fail-closed
via `scripts/kater-with-chefvault.py` — the same wrapper the system service uses.
This is the "pod-ready" deployment path: a read-only root FS, no capabilities,
no privilege escalation.

## Build the image

```bash
docker build -t kater-dev-tools:latest .
# or: docker compose build
```

The image includes the vault-auth bootstrap wrapper at
`/app/scripts/kater-with-chefvault.py` and `uv` (the wrapper execs `kater` via
`uv`). It runs as non-root `kater` (uid 10001) with `/app/.kater` pre-created
owner-only so a named volume mounted there inherits the right ownership.

## Bootstrap the broker token (host, manual operator step)

The container needs a ChefVault consumer token so the wrapper can materialize the
`kater-dev-tools/ops` profile. **This is a manual operator step on the host** — see
`docs/ops/chefvault.md` for the full contract. Provider keys are never kept in a
durable env file; only the broker token is bootstrapped on the host.

- token file: `/etc/chef/kater/broker-token` (mode `0600`)
- env file: `/etc/chef/kater/secrets.env` (non-secret `KATER_*` overrides; the unit
  reads it via `EnvironmentFile`)
- broker binaries on the host PATH (`chefvault-profile`, `chefvault-profile-mcp`)
  are mounted read-only into the container

The token file is mounted read-only into the container and read by the wrapper's
mode-`0600` check, so it must be readable by the container runtime user. Create it
with the image's non-root uid:

```bash
sudo install -d -m 0755 /etc/chef/kater
sudo install -m 0600 /dev/null /etc/chef/kater/broker-token
printf '%s\n' '<kater broker token>' | sudo tee /etc/chef/kater/broker-token >/dev/null
sudo chown 10001:10001 /etc/chef/kater/broker-token
sudo chmod 0600 /etc/chef/kater/broker-token
```

## Install the unit

```bash
sudo install -m 0644 deploy/kater-pod.service /etc/systemd/system/kater-pod.service
sudo systemctl daemon-reload
sudo systemctl enable --now kater-pod.service
```

## Verify

```bash
systemctl status kater-pod.service          # active (running)
curl -fsS http://127.0.0.1:9091/health      # container healthcheck path
curl -fsS http://127.0.0.1:9091/health/live
curl -fsS http://127.0.0.1:9091/health/ready
journalctl -u kater-pod.service -n 100 --no-pager | rg -i 'token|secret|ghp_' || true
```

The container binds loopback only (`serve --host 127.0.0.1`); with host networking
that exposes 9090–9092 on the host loopback and lets the container reach the local
ChefVault broker at `127.0.0.1:8322`.

## Notes

- `ExecStartPre` pulls the image each start (idempotent, best-effort).
- Restart is `on-failure` with a 5s backoff.
- Keep the broker token on the host; never bake it into the image or env file.