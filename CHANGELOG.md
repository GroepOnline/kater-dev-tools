# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/OnlineChefGroep/kater-dev-tools/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/OnlineChefGroep/kater-dev-tools/releases/tag/v1.0.0

## [Unreleased]

### Added

- Shared agent-taste registry: `.agents/registry/taste.yaml` + overlays +
  `generate-taste.py` (cmd / Cursor / Claude Code artefacts)
- Decision boundary: UI-taste stays in design-system; agent-taste lives here
- Signals + eval gate: `signals.yaml`, `taste-signal.py`, `eval-score.py --gate`,
  thresholds/scorecard, CI job + nightly `agent-taste-eval.yml` (artefact only)
- Fleet runner `scripts/run-taste-brain-eval.sh` + systemd timer templates under
  `infra/` (not for laptop)

### Changed

- _Nothing yet._

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
