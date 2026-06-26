from __future__ import annotations

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


TOOL_SOURCES: tuple[ToolSource, ...] = (
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
            args=["-y", "@modelcontextprotocol/server-github"],
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
            args=["-y", "@modelcontextprotocol/server-gitlab"],
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
            url="https://mcp.linear.app/sse",
            env_template={"LINEAR_API_KEY": "${LINEAR_API_KEY}"},
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
            args=["-y", "firecrawl-mcp"],
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
            args=["-y", "@cloudflare/mcp-server-cloudflare"],
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
            args=["-y", "@upstash/mcp-server"],
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
            args=["-y", "@anthropic-ai/mcp-server-playwright"],
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
            args=["-y", "resend-mcp"],
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
            args=["-y", "@modelcontextprotocol/server-slack"],
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
            args=["-y", "@anthropic-ai/mcp-server-figma"],
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
            args=["-y", "@modelcontextprotocol/server-postgres"],
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
            args=["-y", "@modelcontextprotocol/server-sqlite"],
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
            args=["-y", "@modelcontextprotocol/server-filesystem"],
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
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env_template={"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        ),
    ),
    # ── Specialized ─────────────────────────────────────────────────
    ToolSource(
        name="utrecht",
        description="Utrecht Data OS pipeline and agent adapter.",
        transport=Transport.SSE,
        risk=RiskLevel.LOW,
        profiles={"utrecht"},
        env=["UTRECHT_MCP_URL"],
        context_cost=2,
        homepage="https://utrecht-data-os.nl",
        mcp=McpServerConfig(
            url="${UTRECHT_MCP_URL}",
            env_template={"UTRECHT_MCP_URL": "${UTRECHT_MCP_URL}"},
        ),
    ),
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
            args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
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
            args=["-y", "@modelcontextprotocol/server-memory"],
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
            args=["-y", "@upstash/context7-mcp"],
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
            args=["-y", "deepwiki-mcp"],
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
            args=["-y", "@notionhq/notion-mcp-server"],
            env_template={
                "OPENAPI_MCP_HEADERS": (
                    '{"Authorization":"Bearer ${NOTION_API_KEY}",'
                    '"Notion-Version":"2022-06-28"}'
                )
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
            args=["-y", "@modelcontextprotocol/server-fetch"],
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
            args=["-y", "@modelcontextprotocol/server-time"],
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
            args=["-y", "@modelcontextprotocol/server-puppeteer"],
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
            args=["-y", "@modelcontextprotocol/server-everart"],
            env_template={"EVERART_API_KEY": "${EVERART_API_KEY}"},
        ),
    ),
)


def list_profiles() -> list[str]:
    profiles = {DEFAULT_PROFILE}
    for source in TOOL_SOURCES:
        profiles.update(source.profiles)
    return sorted(profiles)


def sources_for_profiles(profile_names: set[str]) -> list[ToolSource]:
    selected = []
    for source in TOOL_SOURCES:
        if source.default_enabled or source.profiles.intersection(profile_names):
            selected.append(source)
    return selected


def get_source(name: str) -> ToolSource | None:
    for source in TOOL_SOURCES:
        if source.name == name:
            return source
    return None
