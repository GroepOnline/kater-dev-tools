# PR #103 review — dashboard / frontend architecture doc

Lens: `docs/architecture/runtime-kronkel.md` +
`docs/merge-train-20260912.md`.
Head: `adac162`.

## Verdict

**MERGE** (slot 1). Docs-only. Kronkel-aligned: keep Python gateway;
do not rewrite Node/TS “for speed”.

## Diff facts

One file: `docs/architecture/dashboard-and-frontend.md` (+136).
Three-listener model, embedded dashboard vs SPA costs, secrets stay
server-side. Related links exist on `main`.

## Finding (erratum, not a merge-block)

The sentence “There has never been a `package.json` frontend app in
this repository” is false. `studio/` is a React/Vite client that writes
static assets to `src/kater/web/studio_dist/`. Patch after merge
(or in a follow-up): dashboard stays embedded; Studio is the
presentation client, not a gateway rewrite.

## Kronkel

Pass on all eight. Complements `runtime-kronkel.md` (UI vs execute).

## Gate

CI green. No review threads. No file overlap with #95/#102.
