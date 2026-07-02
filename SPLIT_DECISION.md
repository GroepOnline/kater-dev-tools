# OSS / Private Split — Phase 1 Decision

**Date:** 2026-07-02  
**Repos:** `OnlineChefGroep/kater-dev-tools` (public OSS) · `OnlineChefGroep/utrecht-katermcp` (private deployment)

## Decision

**Create `utrecht-katermcp` as a fresh, empty private repository. Do not fork `kater-dev-tools`.**

## Evidence

### History scan (`git log --all -p` + pattern grep)

| Finding | Classification | Notes |
|---------|----------------|-------|
| `api_key` / `token` / `secret` / `password` in diffs | Benign | Auth code, tests, docs, env placeholders (`lin_api_...`, `admin-secret`) |
| `postgres://` / `redis://` with credentials | None | No connection strings with embedded credentials in history |
| `BEGIN.*PRIVATE KEY` | Benign | Redaction regex in adapter code, not a real key |
| `kater.chefgroep.online` in file content | **Org-specific** | Deploy scripts, systemd unit, `docs/PLAN-v1.0.md` (added then partially removed from README/deploy defaults) |
| Author emails `*@chefgroep.nl` / `*@chefgroep.online` | **Org-specific** | Commit metadata only |
| Commit `c59747d` ("secret leak") | Benign (code bug) | Runtime exfiltration via MCP tools; fixed with `include_secrets=False` on exposed surfaces — not committed credentials |

### gitleaks 8.24.2 (`--log-opts="--all"`)

- **39 commits** scanned (~2.75 MB)
- **2 findings** — both **false positives**:
  - `scripts/e2e-mcp.sh:72` — RFC 6455 WebSocket handshake test nonce (`REDACTED_GENERIC_API_KEY)
  - `tests/test_hardening.py:580` — same test fixture
- **No live API keys, tokens, or private keys** in git history

### `.kater/` runtime state

- `git log --all -- .kater/oauth.json` shows commits that **removed** committed runtime state (`7709b5c`: "remove committed runtime state")
- `git show` on historical `.kater/oauth.json` blobs: **empty** (no token payloads in history)
- Current working tree has gitignored `.kater/oauth.json` with live OAuth state — **not tracked**; requires local purge + token rotation (operational hygiene, not a history blocker for this split)

### trufflehog

Not installed in the scan environment. gitleaks covered full history.

## Fork vs fresh

| Criterion | Result |
|-----------|--------|
| Credential-shaped content in history? | **No** (gitleaks false positives only) |
| Org-specific content in history? | **Yes** — `chefgroep.online` domain, org author emails |
| Fork inherits org-specific history? | **Yes** |

Per split policy: fork is acceptable only when history is clean of **both** secrets and org-specific config. Org-specific domain strings are present, so **fork is not acceptable**.

**Fresh private repo** also avoids carrying ~42 commits of public-OSS evolution into a deployment-only home and keeps `utrecht-katermcp` clearly scoped.

## P0 credential report

**No P0 committed credential leak** blocking the split.

**Operational follow-up (not split-blocking):** purge gitignored `.kater/oauth.json` on operator machines and rotate OAuth tokens if that file was ever copied or backed up outside `.gitignore`.

## Final status (2026-07-02)

- OSS strip PR: https://github.com/OnlineChefGroep/kater-dev-tools/pull/17 (CI green)
- Private overlay: https://github.com/OnlineChefGroep/utrecht-katermcp (`isPrivate: true`, 11 tests)
- Local verification: 417 pytest pass; gitleaks clean with `.gitleaks.toml`
