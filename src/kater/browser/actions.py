"""Execution of one :class:`~kater.browser.models.BrowserAction` against a page.

Kept separate from the providers so the Playwright-specific page driving lives
in one place and every provider (local launch, CDP attach, Steel) shares the
exact same policy enforcement. Page objects are typed ``Any``: this module must
never import playwright at module scope.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from kater.browser.models import NAVIGATING_KINDS, ActionKind, ActionResult, BrowserAction
from kater.browser.policy import BrowserPolicy, PolicyViolation

MAX_TEXT_CHARS = 20_000
SNAPSHOT_LIMIT = 100
DEFAULT_SCROLL_DELTA = 600
SCREENSHOT_QUALITY = 60

# Compact "what can an agent act on here" digest. Returns the first
# SNAPSHOT_LIMIT interactive elements with a stable CSS selector each.
_SNAPSHOT_JS = """
(limit) => {
  const selectorFor = (el) => {
    if (el.id) { return '#' + CSS.escape(el.id); }
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter(
          (c) => c.tagName === node.tagName
        );
        if (same.length > 1) {
          part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
        }
      }
      parts.unshift(part);
      if (!parent || parent.tagName === 'HTML') { break; }
      node = parent;
    }
    return parts.join(' > ');
  };
  // Only button-like <input> elements carry a human label in `value`
  // (e.g. <input type="submit" value="Search">). Text/password/email inputs,
  // textareas and selects hold user-entered or autofilled data, so their live
  // value must never leak through the snapshot name.
  const valueLabel = (el) => {
    if (el.tagName !== 'INPUT') { return ''; }
    const type = (el.getAttribute('type') || 'text').toLowerCase();
    if (type === 'submit' || type === 'button' || type === 'reset') {
      return typeof el.value === 'string' ? el.value : '';
    }
    return '';
  };
  const nameFor = (el) => (
    el.getAttribute('aria-label') ||
    el.getAttribute('placeholder') ||
    el.getAttribute('name') ||
    el.getAttribute('title') ||
    el.getAttribute('alt') ||
    valueLabel(el) ||
    (el.innerText || '')
  );
  const out = [];
  const nodes = document.querySelectorAll('a, button, input, textarea, select, [role]');
  for (const el of nodes) {
    if (out.length >= limit) { break; }
    const rect = el.getBoundingClientRect();
    out.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      name: (nameFor(el) || '').trim().slice(0, 160),
      selector: selectorFor(el),
      text: (el.innerText || '').trim().slice(0, 160),
      visible: rect.width > 0 && rect.height > 0,
    });
  }
  return out;
}
"""


def execute_action(
    page: Any,
    action: BrowserAction,
    policy: BrowserPolicy,
    *,
    session_id: str,
    allow_evaluate: bool = False,
    clock: Any = time.time,
) -> ActionResult:
    """
    Execute a browser action while enforcing navigation and evaluation policies.
    
    Parameters:
        session_id (str): Identifier associated with the browser session.
        allow_evaluate (bool): Whether page script evaluation is permitted.
        clock (Any): Callable used to measure action timing.
    
    Returns:
        ActionResult: The action outcome, including page state and any extracted
            text, screenshot, or snapshot. Execution failures are represented in
            the result.
    """
    started = clock()
    timeout = min(
        float(action.timeout_ms or policy.action_timeout_ms),
        float(policy.action_timeout_ms),
    )
    text: str | None = None
    screenshot: str | None = None
    snapshot: tuple[dict[str, Any], ...] | None = None

    try:
        if action.kind is ActionKind.EVALUATE and not allow_evaluate:
            raise PolicyViolation(
                "evaluate is disabled; start the provider with allow_evaluate=True "
                "(KATER_BROWSER_ALLOW_EVALUATE=1) to permit arbitrary page scripts"
            )
        if action.kind is ActionKind.NAVIGATE and action.url:
            policy.check_url(action.url)

        result = _dispatch(page, action, policy, timeout=timeout, allow_evaluate=allow_evaluate)
        text, screenshot, snapshot = result

        if action.kind in NAVIGATING_KINDS:
            _enforce_landing_url(page, policy)
    except PolicyViolation as exc:
        return _failure(action, session_id, started, clock, f"policy: {exc}", page)
    except Exception as exc:
        return _failure(action, session_id, started, clock, _describe(exc), page)

    return ActionResult(
        ok=True,
        kind=action.kind,
        session_id=session_id,
        started_at=started,
        duration_ms=(clock() - started) * 1000.0,
        url=_safe_url(page),
        title=_safe_title(page),
        text=text,
        screenshot_b64=screenshot,
        snapshot=snapshot,
    )


def _dispatch(
    page: Any,
    action: BrowserAction,
    policy: BrowserPolicy,
    *,
    timeout: float,
    allow_evaluate: bool,
) -> tuple[str | None, str | None, tuple[dict[str, Any], ...] | None]:
    """
    Execute a browser action and return any resulting text, screenshot, or element snapshot.
    
    Parameters:
        page (Any): Playwright-like page object on which to perform the action.
        action (BrowserAction): Action to execute.
        policy (BrowserPolicy): Policy used for operations requiring enforcement.
        timeout (float): Maximum duration for supported page operations.
        allow_evaluate (bool): Whether expression evaluation is permitted.
    
    Returns:
        tuple[str | None, str | None, tuple[dict[str, Any], ...] | None]: Text, base64-encoded screenshot, and element snapshot produced by the action, respectively.
    """
    kind = action.kind
    if kind is ActionKind.NAVIGATE:
        page.goto(action.url, timeout=timeout, wait_until="domcontentloaded")
    elif kind is ActionKind.CLICK:
        page.click(action.selector, timeout=timeout)
    elif kind is ActionKind.TYPE:
        page.fill(action.selector, action.text or "", timeout=timeout)
    elif kind is ActionKind.PRESS:
        page.keyboard.press(action.key)
    elif kind is ActionKind.SCROLL:
        page.mouse.wheel(0, action.delta_y if action.delta_y is not None else DEFAULT_SCROLL_DELTA)
    elif kind is ActionKind.WAIT:
        if action.selector:
            page.wait_for_selector(action.selector, timeout=timeout)
        else:
            page.wait_for_timeout(timeout)
    elif kind is ActionKind.SCREENSHOT:
        return None, _screenshot(page, action.full_page, policy), None
    elif kind is ActionKind.SNAPSHOT:
        return None, None, _snapshot(page)
    elif kind is ActionKind.EXTRACT_TEXT:
        return _extract_text(page, action.selector, timeout), None, None
    elif kind is ActionKind.EVALUATE:
        if not allow_evaluate:  # defence in depth; execute_action checks first
            raise PolicyViolation("evaluate is disabled")
        return _stringify(page.evaluate(action.expression)), None, None
    elif kind is ActionKind.BACK:
        page.go_back(timeout=timeout)
    elif kind is ActionKind.FORWARD:
        page.go_forward(timeout=timeout)
    elif kind is ActionKind.RELOAD:
        page.reload(timeout=timeout)
    elif kind is ActionKind.SELECT:
        page.select_option(action.selector, action.value, timeout=timeout)
    else:  # pragma: no cover — ActionKind is exhaustive above
        raise ValueError(f"unsupported action kind: {kind}")
    return None, None, None


def _screenshot(page: Any, full_page: bool, policy: BrowserPolicy) -> str:
    """
    Capture a JPEG screenshot and encode it as an ASCII base64 string.
    
    Parameters:
        full_page (bool): Whether to capture the full page before falling back to the viewport.
        policy (BrowserPolicy): Policy defining the maximum permitted screenshot size.
    
    Returns:
        str: The base64-encoded screenshot.
    
    Raises:
        PolicyViolation: If the screenshot exceeds the configured size limit.
    """
    raw = page.screenshot(type="jpeg", quality=SCREENSHOT_QUALITY, full_page=full_page)
    if len(raw) > policy.max_screenshot_bytes:
        if not full_page:
            raise PolicyViolation(
                f"screenshot is {len(raw)} bytes, over the "
                f"{policy.max_screenshot_bytes} byte cap"
            )
        # Full-page captures blow the cap on long documents; fall back to the
        # viewport rather than failing the agent's live-view request.
        raw = page.screenshot(type="jpeg", quality=SCREENSHOT_QUALITY, full_page=False)
        if len(raw) > policy.max_screenshot_bytes:
            raise PolicyViolation(
                f"screenshot is {len(raw)} bytes, over the "
                f"{policy.max_screenshot_bytes} byte cap"
            )
    return base64.b64encode(raw).decode("ascii")


def _snapshot(page: Any) -> tuple[dict[str, Any], ...]:
    """
    Collect a bounded snapshot of interactive page elements.
    
    Parameters:
        page (Any): Playwright-compatible page object used to evaluate the snapshot script.
    
    Returns:
        tuple[dict[str, Any], ...]: Snapshot entries represented as dictionaries.
    """
    raw = page.evaluate(_SNAPSHOT_JS, SNAPSHOT_LIMIT)
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, dict))


def _extract_text(page: Any, selector: str | None, timeout: float) -> str:
    """Extracts text from the selected page element or the document body.
    
    Parameters:
    	page (Any): Page object providing text extraction.
    	selector (str | None): Selector identifying the element to extract from; uses the document body when omitted.
    	timeout (float): Maximum time to wait for the text extraction.
    
    Returns:
    	str: Extracted text, truncated when it exceeds the configured character limit.
    """
    target = selector or "body"
    text = page.inner_text(target, timeout=timeout)
    return _stringify(text)


def _stringify(value: Any) -> str:
    """
    Convert a value to text and truncate it when it exceeds the maximum text length.
    
    Parameters:
        value (Any): The value to convert.
    
    Returns:
        str: The original string or a representation of the value, truncated with an indicator when it exceeds the maximum length.
    """
    text = value if isinstance(value, str) else repr(value)
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS] + f"\n… truncated at {MAX_TEXT_CHARS} chars"
    return text


def _enforce_landing_url(page: Any, policy: BrowserPolicy) -> None:
    """Re-check where the page actually ended up (redirect / meta-refresh)."""
    landed = _safe_url(page)
    if not landed:
        return
    try:
        policy.check_url(landed)
    except PolicyViolation:
        _blank(page)
        raise


def _blank(page: Any) -> None:
    """Best-effort navigation of the page to a blank document."""
    try:
        page.goto("about:blank", timeout=5000)
    except Exception:  # noqa: S110 — best-effort containment, error already fatal
        pass


def _safe_url(page: Any) -> str | None:
    """Return the page URL when it is available, or ``None`` if it cannot be read."""
    try:
        url = page.url
    except Exception:
        return None
    return str(url) if url else None


def _safe_title(page: Any) -> str | None:
    """Read the page title, returning ``None`` when it is unavailable or empty.
    
    Parameters:
        page (Any): Page object from which to retrieve the title.
    
    Returns:
        str | None: The page title, or ``None`` if retrieval fails or the title is empty.
    """
    try:
        title = page.title()
    except Exception:
        return None
    return str(title) if title else None


def _describe(exc: Exception) -> str:
    """
    Format an exception as a concise single-line description.
    
    Parameters:
        exc (Exception): The exception to describe.
    
    Returns:
        str: The exception class name followed by its first message line.
    """
    message = str(exc).strip() or exc.__class__.__name__
    first = message.splitlines()[0]
    return f"{exc.__class__.__name__}: {first}" if first else exc.__class__.__name__


def _failure(
    action: BrowserAction,
    session_id: str,
    started: float,
    clock: Any,
    message: str,
    page: Any,
) -> ActionResult:
    """
    Create a failed action result with timing, session, page metadata, and an error message.
    
    Parameters:
        action (BrowserAction): The action that failed.
        session_id (str): Identifier of the browser session.
        started (float): Start time used to calculate the action duration.
        clock (Any): Callable that provides the current time.
        message (str): Description of the failure.
        page (Any): Page object from which to read the current URL and title.
    
    Returns:
        ActionResult: A failed result containing the action details and error information.
    """
    return ActionResult(
        ok=False,
        kind=action.kind,
        session_id=session_id,
        started_at=started,
        duration_ms=(clock() - started) * 1000.0,
        url=_safe_url(page),
        title=_safe_title(page),
        error=message,
    )
