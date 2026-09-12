# 2026-09-12 — Execution Foundation strict review-fix

## Goal

PR #95 volledig oppakken: CI groen + strenge review-fixes.

## CI

- `no-org-leak`: merge-train doc (org handle + UDO)
- `unit (3.13)`: `timeout 480s` → 124, geen falende assert
- `gate`: volgschade van unit

## Fixes

Visibility, native-action binding, GitHub mutation credentials,
identity-scoped idempotency + reservation, non-blocking timeout,
400-mapping, plugin coerce, catalog profiles/configured, unit timeout 600s.

## Verify

Focused: execution-foundation, visibility, executor, seed, doctor, CI
workflow tests — groen. Full suite draait na push.

## Follow-up

Human APPROVE op nieuwe head. Body-identity blijft v0 loopback-actor.
