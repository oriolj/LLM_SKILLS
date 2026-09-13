---
name: plausible
description: Plausible Cloud account notes — PARKED (Oriol, 2026-08-31, tier has no Sites API). For PERSONAL (oriolj) sites the answer is the self-hosted Umami — load the `umami` skill instead. Use this one only when the user mentions Plausible itself or a company-scope analytics decision.
---

# Plausible — product analytics (skeleton)

> **2026-09-13: personal sites are on the self-hosted Umami at `stats.oriolj.com`** — the `umami` skill owns adding a site, the tag, the API and the ops. The two tags that pointed at Plausible Cloud (oriolj.com, humans2agents.com) were replaced that day. This file stays for the company-scope decision only.

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
