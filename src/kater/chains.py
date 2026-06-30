from __future__ import annotations

from pydantic import BaseModel, Field


class ChainStep(BaseModel):
    tool: str
    reason: str


class ChainDefinition(BaseModel):
    name: str
    description: str
    profiles: set[str] = Field(default_factory=set)
    steps: list[ChainStep]


CHAINS: tuple[ChainDefinition, ...] = (
    ChainDefinition(
        name="research_brief",
        description="Use research tools, then summarize findings for an agent.",
        profiles={"research", "web"},
        steps=[
            ChainStep(tool="firecrawl_search", reason="Find current sources."),
            ChainStep(tool="firecrawl_scrape", reason="Read selected source pages."),
            ChainStep(tool="kater_summary", reason="Return a compact brief."),
        ],
    ),
    ChainDefinition(
        name="pr_health",
        description="Check GitHub/Linear/Sentry context for a development branch.",
        profiles={"ops", "code"},
        steps=[
            ChainStep(tool="github_pr_status", reason="Inspect PR checks."),
            ChainStep(tool="linear_issue_status", reason="Inspect linked ticket status."),
            ChainStep(tool="sentry_issue_search", reason="Look for fresh regressions."),
        ],
    ),
    ChainDefinition(
        name="utrecht_status",
        description="Check Utrecht Data OS status through its optional adapter.",
        profiles={"utrecht"},
        steps=[
            ChainStep(tool="utrecht_pipeline_status", reason="Check local pipeline artifacts."),
            ChainStep(tool="utrecht_fleet_inventory", reason="Summarize the safe Fleet inventory."),
            ChainStep(tool="utrecht_agent_manifest", reason="Inspect Utrecht tool surface."),
        ],
    ),
)


def list_chains(profile: str | None = None) -> list[ChainDefinition]:
    from kater.profiles import PRIVATE_PROFILES, is_public_mode

    chains = list(CHAINS)
    if is_public_mode():
        # Hide chains that only belong to private (org-specific) profiles.
        chains = [c for c in chains if not (c.profiles and c.profiles.issubset(PRIVATE_PROFILES))]
    if profile is None:
        return chains
    return [chain for chain in chains if profile in chain.profiles]
