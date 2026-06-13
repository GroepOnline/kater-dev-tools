# Kater Dev MCP Gateway

## Problem Frame

This should be a separate dev-tooling repository, not part of the Utrecht Data OS
product runtime. The problem is agent ergonomics: code agents currently see too many
MCP tools by default, including broad dev MCPs such as GitHub, Linear, Exa, Firecrawl,
Hugging Face, Sanity, Sentry, Upstash, browser, Resend, Quiver, and plugin-provided
tools.

The goal is `kater`: one Docker-deployable dev MCP gateway that exposes curated
profiles, simple command wrappers, doctor/autofix checks, and optional tool chains.
Utrecht Data OS can be one adapter/profile, but the gateway itself is for developer
convenience now, not for end-user product delivery.

## Current State To Preserve

- Utrecht Data OS already has `utrecht mcp serve` and a container-hub sketch. Treat
  these as reference patterns and an optional adapter target, not the place where
  Kater is implemented.
- The current Cursor/project MCP setup shows the real tool list to support: project
  MCPs, plugin MCPs, remote MCPs, stdio MCPs, and per-project approval state.
- Dev tools must stay profile-gated so an agent doing a local code task does not get
  web, cloud, email, image, CMS, or infra tools unless the profile asks for them.
- The deploy target is Docker on a local machine or a self-managed server reachable
  over Tailscale/SSH. No Cloudflare track for this tranche.

## Key Decisions

- New repo: create a standalone repository such as `kater-dev-tools` or
  `kater-mcp-gateway`.
- Runtime: Docker Compose first. Supported targets are local Docker and one
  self-managed server. No Cloudflare in the initial plan.
- Scope: pure developer tooling. Do not optimize for Utrecht end users, public product
  APIs, or hosted product reliability.
- Default profile: very small, usually filesystem-safe diagnostics plus profile/doctor
  tools. All high-surface MCPs are opt-in by profile.
- Adapter model: wrap or route to external MCPs through named adapters and chains; do
  not blindly re-export every tool from every server.
- Autofix model: `doctor` reports, `doctor --fix-plan` emits a patch/action plan, and
  `doctor --apply --yes` performs explicit selected changes.
- Profiles: group by task intent, for example `core`, `code`, `ops`, `research`,
  `web`, `cloud`, `content`, `email`, `image`, `utrecht`.

## Implementation Units

### U1. Bootstrap Separate Repo

Create the standalone Kater repository and minimal Python project skeleton with CLI,
tests, Docker Compose, and an env example. Keep the first implementation small and
agent-friendly.

### U2. Inventory and Profile Model

Create a repo-owned inventory of known MCP/tool sources and classify each as
default-safe or profile-gated. Track source name, source type, transport, risk, env
requirements, profile tags, default enabled, and known context cost.

### U3. Doctor and Autofix

Add a doctor that reports context bloat and can optionally apply safe config changes.
Support `doctor --json`, `doctor --fix-plan --json`, and explicit
`doctor --apply --yes`.

### U4. Kater Native Gateway Layer

Build a small native gateway that can expose curated commands, simple tools, and
chains to agents. Provide native tools for profile listing, doctor, config rendering,
and safe command wrappers.

### U5. Docker-Hosted MCP Server

Expose Kater through one MCP endpoint running in Docker. Start with stdio internally
and bridge to HTTP/SSE via `mcp-proxy` where needed.

### U6. Local and Self-Managed Deploy

Provide local Docker Compose and self-managed Docker Compose recipes over
Tailscale/SSH. Cursor connects to Kater as one MCP server; Kater decides which tool
profile is active.

### U7. Utrecht Data OS Adapter

Add Utrecht Data OS as an optional profile/adapter without coupling Kater to the
product repo. Treat Utrecht as a configured external project via mounted repo path or
existing MCP endpoint.

## Verification

- Unit tests for profile classification, doctor output, autofix planning, registry,
  chains, and MCP exposure.
- Docker build and container smoke test.
- Manual Cursor smoke: connect to one Kater MCP endpoint and confirm the default tool
  list is small.
- Utrecht smoke only for the optional adapter/profile, not as a core product test.

## Deferred

- Editing global Cursor plugin cache files.
- Cloudflare deployment or edge hosting.
- Product-facing Utrecht Data OS runtime changes.
- Paid cloud resources.
