# Private deployment overlays

Kater is the OSS **gateway**. A private deployment overlay is an
out-of-tree Python package that contributes extra profiles, native tools,
chain definitions, and capability manifests to a running gateway without
forking the project.

## When to use an overlay

Use an overlay when:

- you need a stable set of MCP servers / tools / chains that aren't a fit
  for upstream OSS (internal services, vendor-specific adapters, or org-
  scoped policies);
- you want profiles hidden from default listings (`PRIVATE_PROFILES`,
  gated by `KATER_PUBLIC=1` mode);
- you ship capability manifests whose publisher your organisation owns and
  versioning you control.

Do **not** use an overlay to bypass `kater doctor` findings, to skip
authentication, or to mutate upstream behaviour from a code-agent session.

## Loading an overlay

```bash
export KATER_EXTENSIONS_MODULE=your_package.extensions
uv run kater server
```

The module exports the public surface described in
[`src/kater/extensions.py`](../../src/kater/extensions.py). At start-up
Kater imports the module and merges each optional export into the live
registry (alongside the OSS builtins):

| Export | Add to Kater |
|---|---|
| `TOOL_SOURCES` | Profile-gated MCP server catalogue entries |
| `PRIVATE_PROFILES` | Profile names hidden when `KATER_PUBLIC=1` |
| `NATIVE_TOOLS` | First-class native tools exposed to agents |
| `CHAINS` | Reusable tool-chain definitions |
| `CAPABILITIES` | `CapabilityManifest` entries for the manifest registry |

Invalid entries are skipped with a warning; the OSS gateway never crashes
on a malformed overlay.

## Governance

- Treat the overlay source as production code (reviewing, versioned
  deploys, signed release artefacts).
- The overlay runs in the same process as `kater serve` and can read the
  same environment, including secrets. Audit what the module imports at
  start-up.
- Trust the OSS security model in [`SECURITY.md`](../../SECURITY.md): the
  gateway still applies auth, CORS, rate limiting, and capability
  lifecycle gates to overlay-registered tools.

## Writing operator runbooks

If your org needs step-by-step deployment, onboarding, or recovery
instructions specific to its overlay, keep those docs in the overlay
package itself (or its `docs/` directory). The OSS repo only ships the
generic overlay pointer contract — it does not host org-specific
playbooks.
