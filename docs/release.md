# Releasing Kater

Kater uses a two-channel release contract enforced by
[`../release-policy.json`](../release-policy.json) and
[`../scripts/validate_release.py`](../scripts/validate_release.py).

## Channels

| Channel | Tag shape | Prerelease | Notes |
|---|---|---|---|
| stable | `vX.Y.Z` | No | Production-ready tag on `main` |
| development | `vX.Y.Z.devN` | Yes | Pre-release snapshot, always marked prerelease on GitHub |

Both channels tag from `main` only.

## Version management

Version is the single source of truth in two files that must match exactly:

- `pyproject.toml` — `[project] version = "X.Y.Z"`
- `src/kater/__init__.py` — `__version__ = "X.Y.Z"`

Bump these together in a PR before tagging. The validator rejects any tag whose
version does not match both sources.

## Cutting a release

### Automated (tag push)

1. Ensure `main` is up to date and green in CI.
2. Bump `pyproject.toml` and `src/kater/__init__.py` to the target version.
3. Push the version bump as a PR and merge to `main`.
4. Create an annotated tag:

   ```bash
   git tag -a v1.0.0 -m "v1.0.0"
   git push origin v1.0.0
   ```

5. The `release.yml` workflow fires, validates the tag against the contract,
   runs full Ruff/Mypy/pytest gates, builds the wheel and sdist, and publishes
   a GitHub Release with the build artifacts attached.

### Manual (workflow_dispatch)

From the Actions tab, run the `Release` workflow with the version input
(e.g. `1.0.0`). This is useful when the tag push trigger is unavailable.

## What the validator checks

`scripts/validate_release.py` enforces:

1. **Tag format** — the tag matches a channel's `tag_pattern`.
2. **Version match** — the version (tag minus leading `v`) matches the channel's
   `version_pattern` and equals `pyproject.toml` and `__init__.py`.
3. **Immutable ancestry** — the tag's commit is an ancestor of `origin/main`,
   preventing rewritten or orphaned tags.
4. **Artifact version** — every file in `dist/` carries the exact resolved
   version in its filename.

Exit code 0 = pass; 1 = first violation. Stdlib only — no dependencies required.

## PyPI

PyPI publishing is **disabled**. The trusted-publishing step in `release.yml`
is commented out. To enable:

1. Configure the PyPI publisher for this repo at
   https://pypi.org/manage/account/publishing/ (OIDC, ref pattern `v*`).
2. Uncomment the publish step in `.github/workflows/release.yml`.

## Rollback

If a release is bad:

1. Retag from a new commit: the validator rejects moved tags because ancestry
   must point at `main`.
2. Delete the GitHub Release + tag (requires repo write access).
3. Revert the version bump in `pyproject.toml` and `__init__.py` via a new PR.
