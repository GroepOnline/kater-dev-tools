# Search and execute connector capabilities

Kater exposes two agent-facing tools for connector work:

- `kater_tool_search` finds registered capabilities for a task.
- `kater_execute` runs one capability through the connector's existing auth, profile permission, transport, and audit path.

Agents do not need every provider tool in their MCP context. They search the catalog first, then execute the selected capability.

```text
agent intent
-> kater_tool_search
-> connector capability
-> kater_execute
-> auth check
-> profile permission
-> connector transport
-> provider
-> capability audit
```

## Search for a capability

Use `kater_tool_search` or the CLI command:

```bash
kater search-tools "create a Linear issue" --profile ops
```

Search uses deterministic lexical ranking. By default, Kater returns only capabilities that the selected profile can execute. Set `include_unavailable` to inspect disabled, blocked, or under-permissioned matches.

A search result includes the connector id, capability id, input schema, mutation flag, required permission, granted permission, health state, and availability.

## Execute a capability

Pass the capability id returned by search:

```bash
kater execute linear.issues.create \
  --profile ops \
  --args '{"title":"Fix release gate"}'
```

`kater_execute` does not bypass connector rules. The existing connector registry still owns auth checks, read or write permission, connector state, and transport dispatch.

If more than one connector owns the same capability id, pass an explicit connector id. Kater rejects ambiguous execution instead of choosing one implicitly.

Every execution writes a capability-audit row with the capability id, principal, context id, outcome, duration, and profile. Kater records denied and failed calls as well as successful calls.

## Add a connector

Dynamic registration is the input path for new integrations:

```text
connector definition
-> register
-> validate and discover capabilities
-> bind auth by reference
-> grant a profile permission
-> enable
-> search
-> execute
```

The connector definition does not contain credential values. Auth remains an env, settings, or ChefVault reference.

## Runtime profile boundary

A running Kater instance accepts `core` plus the profiles configured in its own `KATER_PROFILE`. Search and execute reject a profile that the runtime does not serve.

## What this does not do yet

This layer executes one capability at a time. Kater chains remain the composition mechanism for multi-step work. A later change can compile a natural-language task into a chain of searched capabilities without changing the connector execution contract.
