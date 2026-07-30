#!/usr/bin/env python3
"""Regenerate Cursor control-plane indexes from the filesystem.

Reads skill/agent/rule YAML frontmatter and `.cursor/hooks.json`, then writes:
  - `.cursor/skills/.index.yaml`
  - `.cursor/agents/.index.yaml`
  - `.cursor/rules/.index.yaml`
  - `.cursor/hooks/.index.yaml`
  - `.cursor/INDEX.md`
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GENERATOR = "scripts/generate_cursor_index.py"
INDEX_VERSION = 1
WHEN_MAX = 60

PROD_DOMAIN_RE = re.compile(r"chefgroep\.(nl|online)", re.IGNORECASE)
ORG_HANDLE_RE = re.compile(r"online" + r"chefgroep", re.IGNORECASE)

HOOK_SUMMARIES: dict[str, tuple[str, str]] = {
    "sessionStart": (
        "Inject artifact catalog at session start",
        "sessionStart → fetch-cursor-artifacts.sh injects catalog + hash",
    ),
    "beforeSubmitPrompt": (
        "Allow prompt submission without catalog inject",
        "beforeSubmitPrompt → continue only (schema cannot inject here)",
    ),
    "postToolUse": (
        "Inject catalog once per conversation (cloud cold-start substitute)",
        "postToolUse → first tool use injects catalog; later calls dedupe",
    ),
    "workspaceOpen": (
        "Register `.cursor/plugins` paths when workspace opens",
        "workspaceOpen → returns pluginPaths for Cursor plugin discovery",
    ),
}


@dataclass(frozen=True)
class IndexItem:
    name: str
    path: str
    kind: str
    summary: str
    when: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "path": self.path,
            "kind": self.kind,
            "summary": self.summary,
            "when": self.when,
        }


def repo_root(start: Path | None = None) -> Path:
    root = start or Path(__file__).resolve().parent.parent
    return root


def truncate(text: str, limit: int = WHEN_MAX) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def assert_no_org_leak(text: str, label: str) -> None:
    if PROD_DOMAIN_RE.search(text):
        raise ValueError(f"{label}: org production domain in generated output")
    if ORG_HANDLE_RE.search(text):
        raise ValueError(f"{label}: org handle in generated output")


def parse_frontmatter(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}
    meta = yaml.safe_load(parts[1])
    return meta if isinstance(meta, dict) else {}


def first_line_summary(description: str) -> str:
    text = " ".join(description.split())
    if not text:
        return ""
    first = text.split(". ", 1)[0]
    if not first.endswith("."):
        first = first.rstrip(".") + "."
    return first


def collect_skills(root: Path) -> list[IndexItem]:
    skills_dir = root / ".cursor" / "skills"
    items: list[IndexItem] = []
    if not skills_dir.is_dir():
        return items
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        meta = parse_frontmatter(skill_md)
        name = str(meta.get("name") or skill_md.parent.name)
        description = str(meta.get("description") or "").strip()
        summary = first_line_summary(description) or f"Skill `{name}`."
        rel = skill_md.relative_to(root).as_posix()
        items.append(
            IndexItem(
                name=name,
                path=rel,
                kind="skill",
                summary=summary,
                when=truncate(description or summary),
            )
        )
    return items


def collect_rules(root: Path) -> list[IndexItem]:
    rules_dir = root / ".cursor" / "rules"
    items: list[IndexItem] = []
    if not rules_dir.is_dir():
        return items
    for rule_mdc in sorted(rules_dir.glob("*.mdc")):
        meta = parse_frontmatter(rule_mdc)
        name = str(meta.get("name") or rule_mdc.stem)
        description = str(meta.get("description") or "").strip()
        always_apply = meta.get("alwaysApply")
        summary = first_line_summary(description) or f"Rule `{name}`."
        when_parts: list[str] = []
        if always_apply is True:
            when_parts.append("alwaysApply")
        if description:
            when_parts.append(description)
        when_text = " — ".join(when_parts) if when_parts else summary
        rel = rule_mdc.relative_to(root).as_posix()
        items.append(
            IndexItem(
                name=name,
                path=rel,
                kind="rule",
                summary=summary,
                when=truncate(when_text),
            )
        )
    return items


def collect_commands(root: Path) -> list[IndexItem]:
    commands_dir = root / ".cursor" / "commands"
    items: list[IndexItem] = []
    if not commands_dir.is_dir():
        return items
    for command_md in sorted(commands_dir.glob("*.md")):
        meta = parse_frontmatter(command_md)
        name = str(meta.get("name") or command_md.stem)
        description = str(meta.get("description") or "").strip()
        summary = first_line_summary(description) or f"Slash command `/{name}`."
        rel = command_md.relative_to(root).as_posix()
        items.append(
            IndexItem(
                name=name,
                path=rel,
                kind="command",
                summary=summary,
                when=truncate(description or summary),
            )
        )
    return items


def collect_agents(root: Path) -> list[IndexItem]:
    agents_dir = root / ".cursor" / "agents"
    items: list[IndexItem] = []
    if not agents_dir.is_dir():
        return items
    for agent_md in sorted(agents_dir.glob("*.md")):
        meta = parse_frontmatter(agent_md)
        name = str(meta.get("name") or agent_md.stem)
        description = str(meta.get("description") or "").strip()
        summary = first_line_summary(description) or f"Subagent `{name}`."
        rel = agent_md.relative_to(root).as_posix()
        items.append(
            IndexItem(
                name=name,
                path=rel,
                kind="agent",
                summary=summary,
                when=truncate(description or summary),
            )
        )
    return items


def collect_hooks(root: Path) -> list[IndexItem]:
    hooks_json = root / ".cursor" / "hooks.json"
    if not hooks_json.is_file():
        return []
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    hooks = data.get("hooks") or {}
    items: list[IndexItem] = []
    for event in sorted(hooks.keys()):
        summary, when = HOOK_SUMMARIES.get(
            event,
            (f"Hook event `{event}`", f"Hook event `{event}` via hooks.json"),
        )
        items.append(
            IndexItem(
                name=event,
                path=".cursor/hooks.json",
                kind="hook",
                summary=summary,
                when=truncate(when),
            )
        )
    return items


def write_index_yaml(path: Path, items: list[IndexItem]) -> None:
    payload = {
        "version": INDEX_VERSION,
        "generated_by": GENERATOR,
        "items": [item.as_dict() for item in items],
    }
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    assert_no_org_leak(rendered, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def md_cell(value: str) -> str:
    """Escape a plain-text value so it stays inside one Markdown table cell."""
    return value.replace("|", "\\|")


def md_code_cell(value: str) -> str:
    """Render a value as an inline code span that survives a Markdown table.

    A raw ``|`` would open an extra column (escaped even inside code spans per
    GFM), and a backtick run equal to the fence would end the span early, so the
    fence is widened past the longest run in the value.
    """
    escaped = value.replace("|", "\\|")
    longest_run = max((len(run) for run in re.findall(r"`+", escaped)), default=0)
    fence = "`" * (longest_run + 1)
    pad = " " if escaped.startswith("`") or escaped.endswith("`") else ""
    return f"{fence}{pad}{escaped}{pad}{fence}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_index_md(
    root: Path,
    skills: list[IndexItem],
    agents: list[IndexItem],
    rules: list[IndexItem],
    commands: list[IndexItem],
    hooks: list[IndexItem],
) -> str:
    def rows_for(items: list[IndexItem], prefix: str = "") -> list[list[str]]:
        return [
            [
                md_code_cell(f"{prefix}{i.name}"),
                md_code_cell(i.path),
                md_cell(i.summary),
            ]
            for i in items
        ]

    skill_rows = rows_for(skills)
    agent_rows = rows_for(agents)
    rule_rows = rows_for(rules)
    command_rows = rows_for(commands, prefix="/")
    hook_rows = rows_for(hooks)

    parts = [
        "# Cursor control plane index",
        "",
        (
            "> Auto-generated by `scripts/generate_cursor_index.py`."
            " Regenerate instead of hand-editing."
        ),
        "",
        "## Environment",
        "",
        "| Item | Value |",
        "| --- | --- |",
        "| MCP SSE | `:9090` (`/sse`) |",
        "| REST / dashboard / health | `:9091` |",
        "| WebSocket telemetry | `:9092` |",
        "| Profiles | `core` (cloud-safe, no proxy), `ops` (dev backends) |",
        "| Smoke (server stopped) | `./scripts/smoke.sh` |",
        "| E2E MCP (server running) | `./scripts/e2e-mcp.sh` |",
        (
            "| Pre-commit | `uvx pre-commit install` — ruff, mypy, gitleaks,"
            " `no-org-leak`, `cursor-index` |"
        ),
        "| Cloud env | `.cursor/environment.json` |",
        "",
        "## Skills",
        "",
        (
            markdown_table(["Name", "Path", "Summary"], skill_rows)
            if skill_rows
            else "_No skills found._"
        ),
        "",
        "## Agents",
        "",
        (
            markdown_table(["Name", "Path", "Summary"], agent_rows)
            if agent_rows
            else "_No agents found._"
        ),
        "",
        "## Rules",
        "",
        (
            markdown_table(["Name", "Path", "Summary"], rule_rows)
            if rule_rows
            else "_No rules found._"
        ),
        "",
        "## Commands",
        "",
        (
            markdown_table(["Slash", "Path", "Summary"], command_rows)
            if command_rows
            else "_No commands found._"
        ),
        "",
        "## Hooks",
        "",
        (
            markdown_table(["Event", "Path", "Summary"], hook_rows)
            if hook_rows
            else "_No hooks found._"
        ),
        "",
        "## Koppelingen",
        "",
        "- **Cursor MCP** — `.cursor/mcp.json` → SSE `:9090/sse`",
        "- **REST / dashboard** — `:9091` (`/health`, `/dashboard`, `/api/*`)",
        "- **WebSocket telemetry** — `:9092`",
        (
            "- **Private overlay** — org-pinned skills/agents belong in the"
            " deployment overlay; see `docs/ops/private-cursor-overlay.md`"
        ),
        "",
        "## Regenerate",
        "",
        "```bash",
        "python3 scripts/generate_cursor_index.py",
        "```",
        "",
    ]
    text = "\n".join(parts)
    assert_no_org_leak(text, ".cursor/INDEX.md")
    return text


INDEX_PATHS = (
    Path(".cursor/INDEX.md"),
    Path(".cursor/skills/.index.yaml"),
    Path(".cursor/agents/.index.yaml"),
    Path(".cursor/rules/.index.yaml"),
    Path(".cursor/commands/.index.yaml"),
    Path(".cursor/hooks/.index.yaml"),
)


def generate(root: Path | None = None) -> dict[str, int]:
    repo = repo_root(root)
    skills = collect_skills(repo)
    agents = collect_agents(repo)
    rules = collect_rules(repo)
    commands = collect_commands(repo)
    hooks = collect_hooks(repo)

    write_index_yaml(repo / ".cursor" / "skills" / ".index.yaml", skills)
    write_index_yaml(repo / ".cursor" / "agents" / ".index.yaml", agents)
    write_index_yaml(repo / ".cursor" / "rules" / ".index.yaml", rules)
    write_index_yaml(repo / ".cursor" / "commands" / ".index.yaml", commands)
    write_index_yaml(repo / ".cursor" / "hooks" / ".index.yaml", hooks)

    index_md = render_index_md(repo, skills, agents, rules, commands, hooks)
    (repo / ".cursor" / "INDEX.md").write_text(index_md, encoding="utf-8")

    return {
        "skills": len(skills),
        "agents": len(agents),
        "rules": len(rules),
        "commands": len(commands),
        "hooks": len(hooks),
    }


def check(root: Path | None = None) -> None:
    """Regenerate in a temp tree and fail if committed indexes are stale."""
    repo = repo_root(root)
    with tempfile.TemporaryDirectory(prefix="cursor-index-check-") as tmp:
        tmp_root = Path(tmp)
        cursor_src = repo / ".cursor"
        cursor_dst = tmp_root / ".cursor"
        shutil.copytree(
            cursor_src,
            cursor_dst,
            ignore=shutil.ignore_patterns(".state", "__pycache__"),
        )
        generate(tmp_root)

        for rel in INDEX_PATHS:
            expected = (tmp_root / rel).read_text(encoding="utf-8")
            actual_path = repo / rel
            if not actual_path.is_file():
                raise ValueError(f"missing index: {rel} (run generate_cursor_index.py)")
            actual = actual_path.read_text(encoding="utf-8")
            if actual != expected:
                raise ValueError(
                    f"stale index: {rel} — run: python3 scripts/generate_cursor_index.py"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed indexes do not match a fresh generate",
    )
    args = ap.parse_args()
    try:
        if args.check:
            check(args.root)
            print("generate_cursor_index: check ok")
            return 0
        counts = generate(args.root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"generate_cursor_index: error: {exc}", file=sys.stderr)
        return 1
    print(
        "generate_cursor_index: ok — "
        f"skills={counts['skills']} agents={counts['agents']} "
        f"rules={counts['rules']} commands={counts['commands']} "
        f"hooks={counts['hooks']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
