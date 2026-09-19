# 2026-09-19 — Product Authentik OIDC e2e

## Done

- Kater is now an OIDC RP when `AUTH_OIDC_ISSUER` + `AUTH_OIDC_CLIENT_ID` are set.
- `/authorize` redirects to Authentik; `/oidc/callback` mints the local gateway code.
- Canary: `./scripts/oidc-canary.sh` (discovery + 302 + callback 400; no secrets).
- Docs: Access vs Authentik modes + CF Access bypass checklist. No DNS apply.

## Live IdP facts (probed)

- Public auth host healthz/readyz 200
- Discovery 200 at `/application/o/kater/.well-known/openid-configuration`
- Client id `chefgroep-kater-oidc` (issuer slug is `kater`, not the client-id slug)
- Alternate public TLD discovery 403 from this VM (CF); treat the primary public host as canonical

## Pickup

- CoS/CF lane must register `/oidc/callback` URIs and bypass Access on OIDC paths.
- Place lock remains Kater on bc-scan-arm.
