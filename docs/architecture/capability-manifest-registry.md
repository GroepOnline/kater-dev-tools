# Capability manifest registry (CHE-659)

Status: foundation slice  
Linear: CHE-659 (see the project tracker)
Boundary: Kater capability fabric; not credential/policy authority and not connector runtime

## What it is

Kater’s capability package model: a **stable logical capability ID** plus versioned
manifest metadata (publisher, digest, transport, schemas, scopes, risk class,
lifecycle, health/rollback hints). Manifests live in an in-memory registry for
process-local discovery/invocation checks and in SQLite (`control_capabilities`
in `.kater/kater.db`) for durable operator state.

Operators manage manifests with `kater-capabilities` (wired by the package entry
point once the coordinator registers it). Discovery compiles a **minimal** set
for a task/profile/risk/tag context; that set is a convenience, not a grant.

## Coexistence with `kater-routes` and `backend__tool`

| Surface | Role |
|---|---|
| `backend__tool` | Concrete prefixed MCP tool names; `__` reserved |
| `kater-routes` (CHE-693) | Logical alias → account/backend/tool **pools**, quota, affinity, fallback |
| Capability manifests (CHE-659) | Package identity, risk/lifecycle, schemas, discovery filters |

Logical capability IDs **must not** contain `__`. Route pools and manifests share
the same logical ID space (e.g. `web.search`) but different tables and concerns:
routing picks *which account/backend* to call; the manifest registry decides
*whether the capability exists, is discoverable, and is invocable* under
lifecycle rules.

## Discovery vs invocation

- **Discovery** (`discover(DiscoveryContext)`) filters active/canary manifests by
  profile, max risk, scopes, tags, optional intent boost, and healthcheck
  invocability. Output includes schemas and `approval_expected` hints.
- **Invocation** always rechecks independently (`assert_invocable` /
  `CapabilityRegistry.is_invocable`). A capability omitted from discovery or
  moved to `deprecated`/`revoked` is refused on direct call when managed.

Unmanaged IDs (not present in the registry) remain callable for backward
compatibility with today’s concrete tools until they are enrolled.

## Extension hook `CAPABILITIES`

Optional deployment extensions (`KATER_EXTENSIONS_MODULE`) may export
`CAPABILITIES`: a sequence of `CapabilityManifest` values merged into the
default registry at bootstrap (alongside builtins). Invalid entries are skipped
with a warning. This is the out-of-band path for domain packages (e.g. UDO)
without mutating the live gateway from an agent session.

## Unmanaged vs managed capabilities

| Kind | Registry membership | Discovery | Direct invoke |
|---|---|---|---|
| **Unmanaged** | Absent | Not listed | Allowed (`is_invocable` → unmanaged) |
| **Managed** | Present | Only active/canary (+ filters) | Only active/canary; otherwise denied |

Persisted lifecycle overlays from `control_capabilities` re-apply on registry
bootstrap so operator `set-lifecycle` survives restart for already-registered
IDs. Full custom manifests should be re-registered (CLI/extensions) or loaded by
a later bootstrap path.

## Follow-ons

- **CHE-660** — credential broker, policy engine, approvals and audit (discovery
  hints become enforceable grants; invocation pipeline stages).
- **CHE-664** — package Utrecht Data OS as a Kater domain extension (manifests +
  `CAPABILITIES` / package install path).

Related: CHE-661 connector canary/rollback runtime; CHE-695 context-scoped
tokens; CHE-693 route pools for multi-account fallback behind a logical ID.
