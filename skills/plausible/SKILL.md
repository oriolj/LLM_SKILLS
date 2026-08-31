---
name: plausible
description: Plausible analytics for the estate's sites — the shared-account model and (once the key lands) API + embed mechanics. Use when adding analytics to any site, filling a deploy doc's Plausible row, or when the user mentions Plausible. PARKED (Oriol, 2026-08-31): the account's tier has no Sites API, so nothing gets wired for now; a self-hosted instance may come later. Keep for the account model; update when unparked.
---

# Plausible — product analytics (skeleton)

## Account model (Oriol, 2026-08-31)

**ONE shared Plausible account for all three realms** (exception to
"accounts follow the scope"). **PARKED (Oriol, 2026-08-31): the current tier has NO Sites API, so no
key handover and no wiring for now** — deploy docs keep their Plausible
row as ➖/⏳ with this reason. Possible future: a self-hosted Plausible (or
similar) instance; when that lands, key home is
`hq/homelab/secrets/plausible.env` and this file gets the mechanics.

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
