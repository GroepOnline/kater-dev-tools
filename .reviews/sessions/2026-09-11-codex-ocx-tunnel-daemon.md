# 2026-09-11 — codex via OCX-tunnel + daemon voor remote

## Probleem
- `~/.codex/config.toml` was root:root 0600 → jan kon niet lezen (`Permission denied`,
  `Toegang geweigerd`, stale-arg0-cleanup warnings).
- Codex direct op ChatGPT (`model = "gpt-6-astra"`, OAuth in `auth.json` revoked →
  401 `token_revoked`-loop in `app-server.log`).
- OCX-proxy (`ocx.config.toml` → `127.0.0.1:10100`) stond niet in de hoofdconfig.
- Mijn eerste `[model_providers.opencodex]` met `requires_openai_auth = false` gaf
  `Error loading configuration: Model provider 'opencodex' not found` in de TUI.
- App-server 0.153.4 unmanaged (IDE-gestart) vs CLI 0.154.0; remote-control aan maar
  geen managed daemon.

## Fix (alles via OCX-tunnel, geen directe ChatGPT-route meer)
1. `sudo chown jan:jan + chmod 600 ~/.codex/config.toml` (backup `.bak.20260912-0028`).
2. `model = "azure-us/gpt-6-astra"` + `model_provider = "opencodex"` + tabel exact
   volgens OCX-injector (`ocx-convergence/lane-b-runtime/src/codex/inject.ts`,
   `buildProviderTableBlock`): `requires_openai_auth = true` is verplicht —
   met `false` herkent codex 0.154.0 de provider niet.
3. Token-SSOT `~/.opencodex/service-api-token` (0600) gevuld vanaf control-01
   `/etc/chef/opencodex/service-api-token` (zelfde file als de server-secret-mount,
   nooit geprint, direct pipe). Tunnel + key geverifieerd: `/v1/models` → 132 modellen.
4. `~/.config/fish/conf.d/secrets.fish` exporteert `OPENCODEX_API_AUTH_TOKEN`
   uit het token-bestand (alleen als unset).
5. Stale unmanaged app-server (0.153.4) gestopt, `daemon start` (managed pid),
   `daemon bootstrap` (durable), `enable-remote-control` → beide 0.154.0,
   `remoteControlEnabled: true` op `app-server-control.sock`.
6. Deprecation-warning opgelost: `[features] request_permissions` → `exec_permission_approvals`.
7. Tailscale-remote `codex app-server proxy`-brug was al actief en blijft werken
   tegen dezelfde control-socket.

## Bewijs
- `codex exec "Reply with exactly: PROXY-OK"` → `PROXY-OK` (2x), provider opencodex.
- `daemon version` → running, managed, 0.154.0/0.154.0, remoteControl true.
- Locatie: `~/.codex/` is correct; `~/.config/codex*` bestaat niet voor codex.

## Open / gebruiker
- ChatGPT-OAuth in `~/.codex/auth.json` is nog steeds revoked — irrelevant voor de
  proxy-route; pas `codex login` doen als directe ChatGPT-route ooit weer nodig is.
- Na reboot: daemon starten vanuit login-shell (fish laadt token), dan werkt remote weer.
