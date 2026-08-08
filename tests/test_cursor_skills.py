"""Tests for the Cursor skills/agent artifacts added by this PR.

Validates YAML frontmatter and required body sections for
`.cursor/skills/*/SKILL.md` and `.cursor/agents/*.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".cursor/skills"
AGENTS_DIR = ROOT / ".cursor/agents"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)

EXPECTED_SKILLS = {
    "kater-dev-tools-ci-fixer",
    "kater-dev-tools-create-skill",
    "kater-dev-tools-create-subagent",
    "kater-dashboard",
    "kater-doctor",
    "kater-e2e",
    "kater-gateway",
    "kater-dev-tools-local-verify",
    "kater-dev-tools-parallel-lanes",
    "pr-gate",
}
EXPECTED_AGENTS = {"ci-fixer", "kater-verify", "parallel-lane", "pr-gate"}


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    assert match, f"{path} is missing YAML frontmatter delimited by '---'"
    frontmatter = yaml.safe_load(match.group(1))
    body = text[match.end() :]
    return frontmatter, body


def _skill_paths() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _agent_paths() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md"))


def test_expected_skills_and_agents_exist() -> None:
    skill_names = {p.parent.name for p in _skill_paths()}
    agent_names = {p.stem for p in _agent_paths()}
    assert skill_names == EXPECTED_SKILLS
    assert agent_names == EXPECTED_AGENTS


@pytest.mark.parametrize("skill_path", _skill_paths(), ids=lambda p: p.parent.name)
def test_skill_frontmatter_name_matches_folder(skill_path: Path) -> None:
    frontmatter, _ = _parse_frontmatter(skill_path)
    assert frontmatter["name"] == skill_path.parent.name


@pytest.mark.parametrize("skill_path", _skill_paths(), ids=lambda p: p.parent.name)
def test_skill_frontmatter_has_nonempty_description(skill_path: Path) -> None:
    frontmatter, _ = _parse_frontmatter(skill_path)
    description = frontmatter.get("description")
    assert isinstance(description, str)
    assert description.strip()


def test_meta_scaffolding_skills_are_satellites() -> None:
    # mesh-satellites: model-invocable (ambient true), chained naar skill-creator
    for name in ("kater-dev-tools-create-skill", "kater-dev-tools-create-subagent"):
        path = SKILLS_DIR / name / "SKILL.md"
        frontmatter, _ = _parse_frontmatter(path)
        assert frontmatter.get("role") == "satellite"
        assert frontmatter.get("extends") == "skill-creator"
        assert frontmatter.get("ambient") is True


def test_workflow_skills_do_not_disable_model_invocation() -> None:
    for name in ("kater-gateway", "pr-gate"):
        path = SKILLS_DIR / name / "SKILL.md"
        frontmatter, _ = _parse_frontmatter(path)
        assert "disable-model-invocation" not in frontmatter


def test_pr_gate_skill_and_agent_are_cross_linked() -> None:
    skill_path = SKILLS_DIR / "pr-gate" / "SKILL.md"
    _, skill_body = _parse_frontmatter(skill_path)
    assert ".cursor/agents/pr-gate.md" in skill_body

    agent_path = AGENTS_DIR / "pr-gate.md"
    frontmatter, body = _parse_frontmatter(agent_path)
    assert frontmatter["name"] == "pr-gate"


def test_ci_fixer_skill_and_agent_are_cross_linked() -> None:
    skill_path = SKILLS_DIR / "kater-dev-tools-ci-fixer" / "SKILL.md"
    frontmatter, skill_body = _parse_frontmatter(skill_path)
    assert frontmatter["name"] == "kater-dev-tools-ci-fixer"
    assert ".cursor/agents/ci-fixer.md" in skill_body

    agent_path = AGENTS_DIR / "ci-fixer.md"
    agent_fm, _ = _parse_frontmatter(agent_path)
    assert agent_fm["name"] == "ci-fixer"


def test_parallel_lanes_skill_and_agent_are_cross_linked() -> None:
    skill_path = SKILLS_DIR / "kater-dev-tools-parallel-lanes" / "SKILL.md"
    _, skill_body = _parse_frontmatter(skill_path)
    assert ".cursor/agents/parallel-lane.md" in skill_body

    agent_path = AGENTS_DIR / "parallel-lane.md"
    frontmatter, agent_body = _parse_frontmatter(agent_path)
    assert frontmatter["name"] == "parallel-lane"
    assert ".cursor/skills/kater-dev-tools-parallel-lanes/SKILL.md" in agent_body


def test_pr_gate_agent_frontmatter_fields() -> None:
    agent_path = AGENTS_DIR / "pr-gate.md"
    frontmatter, _ = _parse_frontmatter(agent_path)
    assert frontmatter["name"] == "pr-gate"
    assert frontmatter["model"] == "inherit"
    assert frontmatter["readonly"] is False
    description = frontmatter["description"]
    assert "PR gate" in description


def test_pr_gate_agent_has_mandatory_return_format_section() -> None:
    agent_path = AGENTS_DIR / "pr-gate.md"
    _, body = _parse_frontmatter(agent_path)
    assert "## Return format (mandatory)" in body
    assert "Verdict: PASS|WARN|BLOCK" in body


def test_pr_gate_agent_forbids_unauthorized_merge_or_force_push() -> None:
    agent_path = AGENTS_DIR / "pr-gate.md"
    _, body = _parse_frontmatter(agent_path)
    assert "Never merge, close, or force-push unless the parent prompt explicitly says so." in body
    assert "--force-with-lease" in body


@pytest.mark.parametrize("skill_path", _skill_paths(), ids=lambda p: p.parent.name)
def test_skill_referenced_paths_use_forward_slashes(skill_path: Path) -> None:
    text = skill_path.read_text(encoding="utf-8")
    # Windows-style path separators must never appear in referenced repo paths.
    for line in text.splitlines():
        if "`" in line and (".cursor" in line or "scripts/" in line or "src/" in line):
            assert "\\" not in line, f"backslash path in {skill_path}: {line!r}"