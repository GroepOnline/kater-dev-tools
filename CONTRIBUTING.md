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

## Security

See [SECURITY.md](SECURITY.md). Do not include real API keys in PRs or issue comments.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
