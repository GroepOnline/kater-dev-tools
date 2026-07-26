# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/OnlineChefGroep/kater-dev-tools/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/OnlineChefGroep/kater-dev-tools/releases/tag/v1.0.0

## [Unreleased]

### Added

- OpenAPI paths for the native browser lane (`/api/browser/*`) and automations (`/api/automations/*`).
- `.env.example` knobs for optional browser providers, domain policy, and session limits.
- Deploy docs cover three-port layout (9090/9091/9092), `kater migrate apply` / `kater backup create`, and optional Playwright browser install.

### Changed

- Docker and Kubernetes deploy templates expose WebSocket port 9092, hint at a `/app/.kater` volume, and note optional Playwright for the browser lane.

### Fixed

- _Nothing yet._

## [1.0.0] - 2025-01-01

Initial public release.

### Added

- Industrial-brutalist web dashboard (`kater-control`) for live gateway inspection.
- Developer MCP gateway with profile-gated tools for code agents (Cursor, Claude, etc.).
- `kater` CLI entrypoints: `kater`, `kater-routes`, `kater-capabilities`.
- Pluggable transport backends: stdio, SSE, and streamable HTTP.
- OAuth-authenticated upstream proxies and tunnel/deploy helpers.
- PR-control view with race-safe DOM rendering and standard layout.
