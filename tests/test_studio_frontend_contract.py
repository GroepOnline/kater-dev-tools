from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio"


def test_studio_is_componentized_and_configurable() -> None:
    config = (STUDIO / "src/config.ts").read_text()
    tokens = (STUDIO / "src/styles/tokens.css").read_text()
    components = {path.name for path in (STUDIO / "src/components").glob("*.tsx")}
    assert {"Sidebar.tsx", "Topbar.tsx", "StatusPill.tsx", "MetricCard.tsx", "IntegrationCard.tsx", "PageHeader.tsx", "EmptyState.tsx", "PrCard.tsx"} <= components
    assert "studioConfig" in config
    assert "VITE_KATER_API_BASE" in config
    assert "--accent:" in tokens and "--surface:" in tokens and "--sidebar-width:" in tokens


def test_studio_never_replaces_the_python_runtime_with_mock_state() -> None:
    package = (STUDIO / "package.json").read_text()
    source = "\n".join(path.read_text() for path in (STUDIO / "src").rglob("*") if path.is_file())
    assert '"express"' not in package
    assert '"ws"' not in package
    assert "Math.random" not in source
    assert "setInterval" not in source
    assert "cdn.tailwindcss.com" not in source
    assert "/api/status" in source
    assert "/api/catalog" in source
    assert "/api/pr/list" in source
    assert "/api/browser/providers" in source
    assert "/api/browser/sessions" in source


def test_google_ai_studio_branch_is_documented_as_salvage_only() -> None:
    architecture = (STUDIO / "ARCHITECTURE.md").read_text()
    assert "visual/interaction source material only" in architecture
    assert "Never merge that branch wholesale" in architecture
    assert "Python remains authoritative" in architecture
