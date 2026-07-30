"""Terminal interactive dashboard for Kater.

Dependency-light TUI: ANSI helpers only. Browser / automations panels soft-fail
when those subsystems are not importable or not running.
"""

from __future__ import annotations

import importlib
import os
import shlex
import sys
import time
from typing import Any

from kater.ansi import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW
from kater.browser.base import redact_endpoint
from kater.profiles import all_tool_sources, get_source, list_profiles
from kater.settings import load_settings, save_settings
from kater.telemetry import clear_events, load_events, record_server_toggle, status_overview

_RULE = f"{DIM}{'─' * 72}{RESET}"
_CMD_HINT = (
    f"{DIM}commands: toggle|enable|disable <name> | profile <name> | "
    f"browser | auto | status | clear | help | quit{RESET}"
)


def _clear() -> None:
    """Clear the terminal screen and move the cursor to the home position."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _hide_cursor() -> None:
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def _show_cursor() -> None:
    """Show the terminal cursor."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


# ── soft probes (browser / automations) ─────────────────────────────


def browser_stats() -> dict[str, Any] | None:
    """
    Retrieve browser session statistics when the browser subsystem is available.
    
    Returns:
        dict[str, Any] | None: Browser statistics, or `None` when unavailable.
    """
    try:
        from kater.browser.session import get_manager
    except ImportError:
        return None
    try:
        return get_manager().stats()
    except Exception:
        return None


def browser_sessions(*, live_only: bool = False) -> list[dict[str, Any]] | None:
    """
    List available browser sessions in dictionary form.
    
    Parameters:
    	live_only (bool): Whether to include only live sessions.
    
    Returns:
    	list[dict[str, Any]] | None: The session dictionaries, or `None` when the browser session service is unavailable.
    """
    try:
        from kater.browser.session import get_manager
    except ImportError:
        return None
    try:
        sessions = get_manager().list_sessions(live_only=live_only)
    except Exception:
        return None
    return [s.to_dict() for s in sessions]


def automation_count() -> int | None:
    """
    Determine the number of available automations.
    
    Returns:
        int | None: The automation count, or `None` when the automation engine is unavailable or cannot be queried.
    """
    engine = _automation_engine()
    if engine is None:
        return None
    try:
        items = _automation_items(engine)
    except Exception:
        return None
    return len(items)


def automation_list() -> list[dict[str, Any]] | None:
    """
    List available automations in dictionary form.
    
    Returns:
        list[dict[str, Any]]: The normalized automation records, or None when the automation engine is unavailable or cannot be queried.
    """
    engine = _automation_engine()
    if engine is None:
        return None
    try:
        return _automation_items(engine)
    except Exception:
        return None


def _automation_engine() -> Any | None:
    """Retrieve the available automation engine.
    
    Returns:
        Any | None: The automation engine, or `None` when it is unavailable or cannot be initialized.
    """
    getter: Any | None = None
    try:
        from kater.automations import get_engine as getter
    except ImportError:
        try:
            mod = importlib.import_module("kater.automations.engine")
        except ImportError:
            return None
        getter = getattr(mod, "get_engine", None)
    if getter is None:
        return None
    try:
        return getter()
    except Exception:
        return None


def _automation_items(engine: Any) -> list[dict[str, Any]]:
    """
    Normalize automation entries from an engine into dictionaries.
    
    Parameters:
        engine (Any): Automation engine providing an available listing method.
    
    Returns:
        list[dict[str, Any]]: Normalized automation entries.
    """
    if hasattr(engine, "list_automations"):
        raw = engine.list_automations()
    elif hasattr(engine, "list"):
        raw = engine.list()
    elif hasattr(engine, "all"):
        raw = engine.all()
    else:
        return []
    out: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, dict):
            out.append(item)
        elif hasattr(item, "to_dict"):
            out.append(item.to_dict())
        else:
            out.append(
                {
                    "id": getattr(item, "id", "?"),
                    "name": getattr(item, "name", str(item)),
                    "enabled": bool(getattr(item, "enabled", True)),
                    "kind": getattr(item, "kind", ""),
                    "last_status": getattr(item, "last_status", None),
                }
            )
    return out


# ── pure formatters (unit-tested without a TTY) ─────────────────────


def format_status_lines(
    *,
    version: str,
    profile: str,
    auth_mode: str,
    servers_enabled: int,
    servers_total: int,
    servers_configured: int,
    servers_missing: int,
    browser_sessions: int | None,
    automations: int | None,
    events_total: int,
    tool_calls: int,
    errors: int,
    success_rate: float,
) -> list[str]:
    """
    Build the header and summary lines for the status panel.
    
    Parameters:
        version (str): Kater version displayed in the header.
        profile (str): Active profile name.
        auth_mode (str): Authentication mode.
        servers_enabled (int): Number of enabled servers.
        servers_total (int): Total number of servers.
        servers_configured (int): Number of configured servers.
        servers_missing (int): Number of servers missing required environment variables.
        browser_sessions (int | None): Browser session count, or `None` when unavailable.
        automations (int | None): Automation count, or `None` when unavailable.
        events_total (int): Total number of recorded events.
        tool_calls (int): Number of tool calls.
        errors (int): Number of errors.
        success_rate (float): Tool-call success rate as a percentage.
    
    Returns:
        list[str]: Formatted status panel lines.
    """
    browser = "-" if browser_sessions is None else str(browser_sessions)
    autos = "-" if automations is None else str(automations)
    en_color = GREEN if servers_enabled == servers_total else YELLOW
    cfg_color = GREEN if servers_configured > 0 else RED
    miss_color = RED if servers_missing else GREEN
    return [
        (
            f"{BOLD}KATER{RESET} {DIM}v{version}{RESET}"
            f"  {CYAN}profile{RESET} {BOLD}{profile}{RESET}"
            f"  {YELLOW}auth{RESET} {auth_mode}"
        ),
        _RULE,
        (
            f"  servers {en_color}{servers_enabled}/{servers_total}{RESET} enabled"
            f"  {DIM}|{RESET}  {cfg_color}{servers_configured}{RESET} configured"
            f"  {DIM}|{RESET}  {miss_color}{servers_missing}{RESET} missing env"
            f"  {DIM}|{RESET}  browser {CYAN}{browser}{RESET}"
            f"  {DIM}|{RESET}  autos {CYAN}{autos}{RESET}"
        ),
        (
            f"  events {events_total}"
            f"  {DIM}|{RESET}  calls {tool_calls}"
            f"  {DIM}|{RESET}  errors {errors}"
            f"  {DIM}|{RESET}  success {success_rate:.1f}%"
        ),
    ]


def format_server_mark(enabled: bool, env_ok: bool) -> str:
    """
    Format a colored status mark for a server.
    
    Parameters:
        enabled (bool): Whether the server is enabled.
        env_ok (bool): Whether the server's required environment is configured.
    
    Returns:
        str: A colored `*` for enabled servers with valid configuration, `o` for enabled servers with missing configuration, or `-` for disabled servers.
    """
    if enabled and env_ok:
        return f"{GREEN}*{RESET}"
    if enabled:
        return f"{YELLOW}o{RESET}"
    return f"{RED}-{RESET}"


def format_session_row(session: dict[str, Any]) -> str:
    """
    Format a browser session as a fixed-width display row.
    
    Parameters:
    	session (dict[str, Any]): Session data containing its identifier, state, and optional label or URL.
    
    Returns:
    	str: A formatted session row with truncated identifier and detail fields.
    """
    sid = str(session.get("session_id", "?"))
    short = sid if len(sid) <= 20 else sid[:20]
    state = str(session.get("state", "?"))
    label = session.get("label") or ""
    if label:
        detail = str(label)
    else:
        raw_url = str(session.get("current_url") or "")
        detail = redact_endpoint(raw_url) if raw_url else "-"
    if len(detail) > 36:
        detail = detail[:35] + "~"
    return f"  {short:<20} {state:<8} {detail}"


def format_automation_row(item: dict[str, Any]) -> str:
    """
    Format an automation item as an aligned display row.
    
    Parameters:
    	item (dict[str, Any]): Automation data containing its name or identifier, enabled state, kind, and latest status.
    
    Returns:
    	str: A fixed-width formatted row for the automation item.
    """
    name = str(item.get("name") or item.get("id") or "?")
    if len(name) > 24:
        name = name[:23] + "~"
    enabled = item.get("enabled", True)
    flag = "on " if enabled else "off"
    kind = str(item.get("kind") or "-")
    status = str(item.get("last_status") or "-")
    return f"  {name:<24} {flag:<3} {kind:<10} {status}"


# ── render / commands ──────────────────────────────────────────────


def interactive_loop(
    profile: str = "core",
    refresh_interval: float = 3.0,
) -> None:
    """
    Run the interactive terminal dashboard and process user commands.
    
    Parameters:
        profile (str): Initial configuration profile.
        refresh_interval (float): Minimum number of seconds between automatic dashboard refreshes.
    """
    current_profile = profile
    running = True
    refresh_needed = True
    last_refresh = 0.0

    _hide_cursor()
    try:
        while running:
            now = time.time()
            if refresh_needed or now - last_refresh > refresh_interval:
                _render(current_profile)
                last_refresh = now
                refresh_needed = False

            sys.stdout.write(f"\n{DIM}> {RESET}")
            sys.stdout.flush()

            try:
                raw = sys.stdin.readline()
            except (EOFError, KeyboardInterrupt):
                break
            # readline() returns "" at EOF — guard against a tight spin.
            if not raw:
                break
            line = raw.strip()
            if not line:
                continue

            parts = shlex.split(line)
            cmd = parts[0].lower() if parts else ""

            if cmd in ("q", "quit", "exit"):
                running = False
            elif cmd == "profile" and len(parts) > 1:
                if parts[1] in list_profiles():
                    current_profile = parts[1]
                    os.environ["KATER_PROFILE"] = current_profile
                    refresh_needed = True
                else:
                    _print_err(f"unknown profile: {parts[1]}")
            elif cmd in ("toggle", "enable", "disable") and len(parts) > 1:
                _handle_toggle(parts[0], parts[1])
                refresh_needed = True
            elif cmd == "status":
                refresh_needed = True
            elif cmd == "browser":
                _print_browser()
                last_refresh = time.time()
            elif cmd in ("auto", "automations"):
                _print_automations()
                last_refresh = time.time()
            elif cmd == "help":
                _print_help()
                last_refresh = time.time()
            elif cmd == "clear":
                count = clear_events()
                _print_ok(f"cleared {count} events")
                refresh_needed = True
            else:
                _print_err(f"unknown: {line} (type 'help')")
    finally:
        _show_cursor()
        _clear()
        print(f"{DIM}kater interactive stopped.{RESET}")


def _render(profile: str) -> None:
    """
    Render the current dashboard state for the selected profile.
    
    Parameters:
        profile (str): Profile whose applicable tool sources should be displayed.
    """
    _clear()
    data = status_overview()
    s = data["servers"]
    t = data["telemetry"]
    stats = browser_stats()
    browser_n = None if stats is None else int(stats.get("sessions", 0))
    auto_n = automation_count()

    for line in format_status_lines(
        version=str(data["version"]),
        profile=str(data["profile"]),
        auth_mode=str(data["auth_mode"]),
        servers_enabled=int(s["enabled"]),
        servers_total=int(s["total"]),
        servers_configured=int(s["configured"]),
        servers_missing=int(s["missing_env"]),
        browser_sessions=browser_n,
        automations=auto_n,
        events_total=int(t["total_events"]),
        tool_calls=int(t["tool_calls"]),
        errors=int(t["errors"]),
        success_rate=float(t["success_rate"]),
    ):
        print(line)

    print(_RULE)
    print(f"  {BOLD}SERVERS{RESET}  {DIM}* on  o missing env  - off{RESET}")

    settings = load_settings()
    for source in all_tool_sources():
        if source.transport == "native":
            continue
        if profile not in source.profiles and profile != "core":
            continue
        enabled = settings.is_server_enabled(source.name, default=True)
        env_ok = all(os.environ.get(v) for v in source.env)
        mark = format_server_mark(enabled, env_ok)
        risk = source.risk.value
        risk_color = RED if risk == "high" else YELLOW if risk == "medium" else GREEN
        print(
            f"  {mark} {source.name:<20} "
            f"{DIM}{source.transport.value:<6}{RESET} "
            f"{risk_color}{risk}{RESET}"
        )

    print(_RULE)
    print(f"  {BOLD}EVENTS{RESET}")
    events = load_events()
    recent = events[-5:]
    if not recent:
        print(f"  {DIM}(none){RESET}")
    else:
        for e in recent:
            ok = e.get("success", True)
            mark = f"{GREEN}+{RESET}" if ok else f"{RED}x{RESET}"
            name = str(e.get("name", "?"))[:20]
            dur = float(e.get("duration_ms", 0) or 0)
            etype = str(e.get("type", ""))[:12]
            print(f"  {mark} {DIM}{etype:<12}{RESET} {name:<20} {dur:>6.1f}ms")

    print(_RULE)
    print(f"  {_CMD_HINT}")


def _print_browser() -> None:
    """
    Print the browser session panel, including session counts and details when available.
    """
    sessions = browser_sessions()
    if sessions is None:
        _print_err("browser lane unavailable")
        return
    stats = browser_stats() or {}
    live = stats.get("live", "?")
    print(f"  {BOLD}BROWSER{RESET}  {len(sessions)} session(s)  {DIM}live {live}{RESET}")
    if not sessions:
        print(f"  {DIM}(no sessions){RESET}")
        return
    print(f"  {DIM}{'id':<20} {'state':<8} detail{RESET}")
    for session in sessions:
        print(format_session_row(session))


def _print_automations() -> None:
    """
    Print the available automations and their status, or an error when the automations engine is unavailable.
    """
    items = automation_list()
    if items is None:
        _print_err("automations engine unavailable")
        return
    print(f"  {BOLD}AUTOMATIONS{RESET}  {len(items)}")
    if not items:
        print(f"  {DIM}(none){RESET}")
        return
    print(f"  {DIM}{'name':<24} {'en':<3} {'kind':<10} status{RESET}")
    for item in items:
        print(format_automation_row(item))


def _handle_toggle(action: str, server_name: str) -> None:
    """Update and persist a server's enabled state, then record the change.
    
    Parameters:
    	action (str): The requested action: ``"enable"``, ``"disable"``, or ``"toggle"``.
    	server_name (str): The name of the server to update.
    """
    source = get_source(server_name)
    if not source:
        _print_err(f"unknown server: {server_name}")
        return

    settings = load_settings()
    if action == "enable":
        settings.set_server_enabled(server_name, True)
    elif action == "disable":
        settings.set_server_enabled(server_name, False)
    elif action == "toggle":
        current = settings.is_server_enabled(server_name, default=True)
        settings.set_server_enabled(server_name, not current)
    save_settings(settings)
    record_server_toggle(server_name, action, settings.is_server_enabled(server_name))
    _print_ok(f"{server_name}: {action}d")


def _print_ok(msg: str) -> None:
    """Print a success message with a colored status label."""
    print(f"  {GREEN}ok{RESET} {msg}")


def _print_err(msg: str) -> None:
    """Print an error message with terminal formatting."""
    print(f"  {RED}err{RESET} {msg}")


def _print_help() -> None:
    """Print the available interactive commands and their descriptions."""
    print(f"  {BOLD}commands{RESET}")
    rows = (
        ("toggle <server>", "Toggle a server on/off"),
        ("enable <server>", "Enable a server"),
        ("disable <server>", "Disable a server"),
        ("profile <name>", "Switch active profile"),
        ("browser", "List browser sessions"),
        ("auto", "List automations"),
        ("status", "Refresh display"),
        ("clear", "Clear telemetry data"),
        ("quit", "Exit interactive mode"),
    )
    for cmd, desc in rows:
        print(f"    {cmd:<18} {DIM}{desc}{RESET}")
