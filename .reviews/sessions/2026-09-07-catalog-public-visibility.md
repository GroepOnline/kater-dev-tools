# PR83 public catalog visibility — 2026-09-07

Base: `15f68498c15dbb739ef42ea80e3bab2c5f235820`.
Branch: `fix/catalog-public-visibility-20260907`.

## Finding and change

The existing `visible_tool_sources()` contract hid private-only providers, but
the persisted-connector loops could reintroduce them. Dynamic private-only
connectors and plugin/profile metadata also bypassed that visibility boundary.

- The shared catalog connector map now omits private-only connector profiles
  and IDs belonging to hidden sources, even when a persisted row has stale
  public profile labels.
- All catalog profile projections remove private profile names in public mode.
- Explicit and core plugin projections omit hidden toolkit references and
  private-only bundles. An empty public implicit extension bundle is not emitted.
- Mixed public/private entries keep their public representation. Non-public
  mode preserves the complete catalog. Capability authorization is unchanged.

## Verification

```sh
uv run ruff check .
uv run mypy
uv run pytest --no-cov -q --tb=short tests/test_fabric_catalog_visibility.py tests/test_fabric_catalog.py::test_catalog_url_projection_is_origin_only tests/test_fabric_catalog.py::test_catalog_openapi_describes_filters_and_restriction
git diff --check
```

All pass: 115 source files checked by mypy; 53 selected tests pass. New visibility
tests reproduce the public metadata disclosure before the implementation and
cover all five catalog routes and all supported truthy public-mode values.

The new fixture mocks connector listing, profiles, settings and auth bindings,
and makes `sqlite3.connect` fail immediately. It exercises registered route
handlers, not a live server or the full transport/auth middleware pipeline.
Existing selected URL/OpenAPI tests are pure projections with cache-reset
fixtures. No SQL files/migrations, real database, services, native build,
credentials or runtime configuration were changed or executed.

Full pytest, coverage, CI, push and PR delivery are intentionally not performed:
the current full CI includes SQL migrations and requires explicit authorization
under the standing task boundary. Independent final-head source review remains
with the parent integration lane.
