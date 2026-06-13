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


class ToolSource(BaseModel):
    name: str
    description: str
    transport: Transport
    risk: RiskLevel
    profiles: set[str] = Field(default_factory=set)
    env: list[str] = Field(default_factory=list)
    default_enabled: bool = False
    context_cost: int = 1


DEFAULT_PROFILE = "core"


TOOL_SOURCES: tuple[ToolSource, ...] = (
    ToolSource(
        name="kater",
        description="Native Kater profile, doctor, fix-plan, and chain tools.",
        transport=Transport.NATIVE,
        risk=RiskLevel.LOW,
        profiles={"core"},
        default_enabled=True,
    ),
    ToolSource(
        name="github",
        description="GitHub PR, issue, code search, and CI operations.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"ops", "code"},
        env=["GITHUB_PERSONAL_ACCESS_TOKEN"],
        context_cost=4,
    ),
    ToolSource(
        name="linear",
        description="Linear issue and project operations.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"ops"},
        env=["LINEAR_API_KEY"],
        context_cost=3,
    ),
    ToolSource(
        name="exa",
        description="Web research and page fetch tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"research", "web"},
        env=["EXA_API_KEY"],
        context_cost=3,
    ),
    ToolSource(
        name="firecrawl",
        description="Web search, scrape, crawl, and extraction tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"research", "web"},
        env=["FIRECRAWL_API_KEY"],
        context_cost=5,
    ),
    ToolSource(
        name="huggingface",
        description="Hugging Face models, datasets, papers, and spaces.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"research", "cloud"},
        env=["HF_TOKEN"],
        context_cost=5,
    ),
    ToolSource(
        name="sanity",
        description="Sanity CMS management and content tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.HIGH,
        profiles={"content"},
        env=["SANITY_API_TOKEN"],
        context_cost=3,
    ),
    ToolSource(
        name="sentry",
        description="Sentry issue and observability tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"ops"},
        env=["SENTRY_AUTH_TOKEN"],
        context_cost=3,
    ),
    ToolSource(
        name="upstash",
        description="Upstash Redis and account management tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"cloud", "ops"},
        env=["UPSTASH_EMAIL", "UPSTASH_API_KEY"],
        context_cost=3,
    ),
    ToolSource(
        name="browser",
        description="Local browser automation tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.MEDIUM,
        profiles={"web"},
        context_cost=4,
    ),
    ToolSource(
        name="resend",
        description="Resend email, contact, broadcast, and template tools.",
        transport=Transport.STDIO,
        risk=RiskLevel.HIGH,
        profiles={"email", "content"},
        env=["RESEND_API_KEY"],
        context_cost=5,
    ),
    ToolSource(
        name="quiverai",
        description="QuiverAI SVG generation and asset tools.",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"image"},
        context_cost=3,
    ),
    ToolSource(
        name="utrecht",
        description="Optional Utrecht Data OS MCP or command adapter.",
        transport=Transport.SSE,
        risk=RiskLevel.LOW,
        profiles={"utrecht"},
        env=["UTRECHT_MCP_URL"],
        context_cost=2,
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
