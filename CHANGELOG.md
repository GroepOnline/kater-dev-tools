# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/GroepOnline/kater-dev-tools/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/GroepOnline/kater-dev-tools/releases/tag/v1.2.0
[1.1.1]: https://github.com/GroepOnline/kater-dev-tools/releases/tag/v1.1.1
[1.1.0]: https://github.com/GroepOnline/kater-dev-tools/releases/tag/v1.1.0
[1.0.0]: https://github.com/GroepOnline/kater-dev-tools/releases/tag/v1.0.0

## [Unreleased]

### Added

- Stamped runtime identity on `/health`, `/health/live`, `/health/ready`,
  `/api/status`, and `kater version` (`version`, `source_sha`, `release`,
  `artifact_digest`). Missing or malformed fields are null. Release assets
  now include `SHA256SUMS`.

## [1.2.0] - 2026-09-19

Execution Foundation train plus the company-control deploy path. Product
model is toolkit → integration → connection → action.

### Added

- Execution Foundation catalog and generic execute (`#95`):
  `execute(connection, action, input, identity, policy_context)`,
  `GET /api/connections`, admin-gated `POST /api/execute`, MCP
  `kater_tool_search` / `kater_execute`. Search ranks registered
  capabilities without loading every provider tool into agent context.
- Isolated ChefGroep product transport and disabled product export
  registry (`#92`, `#93`).
- External resource introspection client (`#91`) and Authentik OIDC RP
  (`#117`), with local-dev OIDC placeholders (`#114`).
- Company-control auto-deploy on green main CI (`#87`), including a
  healthy product MCP listener gate.
- Catalog unification of toolkits, integrations, plugins, and MCP (`#83`).
- Runtime-authoritative agent-session work/event transport keyed by
  existing remote contexts (`/api/contexts/{id}/session/*`, MCP tools,
  OpenAPI). Studio composer is a replaceable client over that contract.
- Studio Agent Activity focused on sessions and a refined material
  operator shell.
- Dashboard profile recovery (`Switch profile to core`) and browser
  Go/Reload/Close loading feedback (`aria-busy` + busy labels).
- Dry-run branch lifecycle scanner with terminal-name tombstones and
  exact-SHA receipts; unique patches are never auto-deleted.
- Admin-gated dynamic connector registration via `POST /api/connectors`
  and `kater connector add <definition.json>`; new connectors always
  start disabled with no permissions, and credential values remain out
  of the catalog.
- Bounded GitHub transport for PR-gate tools: typed errors, secret
  redaction, configurable subprocess timeout, and a strict read-only
  retry budget (`docs/ops/pr-gate.md`).

### Changed

- `kater_pr_gate` treats a nonempty `expected_head_sha` mismatch as
  `HEAD_STALE` BLOCK. Merge still requires the same exact-head pin.
- Independent APPROVE on a nonempty pin must cover that review commit
  OID. Empty review lists no longer inherit GitHub `reviewDecision`.
  `gate_for_pr` loads the same overlay policy as merge.
- GitHub-mapped commit authors are not auto-classified as fixers.
  Independent review is author ≠ reviewer ≠ policy `fixer_logins`,
  pinned to the exact head SHA.
- Default policy no longer blocks a protected base. GitHub branch
  protection is expected; `block_base_protected` remains an opt-in
  overlay.
- PR body/list I/O prefers GitHub REST (`gh api`) when `KATER_PR_REPO`
  is set. GraphQL stays only for `reviewThreads`.
- Doctor reports GitHub token env precedence and a SHA-256 fingerprint
  only. Never the token value.
- CI bans GitHub-hosted runners and uses fleet self-hosted labels
  (`#116`).

### Fixed

- Company-control cutover no longer dies on GNU `unlink` with two
  staged env paths (`#108`).
- Execution rejects malformed dangerous policy and preserves merge
  policy failures (`#106`).
- Catalog leaks closed; execute gates hardened.
- Restored database is validated before replacing live state (`#82`).
- Deploy writes use `sudo tee`; fetch before `cat-file`; fail closed
  on service-user release traversal; restore active reverse dependents.
- Auth fails closed on unreadable resource config.
- PR-gate `gh` calls no longer run as one-shot unbounded subprocesses.
- Branch-protection lookup no longer fail-opens on timeout/5xx/429.
- Merge writes never retry; a write timeout is reconciled by a bounded
  read and only reports success when `merged=true` at the original pin.
- `gh api` GET query parameters are placed in the URL. Field flags
  (`-f`) switched the method to POST and 404'd commit check-runs.

## [1.1.1] - 2026-09-01

Patch tag on the 1.1.x line. Package sources were bumped; this changelog
section was missing until 1.2.0.

## [1.1.0] - 2026-08-18

First GroepOnline git tag. `1.0.0` existed in package sources and this
changelog but was never tagged on `GroepOnline/kater-dev-tools`. Feature PRs
after that point stayed on `1.0.0` until this bump. Version sources:
`pyproject.toml` and `src/kater/__init__.py`. Protocol: `docs/release.md`.

### Added

- Catalog Connect fail-closed policy: admin on credential/OAuth/delete mutations, deny-default secret sink, and configured HTTPS public base URL (`docs/ops/catalog-connect.md`).
- Catalog Connect outbound OAuth.
- Usage / cost events ledger (`usage_events` migration) with `GET /api/usage` and `GET /api/usage/summary`; route decisions mirror into the ledger.
- Dashboard Fabric view for capabilities, contexts, and computer status (palette-only nav).
- HTTP capability discovery (`GET /api/capabilities`, `GET /api/capabilities/{id}`) and remote context CRUD (`/api/contexts*`) with migration v4 (`remote_contexts`).
- `docs/browser.md` plus `.env.example` notes for the three browser backends (`local`, `cdp`, `steel`/`remote`).
- OpenAPI paths for the native browser lane (`/api/browser/*`) and automations (`/api/automations/*`).
- `.env.example` knobs for optional browser providers, domain policy, and session limits.
- Deploy docs cover three-port layout (9090/9091/9092), `kater migrate apply` / `kater backup create`, and optional Playwright browser install.
- Shared agent-taste registry: `.agents/registry/taste.yaml` + overlays +
  `generate-taste.py` (cmd / Cursor / Claude Code artefacts)
- Decision boundary: UI-taste stays in design-system; agent-taste lives here
- Signals + eval gate: `signals.yaml`, `taste-signal.py`, `eval-score.py --gate`,
  thresholds/scorecard, CI job + nightly `agent-taste-eval.yml` (artefact only)
- Fleet runner `scripts/run-taste-brain-eval.sh` + systemd timer templates under
  `infra/` (not for laptop)
- Release contract (`release-policy.json` + `scripts/validate_release.py`) and
  post-merge bump protocol in `docs/release.md`.
- Streamable HTTP `/mcp` for Cursor cloud agents; MCP protocol negotiation (2025-06-18).
- Executable PR merge gate (`kater_pr_*`).
- Pod-ready image, vault-auth bootstrap, hardened pod unit.

### Changed

- Docker and Kubernetes deploy templates expose WebSocket port 9092, hint at a `/app/.kater` volume, and note optional Playwright for the browser lane.
- Org references swept to GroepOnline.

### Fixed

- Catalog Connect: HTTP `DELETE` now reaches the API handler; re-saving a token updates the existing account instead of duplicating it; disconnect clears gateway-written process env so the backend does not restart with the revoked token.
- Slack catalog table lists HTTP (Slack-hosted MCP) instead of stdio. `SLACK_BOT_TOKEN` is now `SLACK_ACCESS_TOKEN`.
- Cryptography 50.0.0 (GHSA Bleichenbacher oracle).
- CI PR lane accepts e2e=skipped; GitHub-hosted runners banned until Actions spending restored.

## [1.0.0] - 2025-01-01

Initial public release. Not tagged on the GroepOnline remote.

### Added

- Industrial-brutalist web dashboard (`kater-control`) for live gateway inspection.
- Developer MCP gateway with profile-gated tools for code agents (Cursor, Claude, etc.).
- `kater` CLI entrypoints: `kater`, `kater-routes`, `kater-capabilities`.
- Pluggable transport backends: stdio, SSE, and streamable HTTP.
- OAuth-authenticated upstream proxies and tunnel/deploy helpers.
- PR-control view with race-safe DOM rendering and standard layout.
