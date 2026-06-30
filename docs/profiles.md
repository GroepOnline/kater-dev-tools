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
| `image` | Image/vector generation | QuiverAI |
| `utrecht` | Utrecht Data OS adapter | Existing Utrecht MCP or CLI |

High-surface tools should stay out of `core`. Prefer selecting a profile per task.
