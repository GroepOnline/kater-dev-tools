# 2026-09-25 — Consolidate onto main

## Open PRs at start

| PR | Decision | Reason |
| --- | --- | --- |
| #122 artifact retention 7d | FOLD | Wanted; fold into ubuntu-latest foundation |
| #109 setup-uv 10.0.1→10.1.0 | FOLD | Dependabot minor; fold into foundation |
| #112 stamped runtime identity | MERGE | Still wanted; rebase after foundation, drop self-hosted commits |
| #120 python-minor-patch (mcp/playwright/ruff) | MERGE | Dependabot minor/patch; rebase after foundation if tests pass |

#116 already on main banned hosted runners. Repo is PUBLIC → restore `ubuntu-latest`.
`company-control-deploy` stays `[self-hosted, Linux, X64, company-control]` for bc-scan-arm.

## Foundation

Branch `cursor/ci-hosted-runners-fold-1cd5` folds #109 + #122 and reverts #116 for public jobs.
