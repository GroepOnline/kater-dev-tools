## 2025-05-15 - [ARIA Tabs Implementation]
**Learning:** Implementing the WAI-ARIA Tabs pattern (role="tablist", role="tab", role="tabpanel") significantly improves keyboard navigation and screen reader support for single-page dashboard interfaces. It provides a standard way for users to understand and interact with navigable sections.
**Action:** Always use the full WAI-ARIA Tabs pattern when building tabbed interfaces to ensure accessibility standards are met.

## 2025-07-12 - [UX Recovery Pattern for Search]
**Learning:** Providing a "Clear search" recovery path in zero-result states (using the `.view-empty-link` pattern) reduces user frustration by offering an immediate way back to a valid state without requiring manual text deletion.
**Action:** Implement functional recovery links in all empty/zero-result states within dashboard views.

## 2026-07-14 - [Dynamic ARIA for Status Transitions]
**Learning:** For background processes like tunnels or long-running actions, updating ARIA labels to reflect transitionary states (e.g., "Starting...") provides critical feedback to screen reader users that the application is processing their request. Visible button text must stay in lockstep with the announced action (Start/Stop, not ON vs Stop).
**Action:** Always implement state-aware ARIA labels for buttons that trigger asynchronous state changes, and keep visible labels action-consistent.

## 2025-07-20 - [Keyboard-Safe ARIA Tabs]
**Learning:** Implementing 'roving tabindex' (tabindex="-1" for inactive tabs) without custom arrow-key event listeners breaks keyboard navigation. For simple tabbed interfaces, maintaining `tabindex="0"` on all tabs preserves default sequential navigation while still benefiting from ARIA semantic roles.
**Action:** Only use roving tabindex when fully implementing the keyboard interaction model (arrows, Home, End); otherwise, stick to standard sequential tabbing.
