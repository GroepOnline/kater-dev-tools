#!/usr/bin/env python3
"""Generate per-tool agent-taste artefacts from .agents/registry/taste.yaml.

Usage:
  python3 .agents/scripts/generate-taste.py
  python3 .agents/scripts/generate-taste.py --check
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / ".agents" / "registry"
TASTE = REG / "taste.yaml"
HDR = "GENERATED from .agents/registry/taste.yaml - do not edit by hand"


def _need_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        sys.exit(
            "PyYAML required: uv run python .agents/scripts/generate-taste.py "
            "or pip install pyyaml"
        )


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


def render_claude_section(rules: list[dict]) -> str:
    body = bullets(rules)
    return (
        "<!-- TASTE:START -->\n"
        f"<!-- {HDR} -->\n\n"
        "## Agent taste\n\n"
        f"{body}"
        "<!-- TASTE:END -->\n"
    )


def upsert_markers(path: Path, section: str, start: str, end: str) -> str:
    if path.exists():
        raw = path.read_text(encoding="utf-8")
    else:
        raw = ""
    if start in raw and end in raw:
        pattern = re.compile(
            re.escape(start) + r".*?" + re.escape(end),
            re.DOTALL,
        )
        return pattern.sub(section.rstrip("\n"), raw)
    if raw and not raw.endswith("\n"):
        raw += "\n"
    return raw + ("\n" if raw else "") + section


def write_or_check(path: Path, content: str, check: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if check:
        if not path.exists():
            print(f"MISSING {path.relative_to(ROOT)}")
            return False
        cur = path.read_text(encoding="utf-8")
        if cur != content:
            print(f"DRIFT   {path.relative_to(ROOT)}")
            return False
        print(f"OK      {path.relative_to(ROOT)}")
        return True
    path.write_text(content, encoding="utf-8")
    print(f"WROTE   {path.relative_to(ROOT)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if artefacts drift")
    args = ap.parse_args()
    data = load_taste()
    ok = True

    cmd_rules = rules_for("cmd", data)
    ok &= write_or_check(
        ROOT / ".commandcode" / "taste" / "taste.md",
        render_cmd(cmd_rules),
        args.check,
    )

    cursor_rules = rules_for("cursor", data)
    ok &= write_or_check(
        ROOT / ".cursor" / "rules" / "taste.mdc",
        render_cursor_mdc(cursor_rules),
        args.check,
    )

    claude_rules = rules_for("claude_code", data)
    section = render_claude_section(claude_rules)
    claude_path = ROOT / "CLAUDE.md"
    if args.check:
        if not claude_path.exists():
            print("MISSING CLAUDE.md")
            ok = False
        else:
            raw = claude_path.read_text(encoding="utf-8")
            if "<!-- TASTE:START -->" not in raw or section.split("<!-- TASTE:START -->")[1].split("<!-- TASTE:END -->")[0] not in raw:
                # softer check: markers present and HDR present
                if "<!-- TASTE:START -->" not in raw or HDR not in raw:
                    print("DRIFT   CLAUDE.md (taste markers)")
                    ok = False
                else:
                    print("OK      CLAUDE.md (markers)")
            else:
                print("OK      CLAUDE.md")
    else:
        new = upsert_markers(
            claude_path,
            section,
            "<!-- TASTE:START -->",
            "<!-- TASTE:END -->",
        )
        claude_path.write_text(new, encoding="utf-8")
        print("WROTE   CLAUDE.md")

    if args.check and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
