# Residual Review Findings — land/recovery-connections-plugins-20260912

Source run: ce-code-review `20260912-090228-f6ffcf9d`, branch-remote review of
`land/recovery-connections-plugins-20260912` @ `a33fee8` against `main` @ `af546b2`,
with plan `.compound-engineering/artifacts/plans/2026-09-12-001-chore-branch-pr-consolidation-plan.md`.
Review envelope: 8 personas, verdict Ready with fixes; 3 findings applied on the
branch (`fix(review): apply review findings` — malformed-entry skip, shared
plugin-id normalizer, deleted unused `get_connection_view`).

## Filed

- P2 `src/kater/api/fabric_routes.py:792` — Agent tool missing for GET /api/connections surface — https://github.com/GroepOnline/kater-dev-tools/issues/96
- P2 `src/kater/api/fabric_routes.py:812` — Agent tool missing for GET /api/plugins/{id} detail — https://github.com/GroepOnline/kater-dev-tools/issues/97
- P2 `src/kater/connections.py:128` — Stored-but-unconfigured connection hides configured runtime env row — https://github.com/GroepOnline/kater-dev-tools/issues/98
- P2 `src/kater/plugins.py:126` — Plugin IDs still disagree with fabric_catalog list IDs — https://github.com/GroepOnline/kater-dev-tools/issues/99
- P3 `src/kater/api/fabric_routes.py:894` — Integration alias OpenAPI omits handler error responses — https://github.com/GroepOnline/kater-dev-tools/issues/100
- P2/P3 `tests/test_connections_plugins.py` — Test gaps on landed connections/plugins surface — https://github.com/GroepOnline/kater-dev-tools/issues/101

## Failed

None — all 6 tickets filed via `gh`.

## No sink

None — GitHub Issues reachable.
