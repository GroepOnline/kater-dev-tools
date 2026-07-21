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

## 2026-07-21 - [Async View Layout, Race-Safe Reload, and DOM-Safe Rendering]

**Learning:** Asynchronous dashboard views (e.g., PR control) must follow the standard `.view-header` / `.view-scroll` layout to stay visually consistent with other tabs. When the user can trigger reloads while a previous request is in flight, an incrementing sequence counter (`prLoadSeq`) is the simplest way to discard stale responses and stale errors so the view never shows outdated data. Finally, building cards with `document.createElement` + `textContent` instead of `innerHTML` removes the DOM XSS surface entirely — server data never flows through the HTML parser.

**Action:** For every async-loading view: (1) use `.view-header` + `.view-scroll`, (2) add a manual reload button that toggles `disabled` + `aria-busy` and restores itself in a `finally` block, (3) guard the async body with a sequence counter so superseded responses are ignored, and (4) render untrusted server data via the DOM API (`textContent`, `setAttribute`) rather than `innerHTML`.
