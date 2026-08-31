---
name: plausible
description: Plausible analytics for the estate's sites — the shared-account model and (once the key lands) API + embed mechanics. Use when adding analytics to any site, filling a deploy doc's Plausible row, or when the user mentions Plausible. SKELETON — grows as the account key arrives and the first site is wired; update it with every verified fact.
---

# Plausible — product analytics (skeleton)

## Account model (Oriol, 2026-08-31)

**ONE shared Plausible account for all three realms** (exception to
"accounts follow the scope"). API key: ⏳ not yet delivered — home is
`hq/homelab/secrets/plausible.env` (`PLAUSIBLE_API_KEY`, plus
`PLAUSIBLE_URL` if it turns out self-hosted); the ask lives in hq
`USER_TODO.md`. Note: hq's deploying doc §3b earlier recorded "self-hosted,
decided in principle, not built" — Oriol's 2026-08-31 statement implies an
account now exists; reconcile hosting mode when the key arrives and fix
BOTH docs.

## House rules that already apply

- Citizen-facing surfaces stay cookieless (`zero-cookies` skill) —
  Plausible is the compatible choice; no other analytics vendor, ever
  (hq deploying doc §3b).
- Every deployed repo's status table has a Plausible row — close it when
  the site is wired.

## To fill in on first use (do not guess)

Site creation via API vs UI; the script tag / proxying decision; per-realm
site grouping; shared-link dashboards. Verify against the live account,
then replace this section.
