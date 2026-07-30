"""Native browser lane: policy-guarded browser automation for agents.

Importing this package is cheap and side-effect free — no browser is started
and playwright is never imported until a provider is actually used.
"""

from __future__ import annotations

from kater.browser.models import (
    ActionKind,
    ActionResult,
    BrowserAction,
    BrowserSession,
    ProviderKind,
    SessionState,
    new_session_id,
)
from kater.browser.policy import BrowserPolicy, PolicyViolation, load_policy
from kater.browser.providers import (
    BrowserProvider,
    BrowserUnavailableError,
    CdpProvider,
    PlaywrightProvider,
    ProviderInfo,
    SteelProvider,
    probe_providers,
    resolve_provider,
)
from kater.browser.session import (
    BrowserSessionManager,
    SessionLimitError,
    UnknownSessionError,
    get_manager,
    reset_manager,
    set_manager,
)

__all__ = [
    "ActionKind",
    "ActionResult",
    "BrowserAction",
    "BrowserPolicy",
    "BrowserProvider",
    "BrowserSession",
    "BrowserSessionManager",
    "BrowserUnavailableError",
    "CdpProvider",
    "PlaywrightProvider",
    "PolicyViolation",
    "ProviderInfo",
    "ProviderKind",
    "SessionLimitError",
    "SessionState",
    "SteelProvider",
    "UnknownSessionError",
    "get_manager",
    "load_policy",
    "new_session_id",
    "probe_providers",
    "reset_manager",
    "resolve_provider",
    "set_manager",
]
