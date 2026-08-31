# Kater Studio

Kater Studio is the optional React/Vite presentation client for the existing Python Kater runtime. Its agent-activity primitives are adapted from the MIT-licensed Brainless registry; the earlier Google AI Studio branch remains visual reference material only.

Rules:
- Python Kater remains authoritative for MCP, REST, auth, policy, telemetry and mutations.
- No fake telemetry or mock replacement backend in production code.
- Every visible UI concern is a component or reusable primitive.
- Copy, navigation, API base URL, feature flags and visual tokens are centralized and adjustable.
- The Studio can be replaced or rebuilt without changing the Kater agent hot path.

Development:

```bash
uv run npm --prefix studio ci
uv run npm --prefix studio run dev
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:9091` by default. `uv run npm --prefix studio run build` writes deterministic runtime assets into `src/kater/web/studio_dist/` for Python packaging.
