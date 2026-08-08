from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "scripts" / "generate_cursor_index.py"
INDEX_MD = ROOT / ".cursor" / "INDEX.md"
SKILLS_INDEX = ROOT / ".cursor" / "skills" / ".index.yaml"
AGENTS_INDEX = ROOT / ".cursor" / "agents" / ".index.yaml"
RULES_INDEX = ROOT / ".cursor" / "rules" / ".index.yaml"
COMMANDS_INDEX = ROOT / ".cursor" / "commands" / ".index.yaml"
HOOKS_INDEX = ROOT / ".cursor" / "hooks" / ".index.yaml"

ORG_HANDLE_RE = re.compile(r"online" + r"chefgroep", re.IGNORECASE)
PROD_DOMAIN_RE = re.compile(r"chefgroep\.(nl|online)", re.IGNORECASE)

EXPECTED_HOOK_EVENTS = {"sessionStart", "beforeSubmitPrompt", "postToolUse", "workspaceOpen"}


def _load_index(path: Path) -> dict:
    assert path.is_file(), f"missing index: {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _assert_no_org_leak(text: str, label: str) -> None:
    assert not PROD_DOMAIN_RE.search(text), f"{label}: org production domain leak"
    assert not ORG_HANDLE_RE.search(text), f"{label}: org handle leak"


def test_generator_runs_clean() -> None:
    proc = subprocess.run(
        ["python3", str(GENERATOR)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "generate_cursor_index: ok" in proc.stdout


def test_generator_check_mode() -> None:
    subprocess.run(["python3", str(GENERATOR)], cwd=ROOT, check=True)
    proc = subprocess.run(
        ["python3", str(GENERATOR), "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "check ok" in proc.stdout


def test_index_lists_skills_and_agents() -> None:
    subprocess.run(["python3", str(GENERATOR)], cwd=ROOT, check=True)

    skills = _load_index(SKILLS_INDEX)
    agents = _load_index(AGENTS_INDEX)
    rules = _load_index(RULES_INDEX)
    commands = _load_index(COMMANDS_INDEX)
    hooks = _load_index(HOOKS_INDEX)

    assert skills["version"] == 1
    assert skills["generated_by"] == "scripts/generate_cursor_index.py"
    assert agents["generated_by"] == skills["generated_by"]
    assert rules["generated_by"] == skills["generated_by"]
    assert commands["generated_by"] == skills["generated_by"]
    assert hooks["generated_by"] == skills["generated_by"]

    skill_names = {item["name"] for item in skills["items"]}
    agent_names = {item["name"] for item in agents["items"]}
    rule_names = {item["name"] for item in rules["items"]}
    command_names = {item["name"] for item in commands["items"]}
    hook_names = {item["name"] for item in hooks["items"]}

    for required in (
        "kater-gateway",
        "pr-gate",
        "kater-dev-tools-create-skill",
        "kater-dev-tools-create-subagent",
        "kater-doctor",
        "kater-e2e",
        "kater-dashboard",
        "kater-dev-tools-local-verify",
        "kater-dev-tools-parallel-lanes",
        "kater-dev-tools-ci-fixer",
    ):
        assert required in skill_names, f"missing skill index entry: {required}"

    for required in ("pr-gate", "kater-verify", "ci-fixer", "parallel-lane"):
        assert required in agent_names, f"missing agent index entry: {required}"

    for required in ("kater-project", "verify-before-claim"):
        assert required in rule_names, f"missing rule index entry: {required}"

    for required in ("kater-dev-tools-local-verify", "kater-gateway", "pr-gate", "kater-dev-tools-ci-fixer"):
        assert required in command_names, f"missing command index entry: {required}"

    assert EXPECTED_HOOK_EVENTS <= hook_names

    for item in (
        skills["items"]
        + agents["items"]
        + rules["items"]
        + commands["items"]
        + hooks["items"]
    ):
        assert item["kind"] in {"skill", "agent", "rule", "command", "hook"}
        assert item["path"].startswith(".cursor/")
        assert item["summary"]
        assert item["when"]


def test_index_md_and_yaml_have_no_org_handles() -> None:
    subprocess.run(["python3", str(GENERATOR)], cwd=ROOT, check=True)

    targets = [
        INDEX_MD,
        SKILLS_INDEX,
        AGENTS_INDEX,
        RULES_INDEX,
        COMMANDS_INDEX,
        HOOKS_INDEX,
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        _assert_no_org_leak(text, str(path.relative_to(ROOT)))

    index_text = INDEX_MD.read_text(encoding="utf-8")
    assert "9090" in index_text
    assert "9091" in index_text
    assert "9092" in index_text
    assert "private-cursor-overlay.md" in index_text
    assert "Koppelingen" in index_text
    assert "## Rules" in index_text
    assert "## Commands" in index_text


def test_markdown_cells_escape_pipes_and_backticks() -> None:
    """Frontmatter values cannot break out of their INDEX.md table cell."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("generate_cursor_index", GENERATOR)
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    # Register before exec: the module's dataclasses resolve annotations via
    # sys.modules[cls.__module__].
    sys.modules[spec.name] = gen
    try:
        spec.loader.exec_module(gen)
    finally:
        sys.modules.pop(spec.name, None)

    # A pipe in a summary must not open an extra column.
    assert gen.md_cell("a | b") == "a \\| b"
    # A pipe in a code span still needs escaping inside GFM tables.
    assert gen.md_code_cell("a|b") == "`a\\|b`"
    # Backtick runs widen the fence (and get padded) instead of ending the span.
    assert gen.md_code_cell("a`b") == "``a`b``"
    assert gen.md_code_cell("`b`") == "`` `b` ``"

    row = gen.markdown_table(
        ["Name", "Summary"],
        [[gen.md_code_cell("we|ird`name"), gen.md_cell("pipe | in summary")]],
    ).splitlines()[-1]
    # Two cells means exactly three unescaped delimiters on the row.
    assert len(re.findall(r"(?<!\\)\|", row)) == 3, row
