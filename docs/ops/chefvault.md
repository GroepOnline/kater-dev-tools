# ChefVault integration

Kater can obtain all adapter credentials from the collection-scoped ChefVault broker and
proxy the profile-only ChefVault MCP behind the gateway. Provider keys are not copied into
Git or a permanent shared `.env`; only one consumer-specific broker token is bootstrapped.

## One-time bootstrap

Install/build ChefVault so these binaries are available in `PATH`:

- `chefvault-profile`
- `chefvault-profile-mcp`

On the Kater host, create the consumer token file:

```bash
install -d -m 700 ~/.config/chefgroep
printf '%s\n' '<kater broker token>' > ~/.config/chefgroep/kater-broker-token
chmod 600 ~/.config/chefgroep/kater-broker-token
```

The token must allow profile `kater-dev-tools/ops` and only the `Kater/*` collections
referenced by that profile. It must not allow unrelated or master/admin collections.

Set the broker URL when it is not local:

```bash
export CHEF_VAULT_BROKER_URL=http://<broker-private-ip>:8322
```

## Start Kater

```bash
uv run python scripts/kater-with-chefvault.py up
```

The bootstrap does the following atomically:

1. resolves `kater-dev-tools/ops` through the broker;
2. writes `.kater/.env.chefvault` with mode `0600`;
3. passes the resolved variables directly to the Kater process;
4. loads `kater.chefvault_extension`;
5. adds private profile `chef-vault` to the active Kater profiles;
6. starts Kater with the original command arguments.

Examples:

```bash
uv run python scripts/kater-with-chefvault.py doctor
uv run python scripts/kater-with-chefvault.py serve --proxy
uv run python scripts/kater-with-chefvault.py tools --profile ops,chef-vault
```

`chefvault` then appears as a private stdio backend. Its tools list allowed secret profiles
and materialize them to a protected runtime directory. MCP tool responses contain paths and
environment key names only, never secret values.

## Rotation and fallback keys

Keep independent Vaultwarden items per provider (`primary`, `fallback`, `read-only`,
`agents-scoped`). Update the ChefVault profile mapping when an alias changes. Rotation does
not require editing Kater configuration: restart through the bootstrap and the fresh bundle
is resolved before the gateway starts.

## Production systemd (bc-scan-arm)

For the always-on runtimehost, do **not** start Kater from a durable plaintext
provider-key env file under a personal home directory.

Use:

- unit: `scripts/systemd/kater-system.service.example`
- non-secret config: `scripts/systemd/kater.conf.example` → `/etc/kater/kater.conf`
- broker token file: `/etc/kater/broker-token` (mode `0600`, owner `kater`)
- bootstrap: `scripts/kater-with-chefvault.py` via `ExecStart`

Full host layout and cutover gates: `docs/ops/bc-scan-arm-runtime.md`.

## Failure behavior

The startup fails before Kater launches when the broker token is missing, the profile is not
allowed, a required item is absent, or a referenced collection is outside the token scope.
Optional provider keys are reported by ChefVault but do not block startup.
