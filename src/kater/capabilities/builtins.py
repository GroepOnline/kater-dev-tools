from __future__ import annotations

import hashlib

from kater.capabilities.models import (
    CapabilityManifest,
    CapabilityTransport,
    LifecycleState,
    RiskClass,
)

_PUBLISHER = "kater"
_PACKAGE_CORE = "kater.core"
_VERSION = "1.0.0"


def _digest(capability_id: str, version: str) -> str:
    payload = f"{capability_id}@{version}".encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _native(
    capability_id: str,
    *,
    description: str,
    profiles: frozenset[str],
    tags: frozenset[str] = frozenset(),
    required_scopes: frozenset[str] = frozenset(),
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    risk_class: RiskClass = RiskClass.READ,
    mutation: bool = False,
) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        package_id=_PACKAGE_CORE,
        publisher_id=_PUBLISHER,
        version=_VERSION,
        digest=_digest(capability_id, _VERSION),
        transport=CapabilityTransport.NATIVE,
        description=description,
        input_schema=input_schema if input_schema is not None else {},
        output_schema=output_schema if output_schema is not None else {},
        required_scopes=required_scopes,
        risk_class=risk_class,
        data_classification="internal",
        profiles=profiles,
        lifecycle_state=LifecycleState.ACTIVE,
        tags=tags,
        mutation=mutation,
    )


BUILTIN_CAPABILITIES: tuple[CapabilityManifest, ...] = (
    _native(
        "kater.profiles.list",
        description="List available Kater profiles and their tool sources.",
        profiles=frozenset({"core"}),
        tags=frozenset({"profiles", "kater"}),
        required_scopes=frozenset({"kater.profiles.read"}),
    ),
    _native(
        "kater.doctor.run",
        description="Run Kater doctor checks and return diagnostic findings.",
        profiles=frozenset({"core"}),
        tags=frozenset({"doctor", "diagnostics", "kater"}),
        required_scopes=frozenset({"kater.doctor.run"}),
    ),
    _native(
        "kater.proxy.status",
        description="Report proxy backend status and enablement.",
        profiles=frozenset({"core"}),
        tags=frozenset({"proxy", "status", "kater"}),
        required_scopes=frozenset({"kater.proxy.read"}),
    ),
    _native(
        "web.search",
        description="Logical web search route capability (placeholder schemas).",
        profiles=frozenset({"research", "web"}),
        tags=frozenset({"web", "search", "research"}),
        required_scopes=frozenset({"web.search"}),
        input_schema={},
        output_schema={},
    ),
    _native(
        "kater.session.continue",
        description="Continue an active remote-context agent session.",
        profiles=frozenset({"core"}),
        tags=frozenset({"session", "kater"}),
        risk_class=RiskClass.LOCAL_WRITE,
        mutation=True,
        input_schema={"type": "object", "properties": {"context_id": {"type": "string"}}},
    ),
    _native(
        "kater.session.work.submit",
        description="Submit natural-language work on a remote-context session.",
        profiles=frozenset({"core"}),
        tags=frozenset({"session", "kater"}),
        risk_class=RiskClass.LOCAL_WRITE,
        mutation=True,
        input_schema={
            "type": "object",
            "properties": {
                "context_id": {"type": "string"},
                "prompt": {"type": "string"},
                "katerContextId": {"type": "string"},
            },
        },
    ),
    _native(
        "kater.session.work.cancel",
        description="Cancel in-flight session work.",
        profiles=frozenset({"core"}),
        tags=frozenset({"session", "kater"}),
        risk_class=RiskClass.LOCAL_WRITE,
        mutation=True,
    ),
    _native(
        "kater.session.work.transition",
        description="Advance session work through the Kater agent state machine.",
        profiles=frozenset({"core"}),
        tags=frozenset({"session", "kater"}),
        risk_class=RiskClass.LOCAL_WRITE,
        mutation=True,
    ),
    _native(
        "kater.session.events.read",
        description="Poll authoritative Kater-neutral session events.",
        profiles=frozenset({"core"}),
        tags=frozenset({"session", "kater"}),
    ),
    _native(
        "kater.session.events.append",
        description="Append a provider-neutral session event for an existing context.",
        profiles=frozenset({"core"}),
        tags=frozenset({"session", "kater"}),
        risk_class=RiskClass.LOCAL_WRITE,
        mutation=True,
    ),
)


def iter_builtins() -> tuple[CapabilityManifest, ...]:
    return BUILTIN_CAPABILITIES
