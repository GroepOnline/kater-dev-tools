# Execution Foundation

Kater is ChefGroep's generic execution and integration gateway. It is not a
GitHub-PR product and not a second Commander or Factory.

## Plane split

| Component | Owns | Does not own |
| --- | --- | --- |
| **Kater** | Tools, integrations, connections/credentials, `execute`, policy, audit, retries | Agent runs, workflow graphs, fleet deploy, model routing |
| **ChefCommander** | Runs, agents, workflows, delegation, orchestration | Provider credentials and vendor SDKs |
| **ChefFactory** | Control-plane, deployment, configuration, governance, fleet | Per-action provider calls |
| **OCX** | Models, inference, provider routing | External SaaS credentials |
| **MCP / plugins / skills** | Interfaces that call Kater | Execution policy |

Credentials live on Kater connections. Tasks live in Commander. Deployment and
config live in Factory. Model keys and routes live in OCX.

## Canonical model

```text
toolkit → integration → connection → action
```

- **Toolkit** — agent-facing capability bundle (`ToolkitManifest`, GitHub first).
- **Integration** — provider adapter behind that toolkit (`IntegrationManifest` / `ConnectorRecord`).
- **Connection** — secret-free account/credential binding (`ConnectionView`).
- **Action** — one invocable operation (`github.pr.merge`, `linear.issues.create`).

`PluginManifest` groups toolkits. MCP is a transport, not the architecture.

## Execute contract

```text
kater.execute(connection, action, input, identity, policy_context)
```

Every call is schema-validated, timed, optionally retried, optionally
idempotent, identity-stamped (`actor_id` / `agent_id`), correlated
(`run_id` / `trace_id`), policy-checked, and written to the capability audit.

Dangerous writes (merge/delete/admin) use this policy layer. GitHub
reviewer / exact-head authority is one policy, not Kater's product purpose.

`kater_pr_*` tools are compatibility wrappers over `github.pr.*`.

## Surfaces

| Surface | Path |
| --- | --- |
| REST execute | `POST /api/execute` |
| REST connections | `GET /api/connections`, `GET /api/connections/{id}` |
| REST actions | `GET /api/actions` |
| MCP | `kater_execute`, `kater_tool_search` |
| CLI | `kater execute`, `kater connections`, `kater actions` |

Compatibility: `capability_id` / `arguments` still resolve to `action` / `input`.
