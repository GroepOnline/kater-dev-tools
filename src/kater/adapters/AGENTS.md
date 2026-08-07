# adapters/ — client-side MCP config rendering

## OVERVIEW
Produces the `mcpServers` JSON an EXTERNAL client (Cursor/Claude Desktop) pastes to talk to Kater. Reads profiles + settings; never spawns backends.

## STRUCTURE
- external.py  # McpAdapter inventory + render_profile_config (full JSON)
- __init__.py  # empty

## WHERE TO LOOK
| Task | Location |
|------|----------|
| Add adapter detection | external.py scan_adapters |
| Change client JSON shape | external.py render_profile_config |

## CONVENTIONS
- `scan_adapters(include_secrets=False)` default preserves `${VAR}` placeholders — secrets never cross the wire via REST.
- Consumed by api/routes `/api/adapters` and cli `config --profile X`.

## ANTI-PATTERNS
- Don't resolve secrets here for the REST surface — only the local CLI (operator) path may.
