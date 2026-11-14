from __future__ import annotations

import os
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Transport(StrEnum):
    NATIVE = "native"
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Category(StrEnum):
    DEV = "dev"
    CRM = "crm"
    COMMS = "comms"
    AI = "ai"
    DATA = "data"
    INFRA = "infra"
    PRODUCTIVITY = "productivity"


AuthScheme = Literal["api_key", "oauth2", "bearer", "none"]


class ToolRef(BaseModel):
    name: str
    description: str = ""


class TriggerRef(BaseModel):
    name: str
    description: str = ""
    cadence: Literal["realtime", "poll"] = "realtime"


class McpServerConfig(BaseModel):
    """How to actually launch/connect to this MCP server."""

    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env_template: dict[str, str] = Field(default_factory=dict)
    headers_template: dict[str, str] = Field(default_factory=dict)


class OAuthConnectConfig(BaseModel):
    """Outbound OAuth for the catalog Connect button (Kater as OAuth client)."""

    provider: str
    authorize_url: str
    token_url: str
    client_id_env: str
    client_secret_env: str = ""
    scopes: list[str] = Field(default_factory=list)
    pkce: bool = True
    token_env: str = "ACCESS_TOKEN"
    refresh_env: str = "REFRESH_TOKEN"
    resource: str | None = None
    extra_authorize: dict[str, str] = Field(default_factory=dict)


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
    oauth: OAuthConnectConfig | None = None
    category: Category = Category.DEV
    logo_url: str | None = None
    auth_schemes: list[AuthScheme] = Field(default_factory=list)
    toolkit_tools: list[ToolRef] = Field(default_factory=list)
    triggers: list[TriggerRef] = Field(default_factory=list)
    trigger_count: int = 0
    docs_url: str | None = None

    @model_validator(mode="after")
    def _infer_toolkit_defaults(self) -> ToolSource:
        name_category: dict[str, Category] = {
            "kater": Category.INFRA,
            "github": Category.DEV,
            "gitlab": Category.DEV,
            "linear": Category.PRODUCTIVITY,
            "sentry": Category.DATA,
            "exa": Category.DATA,
            "firecrawl": Category.DATA,
            "huggingface": Category.AI,
            "sanity": Category.PRODUCTIVITY,
            "cloudflare": Category.INFRA,
            "upstash": Category.INFRA,
            "browser": Category.DEV,
            "resend": Category.COMMS,
            "slack": Category.COMMS,
            "quiverai": Category.AI,
            "figma": Category.PRODUCTIVITY,
            "postgres": Category.DATA,
            "sqlite": Category.DATA,
            "filesystem": Category.DEV,
            "brave-search": Category.DATA,
            "sequential-thinking": Category.AI,
            "memory": Category.AI,
            "context7": Category.DEV,
            "deepwiki": Category.DEV,
            "notion": Category.PRODUCTIVITY,
            "fetch": Category.DEV,
            "time": Category.PRODUCTIVITY,
            "puppeteer": Category.DEV,
            "everart": Category.AI,
        }
        toolkit_map: dict[str, list[ToolRef]] = {
            "github": [
                ToolRef(name="create_issue", description="Create GitHub issue"),
                ToolRef(name="search_code", description="Search code"),
                ToolRef(name="get_pr", description="Get PR details"),
                ToolRef(name="list_repos", description="List repositories"),
            ],
            "gitlab": [
                ToolRef(name="create_mr", description="Create merge request"),
                ToolRef(name="list_issues", description="List issues"),
                ToolRef(name="get_pipeline", description="Get pipeline"),
                ToolRef(name="search_code", description="Search code"),
            ],
            "linear": [
                ToolRef(name="create_issue", description="Create Linear issue"),
                ToolRef(name="list_projects", description="List projects"),
                ToolRef(name="update_issue", description="Update issue"),
                ToolRef(name="search_issues", description="Search issues"),
            ],
            "sentry": [
                ToolRef(name="list_issues", description="List Sentry issues"),
                ToolRef(name="get_event", description="Get event"),
                ToolRef(name="list_releases", description="List releases"),
                ToolRef(name="search_events", description="Search events"),
            ],
            "exa": [
                ToolRef(name="web_search", description="Web search"),
                ToolRef(name="fetch_page", description="Fetch page"),
                ToolRef(name="crawl", description="Crawl site"),
                ToolRef(name="research", description="Research"),
            ],
            "firecrawl": [
                ToolRef(name="scrape", description="Scrape URL"),
                ToolRef(name="crawl", description="Crawl"),
                ToolRef(name="search", description="Search"),
                ToolRef(name="extract", description="Extract"),
            ],
            "huggingface": [
                ToolRef(name="search_models", description="Search models"),
                ToolRef(name="get_model", description="Get model"),
                ToolRef(name="list_datasets", description="List datasets"),
                ToolRef(name="search_papers", description="Search papers"),
            ],
            "sanity": [
                ToolRef(name="query", description="GROQ query"),
                ToolRef(name="create_doc", description="Create document"),
                ToolRef(name="patch_doc", description="Patch document"),
                ToolRef(name="list_datasets", description="List datasets"),
            ],
            "cloudflare": [
                ToolRef(name="list_workers", description="List workers"),
                ToolRef(name="get_zone", description="Get zone"),
                ToolRef(name="kv_get", description="KV get"),
                ToolRef(name="r2_list", description="R2 list"),
            ],
            "upstash": [
                ToolRef(name="redis_get", description="Redis get"),
                ToolRef(name="qstash_publish", description="Publish message"),
                ToolRef(name="create_db", description="Create DB"),
                ToolRef(name="list_backups", description="List backups"),
            ],
            "browser": [
                ToolRef(name="navigate", description="Navigate"),
                ToolRef(name="click", description="Click"),
                ToolRef(name="screenshot", description="Screenshot"),
                ToolRef(name="fill", description="Fill form"),
            ],
            "resend": [
                ToolRef(name="send_email", description="Send email"),
                ToolRef(name="list_contacts", description="List contacts"),
                ToolRef(name="create_broadcast", description="Create broadcast"),
                ToolRef(name="get_template", description="Get template"),
            ],
            "slack": [
                ToolRef(name="post_message", description="Post message"),
                ToolRef(name="list_channels", description="List channels"),
                ToolRef(name="search_messages", description="Search"),
                ToolRef(name="create_trigger", description="Trigger event"),
            ],
            "figma": [
                ToolRef(name="get_file", description="Get file"),
                ToolRef(name="get_components", description="Get components"),
                ToolRef(name="export_image", description="Export image"),
                ToolRef(name="list_projects", description="List projects"),
            ],
            "postgres": [
                ToolRef(name="query", description="SQL query"),
                ToolRef(name="list_tables", description="List tables"),
                ToolRef(name="describe", description="Describe"),
                ToolRef(name="insert", description="Insert"),
            ],
            "sqlite": [
                ToolRef(name="query", description="SQL query"),
                ToolRef(name="list_tables", description="List tables"),
                ToolRef(name="backup", description="Backup"),
                ToolRef(name="vacuum", description="Vacuum"),
            ],
            "notion": [
                ToolRef(name="query_db", description="Query DB"),
                ToolRef(name="create_page", description="Create page"),
                ToolRef(name="search", description="Search"),
                ToolRef(name="patch_page", description="Patch page"),
            ],
            "context7": [
                ToolRef(name="query_docs", description="Query docs"),
                ToolRef(name="resolve_lib", description="Resolve library"),
                ToolRef(name="search", description="Search"),
                ToolRef(name="fetch", description="Fetch"),
            ],
            "brave-search": [
                ToolRef(name="web_search", description="Web search"),
                ToolRef(name="news_search", description="News search"),
                ToolRef(name="image_search", description="Image search"),
                ToolRef(name="summarize", description="Summarize"),
            ],
            "sequential-thinking": [
                ToolRef(name="think", description="Think step"),
                ToolRef(name="plan", description="Plan"),
                ToolRef(name="reflect", description="Reflect"),
                ToolRef(name="conclude", description="Conclude"),
            ],
            "memory": [
                ToolRef(name="store", description="Store"),
                ToolRef(name="recall", description="Recall"),
                ToolRef(name="graph", description="Graph"),
                ToolRef(name="forget", description="Forget"),
            ],
            "fetch": [
                ToolRef(name="fetch", description="Fetch URL"),
                ToolRef(name="parse", description="Parse"),
                ToolRef(name="monitor", description="Monitor"),
                ToolRef(name="extract", description="Extract"),
            ],
            "time": [
                ToolRef(name="now", description="Current time"),
                ToolRef(name="convert", description="Convert TZ"),
                ToolRef(name="schedule", description="Schedule"),
                ToolRef(name="parse", description="Parse"),
            ],
            "puppeteer": [
                ToolRef(name="navigate", description="Navigate"),
                ToolRef(name="act", description="Act"),
                ToolRef(name="screenshot", description="Screenshot"),
                ToolRef(name="pdf", description="PDF"),
            ],
            "everart": [
                ToolRef(name="generate", description="Generate image"),
                ToolRef(name="transform", description="Transform"),
                ToolRef(name="list_models", description="List models"),
                ToolRef(name="upscale", description="Upscale"),
            ],
        }
        trigger_seed: dict[str, list[TriggerRef]] = {
            "github": [TriggerRef(
                name="GITHUB_PUSH_EVENT",
                description="Push to any watched repo",
                cadence="realtime",
            )],
            "slack": [TriggerRef(
                name="SLACK_MESSAGE_EVENT",
                description="New message in channel",
                cadence="realtime",
            )],
            "notion": [TriggerRef(
                name="NOTION_PAGE_UPDATED_EVENT",
                description="Page updated",
                cadence="realtime",
            )],
            "cloudflare": [TriggerRef(
                name="CLOUDFLARE_DEPLOY_EVENT",
                description="Worker deploy completed", cadence="realtime",
            )],
            "upstash": [TriggerRef(
                name="UPSTASH_REDIS_TICK_EVENT",
                description="Polled Redis change",
                cadence="poll",
            )],
        }
        if self.category == Category.DEV and self.name in name_category:
            self.category = name_category[self.name]
        if not self.auth_schemes or self.auth_schemes == ["none"]:
            if self.oauth:
                self.auth_schemes = ["oauth2"]
            elif self.env:
                has_bearer = bool(
                    self.mcp
                    and self.mcp.headers_template
                    and any("Bearer" in v for v in self.mcp.headers_template.values())
                )
                self.auth_schemes = ["bearer" if has_bearer else "api_key"]
            else:
                self.auth_schemes = ["none"]
        if not self.toolkit_tools and self.name in toolkit_map:
            self.toolkit_tools = toolkit_map[self.name]
        if not self.triggers and self.name in trigger_seed:
            self.triggers = trigger_seed[self.name]
        if self.trigger_count == 0:
            self.trigger_count = len(self.triggers)
        if not self.docs_url and self.homepage:
            self.docs_url = self.homepage
        if not self.logo_url and self.name:
            self.logo_url = f"/studio/assets/logos/{self.name}.svg"
        return self


DEFAULT_PROFILE = "core"

GITHUB_MCP_VERSION = "2025.4.8"
GITLAB_MCP_VERSION = "2025.4.25"
FIRECRAWL_MCP_VERSION = "3.22.1"
UPSTASH_MCP_VERSION = "0.2.3"
PLAYWRIGHT_MCP_VERSION = "0.0.76"
RESEND_MCP_VERSION = "2.9.0"
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
            # Remote HTTP/SSE backends use headers_template only; env_template is not sent.
            headers_template={"Authorization": "Bearer ${SENTRY_AUTH_TOKEN}"},
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
        transport=Transport.HTTP,
        risk=RiskLevel.HIGH,
        profiles={"cloud", "ops"},
        env=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
        context_cost=4,
        homepage="https://developers.cloudflare.com",
        # Remote HTTP uses Authorization header only; do not use npx OAuth stdio.
        mcp=McpServerConfig(
            url="https://mcp.cloudflare.com/mcp",
            headers_template={"Authorization": "Bearer ${CLOUDFLARE_API_TOKEN}"},
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
        description=(
            "Slack workspace via Slack-hosted MCP. Connect signs in with your "
            "Slack account (user OAuth). Multiple workspaces are allowed."
        ),
        transport=Transport.HTTP,
        risk=RiskLevel.HIGH,
        profiles={"email", "ops"},
        env=["SLACK_ACCESS_TOKEN"],
        context_cost=4,
        homepage="https://mcp.slack.com/mcp",
        oauth=OAuthConnectConfig(
            provider="slack",
            authorize_url="https://slack.com/oauth/v2_user/authorize",
            token_url="https://slack.com/api/oauth.v2.user.access",
            client_id_env="SLACK_MCP_CLIENT_ID",
            client_secret_env="SLACK_MCP_CLIENT_SECRET",
            pkce=True,
            token_env="SLACK_ACCESS_TOKEN",
            refresh_env="SLACK_REFRESH_TOKEN",
            resource="https://mcp.slack.com/mcp",
        ),
        mcp=McpServerConfig(
            url="https://mcp.slack.com/mcp",
            headers_template={"Authorization": "Bearer ${SLACK_ACCESS_TOKEN}"},
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
            env_template={"OPENAPI_MCP_HEADERS": '{"Authorization":"Bearer ${NOTION_API_KEY}"}'},
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

    extra = tuple(extension_attr("TOOL_SOURCES", ()))
    by_name = {source.name: source for source in _BUILTIN_TOOL_SOURCES}
    order = [source.name for source in _BUILTIN_TOOL_SOURCES]
    for source in extra:
        if source.name not in by_name:
            order.append(source.name)
        by_name[source.name] = source
    return tuple(by_name[name] for name in order)


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


def get_triggers(name: str) -> list[TriggerRef]:
     for src in visible_tool_sources():
         if src.name == name:
             return list(src.triggers)
     return []
