# Private Cursor overlay (deployment repo)

Public OSS **kater-dev-tools** ships generic Cursor skills/agents under `.cursor/`
that must pass `scripts/no_org_leak.py` (no org GitHub handle or production
domain outside the attribution allowlist).

Org-pinned variants — for example a PR gate skill that hardcodes the deployment
repo slug — belong in the **private deployment overlay** named in
[`SPLIT_DECISION.md`](../../SPLIT_DECISION.md), not in this public tree. The
overlay repo slug is deliberately not spelled out here: `scripts/no_org_leak.py`
treats it as a private data-plane reference outside the audit allowlist.

## Layout in the private overlay repo

```text
<private-deployment-repo>/
  .cursor/
    skills/kater-pr-gate/SKILL.md   # org-pinned; may reference deployment repo
    agents/kater-pr-gate.md
```

Copy from the generic OSS `.cursor/skills/pr-gate/` and `.cursor/agents/pr-gate.md`,
then pin `repo:` to the deployment remote. Do **not** copy those org-pinned files
back into kater-dev-tools — CI `no-org-leak` will fail.

## Local guard

Install pre-commit hooks so org leaks are caught before push:

```bash
uvx pre-commit install
uvx pre-commit run no-org-leak --all-files
uvx pre-commit run cursor-index --all-files
```

For the full local / desktop / Cloud verify matrix (gateway, dashboard, smoke vs
e2e, hook koppelingen), see [local-desktop-verify.md](./local-desktop-verify.md).
