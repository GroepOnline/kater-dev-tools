# OSS / Private Split — Phase 2 Audit

**Date:** 2026-07-02  
**Scope:** `kater-dev-tools` working tree at split branch `feat/oss-private-split`

## Completion status (2026-07-02)

All org-specific items below were **resolved** on branch `feat/oss-private-split`:

| Action | Result |
|--------|--------|
| Move deploy scripts / systemd with production domain | → `OnlineChefGroep/utrecht-katermcp` (private) |
| Remove `src/kater/adapters/utrecht.py` | Deleted; extension hook added |
| Remove handoff docs, `docs/adapters/utrecht.md` | Deleted from OSS |
| Genericize `docs/PLAN-v1.0.md` | Removed from OSS (copy in private `docs/internal/`) |
| Update tests | `demo_private` fixture via `tests/fixtures/private_extension.py` |
| CI leak gate | `.github/workflows/no-org-leak.yml` + `.gitleaks.toml` |
| Private repo | https://github.com/OnlineChefGroep/utrecht-katermcp (`isPrivate: true`) |

**Verification:** 417 tests pass; no `chefgroep.nl`/`.online` in tracked OSS content; gitleaks clean.

---

## Summary (original audit)

| Classification | Count | Action |
|----------------|-------|--------|
| generic-example | 15+ | Keep in OSS |
| org-specific-config | 28 | Move to `utrecht-katermcp` or genericize in OSS |
| credential-shaped (P0) | 1 (local only) | Purge locally; not in git index |

## Hit table (original — pre-split)

| File | Line(s) | Match (redacted) | Classification | Action |
|------|---------|------------------|----------------|--------|
| `scripts/ensure-online.sh` | 11–12 | `https://kater.chefgroep.online/...` | org-specific-config | ✅ Moved |
| `scripts/systemd/kater.service` | 8, 14–15 | production domain | org-specific-config | ✅ Moved |
| `docs/PLAN-v1.0.md` | 182, 272, 276 | production domain | org-specific-config | ✅ Removed from OSS |
| `docs/HANDOFF-2026-06-13.md` | multiple | internal paths | org-specific-config | ✅ Removed |
| `docs/HANDOFF-2026-06-25.md` | multiple | internal paths | org-specific-config | ✅ Removed |
| `docs/adapters/utrecht.md` | 9, 17 | org adapter doc | org-specific-config | ✅ Moved |
| `src/kater/profiles.py` | utrecht ToolSource | org-specific-config | ✅ Removed; extension hook |
| `src/kater/adapters/utrecht.py` | all | org adapter | org-specific-config | ✅ Moved |
| `src/kater/registry.py` | utrecht_* tools | org-specific-config | ✅ Moved |
| `src/kater/chains.py` | utrecht chain | org-specific-config | ✅ Moved |
| `tests/test_utrecht_adapter.py` | all | org tests | org-specific-config | ✅ Moved |
| `.kater/oauth.json` | local OAuth state | credential-shaped | ⚠️ Purge locally; rotate tokens |

## Move map → `utrecht-katermcp`

| OSS path | Private path |
|----------|--------------|
| `scripts/ensure-online.sh` | `deploy/ensure-online.sh` |
| `scripts/systemd/kater.service` | `deploy/systemd/kater.service` |
| `src/kater/adapters/utrecht.py` | `src/utrecht_kater/adapter.py` |
| utrecht registry/chains/profile defs | `src/utrecht_kater/extensions.py` |
| `docs/adapters/utrecht.md` | `docs/adapters/utrecht.md` |
| `docs/HANDOFF-*.md`, `docs/PLAN-v1.0.md` | `docs/internal/` |
| — | `profiles/ops.yaml`, `profiles/utrecht.yaml` |
| — | `.env.example`, `docs/DEPLOYMENT.md` |

## OSS replacements

| Removed | Replaced with |
|---------|---------------|
| Hardcoded production domain | `kater.example.com` or `$KATER_DOMAIN` |
| `utrecht` profile in core | `KATER_EXTENSIONS_MODULE` (private overlay) |
| `PRIVATE_PROFILES = {"utrecht"}` | Loaded from extension module when set |
