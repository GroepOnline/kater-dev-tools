# Contributing to Kater

Thanks for helping improve Kater! This project is a developer MCP gateway — keep changes focused and testable.

## Development setup

```bash
git clone https://github.com/OnlineChefGroep/kater-dev-tools.git
cd kater-dev-tools
uv sync --dev
uv run pytest -v
uv run ruff check .
./scripts/smoke.sh
```

## Pull requests

1. Fork and create a feature branch from `main`.
2. Keep diffs focused — one concern per PR when possible.
3. Add or update tests for behavior changes.
4. Run lint and tests locally before pushing.
5. Update README/docs if user-facing behavior changes.

## Code style

- Python 3.11+, ruff with line length 100
- Match existing module patterns (deep modules, minimal surface area)
- No secrets in code, tests, or committed config

## Pre-commit hooks

Optioneel maar sterk aanbevolen: installeer de pre-commit hooks lokaal zodat
lint/type/format/secrets checks al draaien vóór je een commit maakt. De hooks
gebruiken exact dezelfde `ruff`, `mypy` en `gitleaks` configuratie als CI
(`.github/workflows/ci.yml` en `no-org-leak.yml`), dus wat lokaal groen is, is
ook groen in CI — geen verrassingen na de push.

```bash
# Installeer de git hook (eenmalig per clone):
uvx pre-commit install

# Run handmatig over alle bestanden:
uvx pre-commit run --all-files
```

`pre-commit` draait via `uvx` en hoeft dus niet als dev-dependency aan
`pyproject.toml` te worden toegevoegd. De configuratie staat in
`.pre-commit-config.yaml`. Na een `git commit` draaien de hooks automatisch
over de gewijzigde bestanden; bij een faalende hook wordt de commit geblokkeerd
tot je de problemen oplost.

## Security

See [SECURITY.md](SECURITY.md). Do not include real API keys in PRs or issue comments.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
