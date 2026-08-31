# Kater Studio architecture

## Authority split

The Google AI Studio branch is visual/interaction source material only. It must never replace Kater's Python runtime. Python remains authoritative for MCP, REST, authentication, policy, telemetry, storage, browser actions, automations and PR control.

Studio is an optional client. Its first migration slice uses the existing `/api/status` and `/api/catalog` endpoints directly. No demo telemetry, random latency, fake PRs or duplicate Node backend is allowed.

## Frontend contract

Every visible concern is a component or reusable primitive. Pages compose those components. Product copy, navigation, feature switches and endpoint roots live in `src/config.ts`; visual values live in `src/styles/tokens.css`. Components consume configuration and tokens instead of embedding product-wide constants.

Current primitives include `Sidebar`, `Topbar`, `StatusPill`, `MetricCard` and `IntegrationCard`. Current views are `IntegrationsView`, `ControlRoomView` and the migration placeholder used for functionality that still lives in the existing dashboard.

## Migration rule

Move one existing capability at a time from the embedded dashboard to Studio, bind it to the real Kater API, add a real-data empty/error state, then verify it before moving the next capability. The old dashboard remains the fallback until feature parity is proven.

## Source branch warning

`feat/scaffold-project-core-integration-types` contains useful Google AI Studio design work but also deletes the Python core and introduces a mock Express runtime. Never merge that branch wholesale. Salvage presentation ideas only.
