# Profiles

Kater profiles keep code-agent tool context scoped to the current task.

## Default

`core` is the default. It exposes only Kater-native diagnostics and profile tools.

## Optional Profiles

| Profile | Purpose | Typical tools |
|---|---|---|
| `code` | Source-control and code workflow | GitHub |
| `ops` | PRs, issues, observability, infra | GitHub, Linear, Sentry, Upstash |
| `research` | Web and model/dataset research | Exa, Firecrawl, Hugging Face |
| `web` | Browser and web extraction | Browser, Exa, Firecrawl |
| `cloud` | Cloud-ish dev support | Hugging Face, Upstash |
| `content` | CMS and publishing | Sanity, Notion, Resend |
| `email` | Email operations | Resend |
| `image` | Image/vector generation | QuiverAI, Figma, EverArt |
| `reasoning` | Thought chains and memory | sequential-thinking, memory |
| `docs` | Library and repo documentation | context7, deepwiki |
| `utils` | Small utility tools | time |

Private/org-specific profiles can be added via `KATER_EXTENSIONS_MODULE` (see `src/kater/extensions.py`).

See the README MCP catalog table for the full server-to-profile mapping.

High-surface tools should stay out of `core`. Prefer selecting a profile per task.
