# proxy/ — multi-backend MCP fan-out

## OVERVIEW
Turns the 29+ upstream MCP servers (from `profiles.py`) into `backend__tool_name` tools on Kater's MCP surface. Each backend is its own subprocess or HTTP client with health + circuit breaker.

## STRUCTURE
- manager.py    # ProxyManager singleton (get_proxy/reset_proxy); CircuitBreaker per backend; _create_backend factory
- base.py       # BaseBackend abstract; MCP session ceremony (initialize→notifications/initialized→tools/list); MockBackend for tests
- aggregator.py # name→(backend,original) router; prefixed_name="backend__tool"
- models.py     # ProxiedTool, BackendStatus (dashboard renders these)
- stdio_backend.py # subprocess Popen ND-JSON; _SAFE_ENV_PASSTHROUGH allow-list
- sse_backend.py   # legacy MCP SSE transport (discover endpoint event, POST JSON-RPC)
- streamable_http_backend.py # modern POST /mcp; mcp-session-id sticky

## WHERE TO LOOK
| Task | Location |
|------|----------|
| Add a transport | base.py (ceremony) + new backend module + manager._create_backend |
| Change health/circuit | manager.CircuitBreaker |
| Change tool naming | aggregator.py |

## CONVENTIONS
- `proxy/__init__` re-exports only ProxyManager/get_proxy/reset_proxy.
- `latency_ms` on BaseBackend is declared but never populated (always 0.0) — known gap.
- stdio backends get a curated env allow-list (PATH/HOME/LANG…); upstream can't read unrelated env.

## ANTI-PATTERNS
- Never let api/* import kater.proxy — proxy is MCP-only by design.
- Only runtime.start() and mcp_server.build_sse_app() call get_proxy().start(); both guard with try/except. get_proxy() is process-global.
