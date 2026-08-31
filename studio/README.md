# Kater Studio

This is the salvaged Google AI Studio direction, rebuilt as an optional presentation client for the existing Python Kater runtime.

Rules:
- Python Kater remains authoritative for MCP, REST, auth, policy, telemetry and mutations.
- No fake telemetry or mock replacement backend in production code.
- Every visible UI concern is a component or reusable primitive.
- Copy, navigation, API base URL, feature flags and visual tokens are centralized and adjustable.
- The Studio can be replaced or rebuilt without changing the Kater agent hot path.

Development:

```bash
npm ci
npm run dev
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:9091` by default. `npm run build` writes deterministic runtime assets into `src/kater/web/studio_dist/` for Python packaging.
