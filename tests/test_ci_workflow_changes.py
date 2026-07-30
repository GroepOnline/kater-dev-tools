"""Regression coverage for the CI/CD workflow and packaging bumps in this PR.

Mirrors the plain-text-assertion convention established in
``test_ci_dependabot_policy.py``: workflow YAML is read as text and checked
for specific pinned versions/flags rather than executed, since these files
only run inside GitHub Actions.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github/workflows/ci.yml"
AUTOMERGE = ROOT / ".github/workflows/automerge.yml"
RELEASE = ROOT / ".github/workflows/release.yml"
NO_ORG_LEAK = ROOT / ".github/workflows/no-org-leak.yml"
PYPROJECT = ROOT / "pyproject.toml"

KATER_CHECKOUT_SHA = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UDO_CHECKOUT_SHA = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"


def _job_block(text: str, job: str, next_job: str) -> str:
    return text.split(f"  {job}:\n", 1)[1].split(f"\n  {next_job}:\n", 1)[0]


def test_automerge_uses_github_script_v9() -> None:
    text = AUTOMERGE.read_text(encoding="utf-8")
    assert text.count("actions/github-script@v9") == 2
    # Guard against a partial/accidental downgrade back to v7.
    assert "actions/github-script@v7" not in text


def test_ci_jobs_install_the_browser_extra() -> None:
    text = CI.read_text(encoding="utf-8")
    required = (
        ("lint-type", "unit"),
        ("unit", "integration"),
        ("integration", "computer-acceptance"),
        ("e2e", "package"),
    )
    for job, next_job in required:
        block = _job_block(text, job, next_job)
        assert "uv sync --frozen --dev --extra browser" in block


def test_unit_matrix_job_uses_kater_checkout_sha_and_longer_timeout() -> None:
    block = _job_block(CI.read_text(encoding="utf-8"), "unit", "integration")
    assert KATER_CHECKOUT_SHA in block
    assert "timeout 300s uv run pytest" in block
    assert "timeout 180s" not in block


def test_computer_acceptance_pins_kater_and_udo_checkouts_separately() -> None:
    """Kater's own checkout tracks the shared pinned SHA, but the private
    contract-runtime checkout intentionally stays on its own (different
    repository's) pin and must not be bumped in lockstep."""
    block = _job_block(CI.read_text(encoding="utf-8"), "computer-acceptance", "package")
    assert KATER_CHECKOUT_SHA in block
    assert UDO_CHECKOUT_SHA in block


def test_computer_acceptance_explains_skipped_fork_runs() -> None:
    block = _job_block(CI.read_text(encoding="utf-8"), "computer-acceptance", "package")
    assert "Explain skipped fork acceptance" in block
    assert "if: github.event.repository.fork == true" in block
    assert "skipped outside the upstream repository" in block


def test_security_pr_dependency_review_is_fork_guarded() -> None:
    block = _job_block(CI.read_text(encoding="utf-8"), "security-pr", "coverage")
    assert (
        "if: github.event.repository.fork != true && github.event_name == 'pull_request'"
        in block
    )
    assert "Dependency review" in block


def test_coverage_job_installs_playwright_chromium() -> None:
    block = _job_block(CI.read_text(encoding="utf-8"), "coverage", "gate")
    assert "uv sync --extra dev --extra browser || uv sync --extra browser" in block
    assert "uv run playwright install chromium" in block


def test_release_workflow_bumps_checkout_action() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "actions/checkout@v7" in text


def test_no_org_leak_workflow_matches_shared_checkout_sha() -> None:
    text = NO_ORG_LEAK.read_text(encoding="utf-8")
    assert KATER_CHECKOUT_SHA in text


def test_pyproject_pins_newer_uv_build_range() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'requires = ["uv_build>=0.12.0,<0.13"]' in text
    assert "0.11.32" not in text
