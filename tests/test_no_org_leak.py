from __future__ import annotations

import scripts.no_org_leak as nol

# Files/contents that must be rejected outside the allowlist.
LEAK_SAMPLES = {
    "src/kater/evil.py": "BASE = 'https://chefgroep" + ".nl/x'",
    "src/kater/evil2.py": "owner = 'online" + "chefgroep'",
    "src/kater/evil3.py": "DB = 'postgres" + "://user:pass@host/db'",
    "src/kater/evil4.py": "BASE = 'https://groeponline.nl/x'",
    "src/kater/evil5.py": "owner = 'GroepOnline'",
}
# Suffixes emitted by scripts/no_org_leak.py (after ``path: ``).
LEAK_EXPECTED_SUFFIX = {
    "src/kater/evil.py": "org production domain outside allowlist",
    "src/kater/evil2.py": "org handle outside attribution allowlist",
    "src/kater/evil3.py": "credential-shaped connection string",
    "src/kater/evil4.py": "org production domain outside allowlist",
    "src/kater/evil5.py": "org handle outside attribution allowlist",
}
# Files/contents that are allowed (attribution / audit docs).
CLEAN_SAMPLES = {
    "README.md": "GroepOnline maintains Kater.",
    "docs/deploy-server.md": "Point DNS at groeponline.nl",
    "SECURITY.md": "Online" + "ChefGroep security contact.",
    "src/kater/ok.py": "print('hello kater')",
    # CODEOWNERS routes review requests to GitHub owners by definition.
    ".github/CODEOWNERS": "* @Online" + "ChefGroep\n",
    # CHANGELOG.md compares against releases under the org's GitHub domain.
    "CHANGELOG.md": (
        "[Unreleased]: https://github.com/Online"
        + "ChefGroep/kater-dev-tools/compare/v1.0.0...HEAD"
    ),
}


def test_scan_flags_leaks(tmp_path):
    targets = []
    for rel, body in LEAK_SAMPLES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        targets.append(str(p))
    errors = nol.scan(targets)
    assert all(any(error.startswith(f"{target}:") for error in errors) for target in targets)
    for rel, expected_suffix in LEAK_EXPECTED_SUFFIX.items():
        assert any(
            error.endswith(f": {expected_suffix}") and error.split(":", 1)[0].endswith(rel)
            for error in errors
        ), f"missing {expected_suffix!r} for {rel}"


def test_scan_allows_attribution_and_clean(tmp_path, monkeypatch):
    targets = []
    for rel, body in CLEAN_SAMPLES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        targets.append(str(p.relative_to(tmp_path)))
    monkeypatch.chdir(tmp_path)
    assert nol.scan(targets) == []


def test_scan_does_not_allow_nested_file_with_attribution_basename(tmp_path):
    nested = tmp_path / "vendor" / "README.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("https://chefgroep" + ".nl/private")
    assert nol.scan([str(nested)])


def test_scan_ignores_directories(tmp_path):
    d = tmp_path / "src" / "kater"
    d.mkdir(parents=True)
    (d / "x.py").write_text("chefgroep" + ".nl")
    assert nol.scan([str(d)]) == []


def test_scan_allows_only_exact_generated_contract_paths(tmp_path, monkeypatch):
    allowed = tmp_path / "src/kater/capabilities/generated/error-envelope.json"
    allowed.parent.mkdir(parents=True)
    allowed.write_text('{"$id":"https://online' + "chefgroep" + '.nl/schema"}')
    lookalike = tmp_path / "vendor/error-envelope.json"
    lookalike.parent.mkdir(parents=True)
    lookalike.write_text(allowed.read_text())
    monkeypatch.chdir(tmp_path)

    assert nol.scan([str(allowed.relative_to(tmp_path))]) == []
    assert nol.scan([str(lookalike.relative_to(tmp_path))])


def test_scan_rejects_org_handle_under_cursor(tmp_path, monkeypatch):
    cursor_skill = tmp_path / ".cursor/skills/example/SKILL.md"
    cursor_skill.parent.mkdir(parents=True)
    cursor_skill.write_text("repo: Online" + "ChefGroep/kater-dev-tools\n")
    monkeypatch.chdir(tmp_path)
    errors = nol.scan([".cursor/skills/example/SKILL.md"])
    assert any("org handle outside attribution allowlist" in error for error in errors)


def test_scan_rejects_org_handle_under_cursor_agents(tmp_path, monkeypatch):
    # Regression: `.cursor/agents/*.md` (added by this PR) must never be
    # allowlisted, matching the `.cursor/skills/*` guard above.
    cursor_agent = tmp_path / ".cursor/agents/pr-gate.md"
    cursor_agent.parent.mkdir(parents=True)
    cursor_agent.write_text("gh repo view --repo Online" + "ChefGroep/kater-dev-tools\n")
    monkeypatch.chdir(tmp_path)
    errors = nol.scan([".cursor/agents/pr-gate.md"])
    assert any("org handle outside attribution allowlist" in error for error in errors)


def test_no_cursor_paths_in_allowlists():
    """Org-pinned Cursor skills/agents stay out of allowlists.

    The sole `.cursor/` exception is ``environment.json`` (Cloud
    ``repositoryDependencies`` must name the meta-skills GitHub slug).
    """
    assert ".cursor/environment.json" in nol.ALLOWED_ORG_HANDLE
    for allowed in (nol.ALLOWED_ORG_HANDLE, nol.ALLOWED_PROD_DOMAIN):
        extras = [
            entry
            for entry in allowed
            if entry.startswith(".cursor/") and entry != ".cursor/environment.json"
        ]
        assert extras == []


def test_self_allowlist(tmp_path, monkeypatch):
    # The detector's own test file holds literal leak samples. It must be
    # allowlisted so the PR diff-scan does not flag the detector suite itself
    # (regression: the CI "Org-leak guard" step failed on exactly this file).
    p = tmp_path / "tests/test_no_org_leak.py"
    p.parent.mkdir(parents=True)
    p.write_text(open("tests/test_no_org_leak.py").read())
    monkeypatch.chdir(tmp_path)
    assert nol.scan(["tests/test_no_org_leak.py"]) == []


def test_scan_allows_pre_commit_config_no_org_leak_hook(tmp_path, monkeypatch):
    # The new local no-org-leak pre-commit hook only references the already
    # allowlisted `no-org-leak.yml` filename in a comment; the config file
    # itself contains no org handle / domain and must not trip the guard.
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "# mirrors .github/workflows/no-org-leak.yml\n"
        "- id: no-org-leak\n"
        "  entry: uv run python scripts/no_org_leak.py\n"
    )
    monkeypatch.chdir(tmp_path)
    assert nol.scan([".pre-commit-config.yaml"]) == []
