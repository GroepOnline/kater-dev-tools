from __future__ import annotations

import os
import shlex
import sys
import time


def _clear() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _move(row: int, col: int = 1) -> None:
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


def _hide_cursor() -> None:
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def _show_cursor() -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def interactive_loop(
    profile: str = "core",
    refresh_interval: float = 3.0,
) -> None:
    from kater.ansi import DIM, RESET
    from kater.profiles import list_profiles

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

            sys.stdout.write(
                f"\n{DIM}> {RESET}"
            )
            sys.stdout.flush()

            try:
                raw = sys.stdin.readline()
            except (EOFError, KeyboardInterrupt):
                break
            # readline() returns "" at EOF — without this guard the loop would
            # spin forever burning CPU once stdin closes (e.g. piped input end).
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
                    time.sleep(1)
            elif cmd in ("toggle", "enable", "disable") and len(parts) > 1:
                _handle_toggle(parts[0], parts[1])
                refresh_needed = True
            elif cmd == "status":
                refresh_needed = True
            elif cmd == "help":
                _print_help()
                time.sleep(2)
                refresh_needed = True
            elif cmd == "clear":
                from kater.telemetry import clear_events
                count = clear_events()
                _print_ok(f"cleared {count} events")
                time.sleep(1)
                refresh_needed = True
            else:
                _print_err(f"unknown: {line} (type 'help')")
                time.sleep(1)

    finally:
        _show_cursor()
        _clear()
        print(f"{DIM}kater interactive stopped.{RESET}")


def _render(profile: str) -> None:
    from kater.ansi import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW
    from kater.telemetry import status_overview

    _clear()

    data = status_overview()
    s = data["servers"]
    t = data["telemetry"]

    print(
        f"{BOLD}KATER{RESET} {DIM}v{data['version']}{RESET}"
        f"  {CYAN}profile:{RESET} {BOLD}{data['profile']}{RESET}"
        f"  {YELLOW}auth:{RESET} {data['auth_mode']}"
        f"  {DIM}storage:{RESET} {data['storage_backend']}"
    )
    print(
        f"{DIM}{'─' * 72}{RESET}"
    )
    print(
        f"  Servers: {GREEN if s['enabled'] == s['total'] else YELLOW}"
        f"{s['enabled']}/{s['total']}{RESET} enabled"
        f"  {DIM}|{RESET}  "
        f"{GREEN if s['configured'] > 0 else RED}{s['configured']}{RESET} configured"
        f"  {DIM}|{RESET}  "
        f"{RED if s['missing_env'] else GREEN}{s['missing_env']}{RESET} missing env"
    )
    print(
        f"  Events: {t['total_events']} total"
        f"  {DIM}|{RESET}  "
        f"{t['tool_calls']} calls"
        f"  {DIM}|{RESET}  "
        f"{t['errors']} errors"
        f"  {DIM}|{RESET}  "
        f"{'{:.1f}'.format(t['success_rate'])}% success"
    )
    print(f"{DIM}{'─' * 72}{RESET}")

    from kater.profiles import TOOL_SOURCES
    from kater.settings import load_settings
    settings = load_settings()

    print(f"  {BOLD}SERVER STATUS{RESET}")
    print()

    for source in TOOL_SOURCES:
        if source.transport == "native":
            continue
        if profile not in source.profiles and profile != "core":
            continue

        enabled = settings.is_server_enabled(source.name, default=True)
        env_ok = all(os.environ.get(v) for v in source.env)

        if enabled and env_ok:
            status = f"{GREEN}●{RESET}"
        elif enabled and not env_ok:
            status = f"{YELLOW}○{RESET}"
        else:
            status = f"{RED}✕{RESET}"

        name = source.name.ljust(20)
        transport = source.transport.value.ljust(6)
        risk = source.risk.value

        risk_color = RED if risk == "high" else YELLOW if risk == "medium" else GREEN

        print(
            f"  {status} {name} {DIM}{transport}{RESET} {risk_color}{risk}{RESET}"
        )

    print(f"{DIM}{'─' * 72}{RESET}")
    print(f"  {BOLD}RECENT EVENTS{RESET}")

    from kater.telemetry import load_events
    events = load_events()
    for e in events[-5:]:
        ok = e.get("success", True)
        icon = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        name = e.get("name", "?")[:20]
        dur = e.get("duration_ms", 0)
        print(f"  {icon} {DIM}{e.get('type', ''):<12}{RESET} {name:<20} {dur:>6.1f}ms")

    if not events:
        print(f"  {DIM}(no events){RESET}")

    print(f"{DIM}{'─' * 72}{RESET}")
    print(f"  {DIM}commands: toggle <name> | enable <name> | disable <name> | "
          f"profile <name> | status | clear | help | quit{RESET}")


def _handle_toggle(action: str, server_name: str) -> None:
    from kater.profiles import get_source
    from kater.settings import load_settings, save_settings
    from kater.telemetry import record_server_toggle

    source = get_source(server_name)
    if not source:
        _print_err(f"unknown server: {server_name}")
        time.sleep(1)
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
    from kater.ansi import GREEN, RESET
    print(f"  {GREEN}✓ {msg}{RESET}")


def _print_err(msg: str) -> None:
    from kater.ansi import RED, RESET
    print(f"  {RED}✗ {msg}{RESET}")


def _print_help() -> None:
    print("  Commands:")
    print("    toggle <server>   Toggle a server on/off")
    print("    enable <server>   Enable a server")
    print("    disable <server>  Disable a server")
    print("    profile <name>    Switch active profile")
    print("    status            Refresh display")
    print("    clear             Clear telemetry data")
    print("    quit              Exit interactive mode")
