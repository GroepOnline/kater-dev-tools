# Releasing Kater

Kater uses a two-channel release contract enforced by
[`../release-policy.json`](../release-policy.json) and
[`../scripts/validate_release.py`](../scripts/validate_release.py).

## After a merge train (the usual path)

Feature PRs never bump the package version. They append under
`## [Unreleased]` in `CHANGELOG.md`. After a train of merges on `main`:

1. Confirm there is no tag that already covers this work:

   ```bash
   git fetch --tags origin
   git ls-remote --tags origin
   ```

2. Choose the bump from what landed (semver):
   - **patch** — fixes and docs only
   - **minor** — additive features (the usual train)
   - **major** — breaking CLI/API/settings

3. Open **one bump PR** that only:
   - sets the same version in `pyproject.toml` and `src/kater/__init__.py`
   - moves `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and leaves an empty Unreleased
   - updates compare links at the top of `CHANGELOG.md`
   - updates `SECURITY.md` supported versions if the minor/major changed

4. Merge that PR to `main`. Do not tag from the bump branch.

5. From **updated** `origin/main`, cut the annotated tag and push it:

   ```bash
   git checkout main
   git pull --ff-only origin main
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

   Tag push fires `.github/workflows/release.yml`. Merge-ready is not a tag.

The remote had **no git tags** until 1.1.0. Declared `1.0.0` in the package
sources was changelog history, not a GitHub Release.

## Channels

| Channel | Tag shape | Prerelease | Notes |
|---|---|---|---|
| stable | `vX.Y.Z` | No | Production-ready tag on `main` |
| development | `vX.Y.Z.devN` | Yes | Pre-release snapshot, always marked prerelease on GitHub |

Both channels tag from `main` only.

## Version sources

Version is the single source of truth in two files that must match exactly:

- `pyproject.toml` — `[project] version = "X.Y.Z"`
- `src/kater/__init__.py` — `__version__ = "X.Y.Z"`

The validator rejects any tag whose version does not match both sources.
Tests in `tests/test_validate_release.py` read those sources; they must not
hardcode a frozen `v1.0.0`.

## Cutting a release

### Automated (tag push)

Follow **After a merge train** above. The bump PR is step 3; the tag is step 5.

### Manual (workflow_dispatch)

From the Actions tab, run the `Release` workflow with the version input
(e.g. `1.1.0`). HEAD must already be on `main` at that version. This is useful
when the tag-push trigger is unavailable.

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

1. Do not move the tag. The validator rejects rewritten tags because ancestry
   must point at `main`.
2. Delete the GitHub Release + tag (requires repo write access).
3. Revert the version bump in `pyproject.toml` and `__init__.py` via a new PR.
