# Third-party frontend components

Kater Studio vendors selected UI primitives from **brainless** by Ben Swerdlow.

- Upstream: `https://github.com/theswerd/brainless`
- Imported upstream commit: `4c5d5ab65ff6cfa8dbb6f27cb8c88d9092a48deb`
- License: MIT (`BRainless-LICENSE.txt`)
- Imported family in this change: Codex header, message, and exec components. The upstream working timer is intentionally excluded by Kater's no-client-runtime-timers contract.

The components are adapted only at their import boundary so they can live inside the existing Kater Vite/React runtime. Kater's Python control plane remains authoritative.
