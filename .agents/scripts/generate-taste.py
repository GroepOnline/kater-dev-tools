#!/usr/bin/env python3
"""Generate per-tool agent-taste artefacts from .agents/registry/taste.yaml.

Usage:
  python3 .agents/scripts/generate-taste.py
  python3 .agents/scripts/generate-taste.py --target /path/to/consumer-repo
  python3 .agents/scripts/generate-taste.py --target /path/to/consumer-repo --check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
REG = SOURCE_ROOT / ".agents" / "registry"
TASTE = REG / "taste.yaml"
HDR = "GENERATED from .agents/registry/taste.yaml - do not edit by hand"


def _need_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        sys.exit(
            "PyYAML required: install it with `uv sync --dev` (or "
            "`pip install pyyaml`), then re-run "
            "`uv run python .agents/scripts/generate-taste.py`"
        )


def load_overlays(target_root: Path) -> list[dict]:
    """Load the per-tool overlays that declare output path, format and markers."""
    yaml = _need_yaml()
    paths = sorted(REG.glob("taste.overlay.*.yaml"))
    if not paths:
        sys.exit(f"no taste overlays found in {REG}")
    overlays = []
    for path in paths:
        ov = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(ov, dict):
            sys.exit(f"invalid overlay: {path}")
        tool = ov.get("tool")
        out = ov.get("output_path")
        fmt = ov.get("format")
        if not tool or not out:
            sys.exit(f"overlay missing tool/output_path: {path}")
        if fmt not in SUPPORTED_FORMATS:
            sys.exit(f"overlay {path}: unsupported format {fmt!r}")
        target = (target_root / out).resolve()
        if not target.is_relative_to(target_root):
            sys.exit(f"overlay {path}: output_path escapes repo root: {out}")
        if fmt == MARKER_FORMAT and not (
            ov.get("marker_start") and ov.get("marker_end")
        ):
            sys.exit(f"overlay {path}: markdown_markers needs marker_start/marker_end")
        overlays.append(ov)
    return overlays


def load_taste() -> dict:
    yaml = _need_yaml()
    data = yaml.safe_load(TASTE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rules" not in data:
        sys.exit(f"invalid taste.yaml: {TASTE}")
    return data


def rules_for(tool: str, data: dict) -> list[dict]:
    out = []
    for r in data.get("rules") or []:
        applies = r.get("applies_to", "all")
        if applies == "all" or applies is None:
            out.append(r)
        elif isinstance(applies, list) and tool in applies:
            out.append(r)
    return out


def bullets(rules: list[dict]) -> str:
    lines = []
    for r in rules:
        text = (r.get("text") or "").strip()
        rid = r.get("id") or "rule"
        if not text:
            continue
        lines.append(f"- {text} `{rid}`")
    return "\n".join(lines) + ("\n" if lines else "")


def render_cmd(rules: list[dict]) -> str:
    body = bullets(rules)
    return f"# {HDR}\n\n{body}"


def render_cursor_mdc(rules: list[dict]) -> str:
    body = bullets(rules)
    return (
        "---\n"
        "description: Agent-gedrag-taste (generated from kater-dev-tools .agents/registry/taste.yaml)\n"
        "alwaysApply: true\n"
        "---\n\n"
        f"<!-- {HDR} -->\n\n"
        "# Agent taste\n\n"
        f"{body}"
    )


def render_markers_section(rules: list[dict], start: str, end: str) -> str:
    body = bullets(rules)
    return (
        f"{start}\n"
        f"<!-- {HDR} -->\n\n"
        "## Agent taste\n\n"
        f"{body}"
        f"{end}\n"
    )


MARKER_FORMAT = "markdown_markers"
# Formats that render a standalone generated file; MARKER_FORMAT patches
# a section into a hand-written file instead.
RENDERERS = {
    "markdown_bullets": render_cmd,
    "cursor_mdc": render_cursor_mdc,
}
SUPPORTED_FORMATS = {MARKER_FORMAT, *RENDERERS}


def upsert_markers(path: Path, section: str, start: str, end: str) -> str:
    if path.exists():
        raw = path.read_text(encoding="utf-8")
    else:
        raw = ""
    starts = raw.count(start)
    ends = raw.count(end)
    if starts or ends:
        # Exactly one pair, in order. Anything else (missing, stray or
        # duplicated delimiter) would leave managed-section delimiters behind
        # after substitution, and --check would report no drift on a file that
        # is already corrupt.
        if starts != 1 or ends != 1:
            sys.exit(
                f"malformed taste markers in {path}: expected exactly one "
                f"{start} and one {end}, found {starts} and {ends}"
            )
        head = raw.index(start)
        tail = raw.index(end) + len(end)
        if head > tail:
            sys.exit(f"malformed taste markers in {path}: {end} occurs before {start}")
        return raw[:head] + section.rstrip("\n") + raw[tail:]
    if raw and not raw.endswith("\n"):
        raw += "\n"
    return raw + ("\n" if raw else "") + section


def display_path(path: Path, target_root: Path) -> str:
    try:
        return str(path.relative_to(target_root))
    except ValueError:
        return str(path)


def write_or_check(path: Path, content: str, check: bool, target_root: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if check:
        if not path.exists():
            print(f"MISSING {display_path(path, target_root)}")
            return False
        cur = path.read_text(encoding="utf-8")
        if cur != content:
            print(f"DRIFT   {display_path(path, target_root)}")
            return False
        print(f"OK      {display_path(path, target_root)}")
        return True
    path.write_text(content, encoding="utf-8")
    print(f"WROTE   {display_path(path, target_root)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if artefacts drift")
    ap.add_argument(
        "--target",
        type=Path,
        default=SOURCE_ROOT,
        help="consumer repo root (default: kater-dev-tools)",
    )
    args = ap.parse_args()
    target_root = args.target.expanduser().resolve()
    if not target_root.is_dir():
        sys.exit(f"target repo does not exist: {target_root}")
    data = load_taste()
    ok = True

    for ov in load_overlays(target_root):
        path = target_root / ov["output_path"]
        rules = rules_for(ov["tool"], data)
        fmt = ov["format"]
        if fmt == MARKER_FORMAT:
            # Marker targets are hand-written outside the markers, so the
            # expected content is the current file with the section
            # substituted. That keeps --check a full content comparison and
            # flags a stale section or a missing end marker as drift.
            section = render_markers_section(
                rules, ov["marker_start"], ov["marker_end"]
            )
            content = upsert_markers(
                path, section, ov["marker_start"], ov["marker_end"]
            )
        else:
            content = RENDERERS[fmt](rules)
        ok &= write_or_check(path, content, args.check, target_root)

    if args.check and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
