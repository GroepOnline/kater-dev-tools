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
GITHUB_SCRIPT_SHA = "actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3"


def _job_block(text: str, job: str, next_job: str) -> str:
    return text.split(f"  {job}:\n", 1)[1].split(f"\n  {next_job}:\n", 1)[0]


def test_automerge_uses_github_script_v9() -> None:
    text = AUTOMERGE.read_text(encoding="utf-8")
    # v9, pinned by commit SHA rather than by a mutable tag.
    assert text.count(f"{GITHUB_SCRIPT_SHA} # v9") == 2
    assert "actions/github-script@v" not in text


def test_ci_runs_full_python_jobs_on_stacked_feature_base_prs() -> None:
    text = CI.read_text(encoding="utf-8")
    on_block = text.split("\njobs:", 1)[0]
    pr_block = on_block.split("pull_request:", 1)[1].split("schedule:", 1)[0]
    assert "branches:" not in pr_block
    assert "  lint-type:" in text
    assert "uv run ruff check ." in text
    assert "uv run mypy" in text
    assert "timeout 480s uv run pytest" in text
    assert "GRO-1209" in text
    assert "INTERIM" in text
    assert "production-safe isolation" in text
    assert "  validate:" in text
    assert "  unit:" in text
    assert "  gate:" in text


def test_no_org_leak_runs_on_stacked_feature_base_prs() -> None:
    text = NO_ORG_LEAK.read_text(encoding="utf-8")
    on_block = text.split("\njobs:", 1)[0]
    pr_block = on_block.split("pull_request:", 1)[1].split("push:", 1)[0]
    assert "branches:" not in pr_block
    assert "github.event.pull_request.base.ref" in text
    assert "PR_BASE_REF" in text
    assert "GRO-1209" in text
    assert 'origin "${{ github.event.pull_request.base.ref }}"' not in text
    assert "format('origin/{0}', github.event.pull_request.base.ref)" not in text
    assert "head.repo.full_name == github.repository" in text
    assert "github.event.pull_request.base.sha" in text
    assert "path: .ci-trusted-scanner" in text
    assert "path: ${{ runner.temp }}/trusted-scanner" not in text
    assert '${RUNNER_TEMP}/no_org_leak.py' in text
    assert "uv run --no-project python" in text
    assert "rm -rf .ci-trusted-scanner" in text


def test_ci_jobs_install_the_browser_extra() -> None:
    text = CI.read_text(encoding="utf-8")
    # lint-type, unit, integration, computer-acceptance, package: 5 occurrences.
    assert text.count("uv sync --frozen --dev --extra browser") == 5


def test_unit_matrix_job_uses_kater_checkout_sha_and_longer_timeout() -> None:
    block = _job_block(CI.read_text(encoding="utf-8"), "unit", "integration")
    assert KATER_CHECKOUT_SHA in block
    assert "timeout 480s uv run pytest" in block
    assert "--no-cov" in block
    assert "timeout 180s" not in block
    assert "timeout 300s" not in block


def test_computer_acceptance_checks_out_kater_and_the_private_runtime() -> None:
    """Both checkouts share the pinned ``actions/checkout`` SHA -- the pin
    identifies the action, not the repository being cloned -- and the private
    contract runtime is selected via its own ``repository:`` input.

    The private runtime's repository name is deliberately not spelled out here:
    ``scripts/no_org_leak.py`` keeps private data-plane references confined to
    the audit docs and the private lane itself, so this asserts the shape of
    the input (owner-scoped ``repository:``) instead.
    """
    block = _job_block(CI.read_text(encoding="utf-8"), "computer-acceptance", "package")
    assert "- name: Checkout Kater" in block
    assert "- name: Checkout pinned private contract runtime" in block
    assert block.count(KATER_CHECKOUT_SHA) >= 2
    assert "repository: ${{ github.repository_owner }}/" in block


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
    # Same pinned, dev-inclusive sync as every other job (no silent fallback
    # that would drop the dev extras and the coverage plugins with them).
    assert "uv sync --frozen --dev --extra browser" in block
    assert "uv run playwright install chromium" in block


def test_release_workflow_bumps_checkout_action() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "actions/checkout@v7" in text


def test_no_org_leak_workflow_matches_shared_checkout_sha() -> None:
    text = NO_ORG_LEAK.read_text(encoding="utf-8")
    assert KATER_CHECKOUT_SHA in text


def test_pyproject_pins_newer_uv_build_range() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'requires = ["uv_build>=0.12.4,<0.13"]' in text
    assert "0.11.32" not in text
    assert "0.12.2" not in text
