from __future__ import annotations

import sys

_USE_COLOR = sys.stdout.isatty()

RESET = "\033[0m" if _USE_COLOR else ""
BOLD = "\033[1m" if _USE_COLOR else ""
DIM = "\033[2m" if _USE_COLOR else ""
RED = "\033[31m" if _USE_COLOR else ""
GREEN = "\033[32m" if _USE_COLOR else ""
YELLOW = "\033[33m" if _USE_COLOR else ""
BLUE = "\033[34m" if _USE_COLOR else ""
MAGENTA = "\033[35m" if _USE_COLOR else ""
CYAN = "\033[36m" if _USE_COLOR else ""
GRAY = "\033[90m" if _USE_COLOR else ""
BG_BLUE = "\033[44m" if _USE_COLOR else ""

_MAX_COL_WIDTH = 40


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def success(text: str) -> str:
    return colorize(text, GREEN)


def error(text: str) -> str:
    return colorize(text, RED)


def warning(text: str) -> str:
    return colorize(text, YELLOW)


def info(text: str) -> str:
    return colorize(text, CYAN)


def dim(text: str) -> str:
    return colorize(text, DIM)


class Table:
    def __init__(self, headers: list[str], title: str | None = None):
        self.headers = headers
        self.title = title
        self.rows: list[list[str]] = []

    def add_row(self, *values: str) -> None:
        self.rows.append([str(value) for value in values])

    def _col_widths(self) -> list[int]:
        widths = [len(header) for header in self.headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(cell))
        return [min(width, _MAX_COL_WIDTH) for width in widths]

    @staticmethod
    def _truncate(value: str, width: int) -> str:
        return value if len(value) <= width else value[:width]

    def _border(self, widths: list[int], left: str, mid: str, right: str) -> str:
        cells = ["─" * (width + 2) for width in widths]
        return f"{left}{mid.join(cells)}{right}"

    def render(self) -> str:
        widths = self._col_widths()
        total_width = (len(widths) + 1) + sum(width + 2 for width in widths)
        lines: list[str] = []

        if self.title:
            lines.append(f"{BOLD}{self.title.center(total_width)}{RESET}")

        lines.append(self._border(widths, "┌", "┬", "┐"))

        header_parts = ["│"]
        for i, width in enumerate(widths):
            text = self._truncate(self.headers[i] if i < len(self.headers) else "", width).ljust(
                width
            )
            header_parts.append(f" {BOLD}{text}{RESET} ")
            header_parts.append("│")
        lines.append("".join(header_parts))

        if self.rows:
            lines.append(self._border(widths, "├", "┼", "┤"))

        for row in self.rows:
            row_parts = ["│"]
            for i, width in enumerate(widths):
                cell = self._truncate(row[i] if i < len(row) else "", width).ljust(width)
                row_parts.append(f" {cell} ")
                row_parts.append("│")
            lines.append("".join(row_parts))

        lines.append(self._border(widths, "└", "┴", "┘"))
        return "\n".join(lines)


def banner(title: str, subtitle: str | None = None) -> str:
    content = [title] + ([subtitle] if subtitle else [])
    inner = max(len(line) for line in content) + 6
    slot = inner - 2
    lines = [
        f"╔{'═' * inner}╗",
        f"║  {title.ljust(slot)}║",
    ]
    if subtitle:
        lines.append(f"║  {subtitle.ljust(slot)}║")
    lines.append(f"╚{'═' * inner}╝")
    return "\n".join(lines)


def kv_grid(items: list[tuple[str, str]], indent: int = 2) -> str:
    if not items:
        return ""
    key_width = max(len(key) for key, _ in items)
    pad = " " * indent
    lines = []
    for key, value in items:
        label = f"{key}:".ljust(key_width + 5)
        lines.append(f"{pad}{label}{value}")
    return "\n".join(lines)


def bar(
    current: int,
    total: int,
    width: int = 20,
    fill_color: str = GREEN,
) -> str:
    if total <= 0:
        ratio = 0.0
    else:
        ratio = min(max(current / total, 0.0), 1.0)
    filled = round(ratio * width)
    empty = width - filled
    pct = round(ratio * 100)
    bar_str = f"{fill_color}{'█' * filled}{RESET}{'░' * empty}"
    return f"[{bar_str}] {pct}%"
