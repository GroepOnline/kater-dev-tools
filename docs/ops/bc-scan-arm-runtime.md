# Kater runtime on bc-scan-arm

Target: move the canonieke Kater runtime off laptop `joep` onto always-on
`bc-scan-arm`, with ChefVault fail-closed secret bootstrap and no
`/home/<person>` paths.

This is packaging + runbook only. Do **not** cut over production traffic until
shadow deploy + soaktest pass.

## Layout

```text
/opt/kater/releases/<git-sha>/
/opt/kater/current -> /opt/kater/releases/<git-sha>
/etc/kater/kater.conf          # non-secret config (0640, root:kater)
/etc/kater/broker-token        # ChefVault consumer token (0600, kater:kater)
/var/lib/kater                 # SQLite / settings state
/var/cache/kater               # fleet cache and other regenerable data
/var/log/kater                 # optional file logs (journald remains primary)
/run/kater                     # RuntimeDirectory (tmpfs)
```

## Service identity

```bash
sudo useradd --system --home /var/lib/kater --shell /usr/sbin/nologin kater
sudo install -d -o kater -g kater -m 0750 /var/lib/kater /var/cache/kater /var/log/kater
sudo install -d -o root -g kater -m 0750 /etc/kater
```

## Non-secret config

```bash
sudo install -o root -g kater -m 0640 \
  /opt/kater/current/scripts/systemd/kater.conf.example \
  /etc/kater/kater.conf
```

Edit host-specific values:

- `UTRECHT_FLEET_INVENTORY_PATH=/var/cache/kater/utrecht-fleet/inventory/fleet.json`
- keep `KATER_HOST=127.0.0.1` while `KATER_AUTH_MODE=none`
- keep CI SSH target pointing at `ubuntu@bc-scan-2`

## ChefVault broker token

```bash
sudo install -o kater -g kater -m 0600 /dev/null /etc/kater/broker-token
sudo -u kater tee /etc/kater/broker-token >/dev/null <<'EOF'
<kater broker token>
EOF
sudo chmod 0600 /etc/kater/broker-token
```

Token scope:

- profile `kater-dev-tools/ops`
- only `Kater/*` collections needed by that profile
- no admin / unrelated collections

Broker URL (private, not public):

```bash
# example in /etc/kater/kater.conf
CHEF_VAULT_BROKER_URL=http://127.0.0.1:8322
```

## Install release

```bash
SHA="$(git -C /path/to/checkout rev-parse HEAD)"
sudo mkdir -p "/opt/kater/releases/$SHA"
sudo rsync -a --delete \
  --exclude .git --exclude .venv --exclude .kater \
  /path/to/checkout/ "/opt/kater/releases/$SHA/"
sudo chown -R kater:kater "/opt/kater/releases/$SHA"
# Runtime state dir the unit lists in ReadWritePaths; systemd needs it to exist
# before ExecStart, and rsync excluded it from the release.
sudo install -d -o kater -g kater -m 0700 "/opt/kater/releases/$SHA/.kater"
sudo ln -sfn "/opt/kater/releases/$SHA" /opt/kater/current
sudo -u kater bash -lc 'cd /opt/kater/current && uv sync --frozen'
```

The release must be owned by `kater` before `uv sync`: the virtualenv is created
project-local at `/opt/kater/current/.venv`, and the unit's `ExecStart` depends on
`/opt/kater/current/.venv/bin/python` existing.

## Fleet cache bootstrap

```bash
sudo -u kater bash -lc '
  mkdir -p /var/cache/kater
  if [ ! -d /var/cache/kater/utrecht-fleet/.git ]; then
    git clone --depth 1 git@github.com:<org>/<fleet-inventory-repo>.git \
      /var/cache/kater/utrecht-fleet
  else
    git -C /var/cache/kater/utrecht-fleet pull --ff-only
  fi
  test -f /var/cache/kater/utrecht-fleet/inventory/fleet.json
'
```

Prefer atomic refresh later (clone/pull into temp dir → validate → rename).

## Systemd unit

```bash
sudo install -m 0644 \
  /opt/kater/current/scripts/systemd/kater-system.service.example \
  /etc/systemd/system/kater.service
sudo systemctl daemon-reload
sudo systemctl enable --now kater.service
```

The unit:

- runs as `User=kater`
- uses `EnvironmentFile=/etc/kater/kater.conf` for non-secrets
- starts via `scripts/kater-with-chefvault.py serve ...` (fail-closed)
- binds loopback only
- hardens filesystem with `ProtectHome=true` and `ProtectSystem=strict`

## Acceptance checks (shadow)

```bash
systemctl is-active kater.service
curl --fail --silent http://127.0.0.1:9091/health/live
curl --silent http://127.0.0.1:9091/health/ready
journalctl -u kater.service -n 100 --no-pager | rg -i 'token|secret|ghp_|cfut_|cfat_' || true
```

Negative tests (must fail closed / degrade predictably):

1. missing `/etc/kater/broker-token`
2. broker unreachable
3. missing fleet.json
4. `bc-scan-2` SSH unreachable
5. host reboot → service returns without laptop `joep`

## Cutover gate

Only after:

- no runtime path under `/home/joep`
- secrets materialize via ChefVault, not a durable plaintext env of provider keys
- health/live always up when process is up
- health/ready reports component degradation clearly
- soaktest on `bc-scan-arm` (memory/CPU/FDs/orphans) passes
- laptop runtime kept as rollback for the observation window
