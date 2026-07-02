from __future__ import annotations

import os
from enum import StrEnum

from pydantic import BaseModel, Field


class Transport(StrEnum):
    NATIVE = "native"
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class McpServerConfig(BaseModel):
    """How to actually launch/connect to this MCP server."""

    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env_template: dict[str, str] = Field(default_factory=dict)
    headers_template: dict[str, str] = Field(default_factory=dict)


class ToolSource(BaseModel):
    name: str
    description: str
    transport: Transport
    risk: RiskLevel
    profiles: set[str] = Field(default_factory=set)
    env: list[str] = Field(default_factory=list)
    default_enabled: bool = False
    context_cost: int = 1
    mcp: McpServerConfig | None = None
    homepage: str | None = None


DEFAULT_PROFILE = "core"

GITHUB_MCP_VERSION = "2025.4.8"
GITLAB_MCP_VERSION = "2025.4.25"
FIRECRAWL_MCP_VERSION = "3.22.1"
CLOUDFLARE_MCP_VERSION = "0.2.0"
UPSTASH_MCP_VERSION = "0.2.3"
PLAYWRIGHT_MCP_VERSION = "0.0.76"
RESEND_MCP_VERSION = "2.9.0"
SLACK_MCP_VERSION = "2025.4.25"
FIGMA_MCP_VERSION = "0.13.2"
POSTGRES_MCP_VERSION = "0.6.2"
SQLITE_MCP_VERSION = "0.8.0"
FILESYSTEM_MCP_VERSION = "2026.1.14"
BRAVE_SEARCH_MCP_VERSION = "0.6.2"
SEQUENTIAL_THINKING_MCP_VERSION = "2025.12.18"
MEMORY_MCP_VERSION = "2026.1.26"
CONTEXT7_MCP_VERSION = "3.2.2"
DEEPWIKI_MCP_VERSION = "0.0.6"
NOTION_MCP_VERSION = "2.4.1"
FETCH_MCP_VERSION = "0.1.1"
TIME_MCP_VERSION = "1.0.0"
PUPPETEER_MCP_VERSION = "2025.5.12"
EVERART_MCP_VERSION = "0.6.2"


_BUILTIN_TOOL_SOURCES: tuple[ToolSource, ...] = (
    # ── Native ──────────────────────────────────────────────────────
    ToolSource(
        name="kater",
        description="Native Kater gateway: profiles, doctor, chains, config, adapters.",
        transport=Transport.NATIVE,
        risk=RiskLevel.LOW,
        profiles={"core"},
        default_enabled=True,
    ),
    # ── Code / VCS ──────────────────────────────────────────────────
    ToolSource(
        name="github",
        description="GitHub PR, issue, code search, and CI operations.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"ops", "code"},
        env=["GITHUB_PERSONAL_ACCESS_TOKEN"],
        context_cost=4,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-github@{GITHUB_MCP_VERSION}"],
            env_template={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"},
        ),
    ),
    ToolSource(
        name="gitlab",
        description="GitLab merge requests, issues, and pipelines.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"ops", "code"},
        env=["GITLAB_PERSONAL_ACCESS_TOKEN"],
        context_cost=4,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-gitlab@{GITLAB_MCP_VERSION}"],
            env_template={"GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}"},
        ),
    ),
    # ── Ops / Ticketing ─────────────────────────────────────────────
    ToolSource(
        name="linear",
        description="Linear issue and project operations.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"ops"},
        env=["LINEAR_API_KEY"],
        context_cost=3,
        homepage="https://linear.app",
        mcp=McpServerConfig(
            url="https://mcp.linear.app/mcp",
            headers_template={"Authorization": "Bearer ${LINEAR_API_KEY}"},
        ),
    ),
    ToolSource(
        name="sentry",
        description="Sentry issue, release, and observability tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"ops"},
        env=["SENTRY_AUTH_TOKEN"],
        context_cost=3,
        homepage="https://sentry.io",
        mcp=McpServerConfig(
            url="https://mcp.sentry.dev/sse",
            env_template={"SENTRY_AUTH_TOKEN": "${SENTRY_AUTH_TOKEN}"},
        ),
    ),
    # ── Research / Web ──────────────────────────────────────────────
    ToolSource(
        name="exa",
        description="Exa web search and page fetch tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"research", "web"},
        env=["EXA_API_KEY"],
        context_cost=3,
        homepage="https://exa.ai",
        mcp=McpServerConfig(
            url="https://mcp.exa.ai/sse",
            env_template={"EXA_API_KEY": "${EXA_API_KEY}"},
        ),
    ),
    ToolSource(
        name="firecrawl",
        description="Firecrawl web search, scrape, crawl, and extraction.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"research", "web"},
        env=["FIRECRAWL_API_KEY"],
        context_cost=5,
        homepage="https://firecrawl.dev",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"firecrawl-mcp@{FIRECRAWL_MCP_VERSION}"],
            env_template={"FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"},
        ),
    ),
    ToolSource(
        name="huggingface",
        description="Hugging Face models, datasets, papers, and spaces.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"research", "cloud"},
        env=["HF_TOKEN"],
        context_cost=5,
        homepage="https://huggingface.co",
        mcp=McpServerConfig(
            url="https://huggingface.co/mcp/sse",
            env_template={"HF_TOKEN": "${HF_TOKEN}"},
        ),
    ),
    # ── Content / CMS ───────────────────────────────────────────────
    ToolSource(
        name="sanity",
        description="Sanity CMS content management and query tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.HIGH,
        profiles={"content"},
        env=["SANITY_API_TOKEN"],
        context_cost=3,
        homepage="https://sanity.io",
        mcp=McpServerConfig(
            url="https://mcp.sanity.io/sse",
            env_template={"SANITY_API_TOKEN": "${SANITY_API_TOKEN}"},
        ),
    ),
    # ── Cloud / Infra ───────────────────────────────────────────────
    ToolSource(
        name="cloudflare",
        description="Cloudflare Workers, R2, D1, KV, Durable Objects, and DNS tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"cloud", "ops"},
        env=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
        context_cost=4,
        homepage="https://developers.cloudflare.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@cloudflare/mcp-server-cloudflare@{CLOUDFLARE_MCP_VERSION}"],
            env_template={
                "CLOUDFLARE_ACCOUNT_ID": "${CLOUDFLARE_ACCOUNT_ID}",
                "CLOUDFLARE_API_TOKEN": "${CLOUDFLARE_API_TOKEN}",
            },
        ),
    ),
    ToolSource(
        name="upstash",
        description="Upstash Redis, QStash, Workflow, and Box management.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"cloud", "ops"},
        env=["UPSTASH_EMAIL", "UPSTASH_API_KEY"],
        context_cost=3,
        homepage="https://upstash.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@upstash/mcp-server@{UPSTASH_MCP_VERSION}"],
            env_template={
                "UPSTASH_EMAIL": "${UPSTASH_EMAIL}",
                "UPSTASH_API_KEY": "${UPSTASH_API_KEY}",
            },
        ),
    ),
    # ── Browser / Automation ────────────────────────────────────────
    ToolSource(
        name="browser",
        description="Playwright browser automation and scraping tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"web"},
        context_cost=4,
        homepage="https://playwright.dev",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}"],
        ),
    ),
    # ── Communication ───────────────────────────────────────────────
    ToolSource(
        name="resend",
        description="Resend email, contacts, broadcasts, and templates.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"email", "content"},
        env=["RESEND_API_KEY"],
        context_cost=5,
        homepage="https://resend.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"resend-mcp@{RESEND_MCP_VERSION}"],
            env_template={"RESEND_API_KEY": "${RESEND_API_KEY}"},
        ),
    ),
    ToolSource(
        name="slack",
        description="Slack messaging, channels, and workspace tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"email", "ops"},
        env=["SLACK_BOT_TOKEN"],
        context_cost=4,
        homepage="https://slack.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-slack@{SLACK_MCP_VERSION}"],
            env_template={"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
        ),
    ),
    # ── Image / Design ──────────────────────────────────────────────
    ToolSource(
        name="quiverai",
        description="QuiverAI SVG generation and asset tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"image"},
        context_cost=3,
        homepage="https://quiver.ai",
        mcp=McpServerConfig(
            url="https://mcp.quiver.ai/sse",
        ),
    ),
    ToolSource(
        name="figma",
        description="Figma design file access and dev-mode tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"image", "content"},
        env=["FIGMA_API_KEY"],
        context_cost=3,
        homepage="https://figma.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"figma-developer-mcp@{FIGMA_MCP_VERSION}"],
            env_template={"FIGMA_API_KEY": "${FIGMA_API_KEY}"},
        ),
    ),
    # ── Database / Storage ──────────────────────────────────────────
    ToolSource(
        name="postgres",
        description="PostgreSQL query and schema tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"cloud", "ops"},
        env=["DATABASE_URL"],
        context_cost=3,
        homepage="https://postgresql.org",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-postgres@{POSTGRES_MCP_VERSION}"],
            env_template={"DATABASE_URL": "${DATABASE_URL}"},
        ),
    ),
    ToolSource(
        name="sqlite",
        description="SQLite local database query tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"code"},
        context_cost=2,
        homepage="https://sqlite.org",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"mcp-server-sqlite-npx@{SQLITE_MCP_VERSION}"],
        ),
    ),
    # ── Filesystem / Search ─────────────────────────────────────────
    ToolSource(
        name="filesystem",
        description="Local filesystem read/write/search tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"code"},
        context_cost=2,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-filesystem@{FILESYSTEM_MCP_VERSION}"],
        ),
    ),
    ToolSource(
        name="brave-search",
        description="Brave Search web search tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"research", "web"},
        env=["BRAVE_API_KEY"],
        context_cost=2,
        homepage="https://brave.com/search",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-brave-search@{BRAVE_SEARCH_MCP_VERSION}"],
            env_template={"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        ),
    ),
    # ── Specialized ─────────────────────────────────────────────────
    ToolSource(
        name="sequential-thinking",
        description="Sequential reasoning and thought-chain tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"reasoning", "research"},
        context_cost=1,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=[
                "-y",
                f"@modelcontextprotocol/server-sequential-thinking@{SEQUENTIAL_THINKING_MCP_VERSION}",
            ],
        ),
    ),
    ToolSource(
        name="memory",
        description="Persistent knowledge graph and memory tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"reasoning"},
        context_cost=1,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-memory@{MEMORY_MCP_VERSION}"],
        ),
    ),
    # ── Documentation / Knowledge ───────────────────────────────────
    ToolSource(
        name="context7",
        description="Context7: up-to-date docs for any library or framework.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"code", "research", "docs"},
        context_cost=2,
        homepage="https://context7.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@upstash/context7-mcp@{CONTEXT7_MCP_VERSION}"],
        ),
    ),
    ToolSource(
        name="deepwiki",
        description="DeepWiki: AI-powered repository documentation and Q&A.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"code", "research", "docs"},
        context_cost=2,
        homepage="https://deepwiki.com",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"deepwiki-mcp@{DEEPWIKI_MCP_VERSION}"],
        ),
    ),
    ToolSource(
        name="notion",
        description="Notion pages, databases, and workspace search.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"content", "ops"},
        env=["NOTION_API_KEY"],
        context_cost=3,
        homepage="https://notion.so",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@notionhq/notion-mcp-server@{NOTION_MCP_VERSION}"],
            env_template={
                "OPENAPI_MCP_HEADERS": '{"Authorization":"Bearer ${NOTION_API_KEY}"}'
            },
        ),
    ),
    ToolSource(
        name="fetch",
        description="Lightweight fetch/convert URLs to markdown.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"research", "web"},
        context_cost=1,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"mcp-server-fetch-typescript@{FETCH_MCP_VERSION}"],
        ),
    ),
    ToolSource(
        name="time",
        description="Timezone conversion and current time tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.LOW,
        profiles={"utils"},
        context_cost=1,
        homepage="https://github.com/modelcontextprotocol/servers",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@guanxiong/mcp-server-time@{TIME_MCP_VERSION}"],
        ),
    ),
    ToolSource(
        name="puppeteer",
        description="Browser automation via Puppeteer for scraping/interaction.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"web"},
        context_cost=4,
        homepage="https://pptr.dev",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-puppeteer@{PUPPETEER_MCP_VERSION}"],
        ),
    ),
    ToolSource(
        name="everart",
        description="EverArt AI image generation tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"image"},
        env=["EVERART_API_KEY"],
        context_cost=3,
        homepage="https://everart.ai",
        mcp=McpServerConfig(
            command="npx",
            args=["-y", f"@modelcontextprotocol/server-everart@{EVERART_MCP_VERSION}"],
            env_template={"EVERART_API_KEY": "${EVERART_API_KEY}"},
        ),
    ),
)


def all_tool_sources() -> tuple[ToolSource, ...]:
    from kater.extensions import extension_attr

    extra = extension_attr("TOOL_SOURCES", ())
    return _BUILTIN_TOOL_SOURCES + tuple(extra)


# Back-compat alias for code/tests that expect the builtin catalog only.
TOOL_SOURCES = _BUILTIN_TOOL_SOURCES


# Private deployment extensions may register profile names via
# KATER_EXTENSIONS_MODULE (see kater.extensions). Those profiles are hidden
# from every public-facing surface when KATER_PUBLIC=1.
def _private_profiles() -> frozenset[str]:
    from kater.extensions import extension_attr

    return frozenset(extension_attr("PRIVATE_PROFILES", ()))


def is_public_mode() -> bool:
    # Match the same truthy set as settings._env_truthy (1/true/yes/on) so a
    # public deployment declared with KATER_PUBLIC=true hides private sources
    # too — previously only the literal "1" did, splitting visibility from the
    # secure-defaults path.
    return os.environ.get("KATER_PUBLIC", "").strip().lower() in {"1", "true", "yes", "on"}


def is_private_profile(profile: str) -> bool:
    return profile in _private_profiles()


def is_private_source(source: ToolSource) -> bool:
    private = _private_profiles()
    return bool(source.profiles) and source.profiles.issubset(private)


def visible_tool_sources() -> tuple[ToolSource, ...]:
    """Tool sources for public-facing listings (hides private ones when public)."""
    if not is_public_mode():
        return all_tool_sources()
    return tuple(s for s in all_tool_sources() if not is_private_source(s))


def list_profiles() -> list[str]:
    profiles = {DEFAULT_PROFILE}
    for source in visible_tool_sources():
        profiles.update(source.profiles)
    if is_public_mode():
        profiles -= _private_profiles()
    return sorted(profiles)


def sources_for_profiles(profile_names: set[str]) -> list[ToolSource]:
    selected = []
    for source in all_tool_sources():
        if source.default_enabled or source.profiles.intersection(profile_names):
            selected.append(source)
    return selected


def get_source(name: str) -> ToolSource | None:
    for source in all_tool_sources():
        if source.name == name:
            return source
    return None
