"""Minimal private-profile fixture for OSS tests (not a real deployment)."""

from __future__ import annotations

from kater.chains import ChainDefinition, ChainStep
from kater.profiles import McpServerConfig, RiskLevel, ToolSource, Transport
from kater.registry import NativeTool

PRIVATE_PROFILES = frozenset({"demo_private"})

TOOL_SOURCES: tuple[ToolSource, ...] = (
    ToolSource(
        name="demo_private_server",
        description="Fixture server for private-profile visibility tests.",
        transport=Transport.NATIVE,
        risk=RiskLevel.LOW,
        profiles={"demo_private"},
        mcp=McpServerConfig(),
    ),
)

NATIVE_TOOLS: list[NativeTool] = [
    NativeTool(
        name="demo_private_status",
        description="Fixture native tool for private-profile tests.",
        profile="demo_private",
        risk="low",
        handler=lambda: {"ok": True},
    ),
]

CHAINS: tuple[ChainDefinition, ...] = (
    ChainDefinition(
        name="demo_private_chain",
        description="Fixture chain for private-profile tests.",
        profiles={"demo_private"},
        steps=[ChainStep(tool="demo_private_status", reason="Check fixture tool.")],
    ),
)

# CHE-659: private deployments (e.g. utrecht-katermcp) export CAPABILITIES the same way.
from kater.capabilities.models import (  # noqa: E402
    CapabilityManifest,
    CapabilityTransport,
    RiskClass,
)

CAPABILITIES: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id="demo.private.status",
        package_id="demo_private",
        publisher_id="onlinechefgroep",
        version="1.0.0",
        digest="sha256:demo-private-status",
        transport=CapabilityTransport.NATIVE,
        description="Fixture capability for extension CAPABILITIES loading.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_scopes=frozenset(),
        risk_class=RiskClass.READ,
        data_classification="internal",
        profiles=frozenset({"demo_private"}),
        tags=frozenset({"demo"}),
    ),
)
