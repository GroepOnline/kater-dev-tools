# Utrecht Data OS Adapter

The Utrecht adapter is optional and external. Kater should not import Utrecht Data
OS code directly.

Configure one of:

```bash
UTRECHT_MCP_URL=http://100.65.83.86:9090/sse
UTRECHT_REPO_PATH=/path/to/your/utrecht-data-os
UTRECHT_FLEET_INVENTORY_PATH=/path/to/your/utrecht-fleet/inventory/fleet.json
```

Use the `utrecht` profile only when the task needs Utrecht-specific tools.

`UTRECHT_FLEET_INVENTORY_PATH` must point at the safe export from
`OnlineChefGroep/utrecht-fleet`. Kater validates that export before exposing it
through `utrecht_fleet_inventory`:

- `source` must be `utrecht-fleet`.
- `privacy.contains_host_private_data` must be `false`.
- Nodes may contain only safe display fields such as `hostname`, `role`,
  `status`, `source`, `cpu`, `ram`, and `last_seen`.
- IP addresses, SSH aliases/users, tokens, private keys, URLs, and email-shaped
  private text are rejected.

This keeps the MCP surface useful for fleet overview while preserving the
private tailnet boundary.
