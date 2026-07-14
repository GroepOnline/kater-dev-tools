# Kater routed capability pools — vertical slice

Status: implemented in PR #108  
Linear: CHE-693  
Boundary: Kater capability fabric; not a model gateway and not Computer/Fleet

## What this actually ships

Kater can now expose one stable logical MCP tool name backed by multiple concrete
backend/tool/account candidates.

Example:

```text
web.search
├── exa-account-a → exa-a__web_search_exa
├── exa-account-b → exa-b__web_search_exa
└── exa-account-c → exa-c__web_search_exa
```

The agent sees `web.search`. Kater chooses the eligible candidate, invokes it,
records the decision, consumes quota, preserves context affinity, and falls back
only when the failure is infrastructure-level.

This is deliberately different from aliasing a model endpoint. The routed unit
is a Kater capability backed by an existing MCP backend/tool pair. Credentials
remain inside the existing backend or future credential broker and never enter
the routing store, decision object, telemetry event, or CLI output.

## End-to-end call path

```text
MCP client
  │ calls logical alias + optional _kater_route metadata
  ▼
ProxyManager.call_tool
  │
  ├─ direct prefixed tool? ───────────────► existing behavior, unchanged
  │
  └─ logical capability alias
       │
       ├─ load persistent candidate pool from SQLite
       ├─ reject unavailable or schema-incompatible candidates
       ├─ overlay live in-flight count and backend latency
       ├─ enforce state, cooldown, routing scopes, concurrency and every quota window
       ├─ preserve context affinity when the pinned account remains eligible
       ├─ rank deterministically by quota headroom, priority, capacity, cost, latency
       ├─ invoke backend/tool with routing metadata stripped
       ├─ fallback only for circuit/open/unavailable/unhealthy/transport failures
       ├─ never repeat a tool-level/business error on another backend
       ├─ consume quota on success
       ├─ place failed infrastructure candidate into bounded cooldown
       └─ persist + broadcast route_decision evidence
```

## Operator workflow

Route state is managed with the package entry point `kater-routes`. It uses the
same `.kater/kater.db` as Kater but separate `control_*` tables.

### Register candidates

```bash
kater-routes add web.search \
  --account exa-primary \
  --provider exa \
  --backend exa-primary \
  --tool web_search_exa \
  --scopes web.read \
  --priority 10 \
  --max-concurrent 4 \
  --cost-per-million 5.0 \
  --quota monthly:1000000:0

kater-routes add web.search \
  --account exa-secondary \
  --provider exa \
  --backend exa-secondary \
  --tool web_search_exa \
  --scopes web.read \
  --priority 20 \
  --max-concurrent 2 \
  --quota daily:2000:0
```

### Inspect and dry-run

```bash
kater-routes list --capability web.search
kater-routes dry-run web.search \
  --context CHE-693 \
  --scopes web.read \
  --estimated-units 1
kater-routes decisions --capability web.search --limit 50
```

### Invoke from MCP

The `_kater_route` envelope is optional and is removed before the concrete MCP
tool is called:

```json
{
  "query": "Utrecht open data",
  "_kater_route": {
    "context_id": "CHE-693",
    "required_scopes": ["web.read"],
    "estimated_units": 1
  }
}
```

Without the envelope, Kater uses context `mcp-default`, no additional routing
constraints, and one estimated unit.

`context_id` is currently an affinity/correlation key, not an authenticated
principal. `required_scopes` is a caller-supplied route-compatibility constraint,
not an authorization grant or policy decision. Authentication remains enforced by
Kater's existing auth gate. Policy-derived contexts and signed scoped tokens belong
to CHE-660/CHE-695; this slice does not claim to implement them.

## Persistence model

The vertical slice creates four SQLite tables:

| Table | Role |
|---|---|
| `control_route_candidates` | Logical capability → account/backend/tool metadata |
| `control_quota_windows` | Multiple quota windows per candidate |
| `control_routing_decisions` | Immutable attempt/outcome ledger |
| `control_route_affinity` | Context-scoped successful account pin |

Every mutation is transactional. SQLite uses WAL and a bounded busy timeout so
route decisions can coexist with the normal telemetry writer. Route
configuration survives gateway restart. Decision records contain capability,
context, candidate, concrete backend/tool, score, reasons, outcome and a bounded
redacted error summary. They do not contain arguments, responses, credentials
or environment values.

## Selection invariants

1. Disabled, active-cooldown and non-reset exhausted candidates are ineligible.
2. Every caller-requested routing scope must be present on the candidate; this is not authorization.
3. Candidate concurrency must have capacity.
4. Every quota window must admit `estimated_units`.
5. Reset windows behave as zero-used without requiring a cleanup job first.
6. Ranking is deterministic; account ID is the final tie-breaker.
7. Quota headroom intentionally outweighs small price and latency differences.
8. A successful account is pinned per capability/context while still eligible.
9. Infrastructure failure clears that affinity and applies cooldown.
10. Tool/business errors do not trigger fallback or poison infrastructure health.
11. Only candidates with an identical object-shaped MCP input schema may share an alias.
12. Logical aliases cannot contain `__`, which remains reserved for concrete prefixed tools.

## Failure classification

Fallback is allowed only when Kater itself can establish that the selected route
was not safely executed:

- circuit breaker open;
- backend absent;
- backend unhealthy;
- transport/backend invocation exception.

A normal backend result containing `error` is returned to the caller and not
replayed elsewhere. Repeated business or validation errors also do not open the
infrastructure circuit breaker for a logical pool. This is essential for
write-capabilities such as issue creation, deploys, merges and database mutations
where an upstream may have committed the action before returning an error.

## Existing surfaces that become live immediately

No parallel dashboard state or new undocumented REST island is introduced. The
slice feeds existing Kater surfaces:

- `tools/list`: includes logical aliases when a compatible concrete tool exists;
- MCP `tools/call`: performs real routing and bounded fallback;
- `/api/events` and `/api/telemetry`: include `route_decision` events;
- `/api/evals`: includes route success/fallback/failure totals;
- `/api/status`: includes persistent route/candidate/affinity/decision counts;
- WebSocket telemetry: broadcasts each routing attempt outcome.

The durable detail ledger remains queryable through `kater-routes decisions`.
A dedicated policy-scoped REST surface belongs in CHE-695, together with remote
contexts and signed scoped tokens, rather than being added prematurely here.

## Compatibility

- Existing `backend__tool` names and direct-call behavior remain unchanged.
- Logical aliases are additive and cannot shadow or imitate concrete prefixed names.
- Existing backend circuit breakers remain authoritative for direct tools.
- Logical pools classify business errors separately from infrastructure failures.
- No credential format, MCP transport, dashboard build or Computer/Fleet contract changes.
- Removing all route candidates restores pre-PR behavior without migration.

## Acceptance evidence

The focused suite proves:

- deterministic quota-aware eligibility and ranking;
- cooldown and reset recovery;
- persistent route and quota round-trip;
- logical alias publication through `tools/list`;
- non-object and schema-incompatible candidates excluded from publication and fallback;
- live fallback from a transport exception to a second backend;
- routing metadata removal before backend invocation;
- quota consumption only on success;
- failed candidate cooldown;
- context affinity and different-context rebalancing;
- no fallback/replay or circuit poisoning for repeated tool-level errors;
- reserved logical namespace and durable decision outcomes;
- canonical lifecycle validation.

## Explicitly deferred

- credential brokerage, policy grants and signed contexts: CHE-660/CHE-695;
- provider usage reconciliation and invoice-grade cost accounting: CHE-694;
- isolated connector process/container supervisor: CHE-661/CHE-696;
- A2A task protocol: CHE-697;
- repository/worktree/PR job resumability and intervention queue: CHE-698.

Those items now build on a real routing execution path instead of another set of
standalone domain objects.