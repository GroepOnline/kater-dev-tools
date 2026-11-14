#!/usr/bin/env python3
"""Generate deterministic per-toolkit SVG logos for the catalog.

Produces one 64x64 SVG per `ToolSource` in `visible_tool_sources()`:
  studio/public/assets/logos/<source.name>.svg

Each SVG is a rounded gradient background with the toolkit's initials
(centered, white, bold) so the dashboard and Studio can render a
mark without depending on a network round-trip.

Running the script twice yields byte-identical files; `--check` exits
non-zero on drift.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from kater.profiles import Category, visible_tool_sources

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

CATEGORY_GRADIENTS: dict[Category, tuple[str, str]] = {
    Category.DEV: ("#2dd4bf", "#0f766e"),
    Category.CRM: ("#a78bfa", "#6d28d9"),
    Category.COMMS: ("#60a5fa", "#2563eb"),
    Category.AI: ("#f472b6", "#be185d"),
    Category.DATA: ("#fbbf24", "#b45309"),
    Category.INFRA: ("#34d399", "#047857"),
    Category.PRODUCTIVITY: ("#c084fc", "#7e22ce"),
}

DEFAULT_GRADIENT = ("#94a3b8", "#475569")


def initials(name: str) -> str:
    parts = [p for p in name.replace("_", "-").split("-") if p]
    letters: list[str] = []
    for part in parts:
        if not part:
            continue
        letters.append(part[0].upper())
        if len(letters) == 2:
            break
    return "".join(letters)[:2] or "?"


def _gradient_id(name: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in name)
    return f"grad-{safe}"


def render_svg(name: str, initials_text: str, gradient_id: str, start: str, end: str) -> str:
    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "viewBox": "0 0 64 64",
            "width": "64",
            "height": "64",
        },
    )
    defs = ET.SubElement(svg, f"{{{SVG_NS}}}defs")
    grad = ET.SubElement(
        defs,
        f"{{{SVG_NS}}}linearGradient",
        {
            "id": gradient_id,
            "x1": "0",
            "y1": "0",
            "x2": "1",
            "y2": "1",
        },
    )
    ET.SubElement(
        grad,
        f"{{{SVG_NS}}}stop",
        {"offset": "0%", "stop-color": start},
    )
    ET.SubElement(
        grad,
        f"{{{SVG_NS}}}stop",
        {"offset": "100%", "stop-color": end},
    )
    ET.SubElement(
        svg,
        f"{{{SVG_NS}}}rect",
        {
            "width": "64",
            "height": "64",
            "rx": "12",
            "ry": "12",
            "fill": f"url(#{gradient_id})",
        },
    )
    ET.SubElement(
        svg,
        f"{{{SVG_NS}}}text",
        {
            "x": "32",
            "y": "40",
            "text-anchor": "middle",
            "font-family": "Inter, sans-serif",
            "font-size": "28",
            "font-weight": "bold",
            "fill": "#fff",
        },
    ).text = initials_text
    ET.indent(svg, space="  ")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(svg, encoding="unicode")
    )


def _gradients_for(category: Category) -> tuple[str, str]:
    return CATEGORY_GRADIENTS.get(category, DEFAULT_GRADIENT)


def generate(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in visible_tool_sources():
        start, end = _gradients_for(source.category)
        svg = render_svg(
            source.name,
            initials(source.name),
            _gradient_id(source.name),
            start,
            end,
        )
        target = out_dir / f"{source.name}.svg"
        target.write_text(svg, encoding="utf-8")
        written.append(target)
    return written


def check(out_dir: Path) -> int:
    if not out_dir.exists():
        print(f"--check: directory missing: {out_dir}", file=sys.stderr)
        return 1
    drift: list[str] = []
    for source in visible_tool_sources():
        start, end = _gradients_for(source.category)
        expected = render_svg(
            source.name,
            initials(source.name),
            _gradient_id(source.name),
            start,
            end,
        )
        target = out_dir / f"{source.name}.svg"
        if not target.exists():
            drift.append(f"missing: {target}")
            continue
        actual = target.read_text(encoding="utf-8")
        if actual != expected:
            drift.append(f"drift: {target}")
    if drift:
        for line in drift:
            print(line, file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("studio/public/assets/logos"),
        help="output directory for SVG files (lives under Vite publicDir: studio/public)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing files match the deterministic output",
    )
    args = parser.parse_args(argv)
    if args.check:
        return check(args.out)
    written = generate(args.out)
    print(f"wrote {len(written)} logos to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())