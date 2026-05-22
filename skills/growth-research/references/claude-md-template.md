# CLAUDE.md — {{PRODUCT_NAME}} partners & ads research

## What this repo is

A research workspace for {{PRODUCT_NAME}}'s go-to-market. It is **not a code project**. There is no Makefile, no build, no tests. The only artefacts are markdown documents and the xlsx files generated from their JSON sidecars.

Product surfaces to keep distinct when researching:

{{SURFACES_SUMMARY}}

When asked to "find places to advertise" or "find partners," **always ask which product surface** unless it's obvious — different surfaces have different audiences and price points.

## Languages supported

{{LANGUAGES}}

## Style conventions for documents in this repo

- **Markdown only** (source of truth). The `.json` and `.xlsx` companions in each topic folder are generated from those markdown notes — keep them in sync.
- **Always include a URL** when listing an outlet, event, subreddit, or company. A name without a URL is a TODO, not a finding.
- **Always tag the product surface** the recommendation fits.
- **Always tag the geography** when relevant.
- **Date all dated facts.** Conferences, prices, contact emails — they go stale. Add `(verified YYYY-MM)`.
- **No filler.** This is a buyer-facing research deck, not an essay. Lead with the table; explain only what's non-obvious.
- **i18n capitalisation**: for Spanish, Catalan, French content use **sentence case** (only first word and proper nouns capitalised).

## How to add new research

1. Open the relevant `research/<topic>/<topic>.md` file.
2. Append the new entry to the appropriate section, with URL + tags + a one-line "why this matters".
3. Mirror the entry into `research/<topic>/<topic>.json`.
4. Re-run `python3 scripts/build_xlsx.py` and `python3 scripts/build_html.py` from the repo root to regenerate the xlsx and the HTML explorer.
5. Update `GROWTH_RESEARCH.md` summary if the finding changes recommended priorities.
6. Commit with a descriptive message (`research: add 12 EU community radio federations`).

The markdown is the source of truth; the JSON is the structured mirror; the xlsx and html/ are regenerated from JSON.

## Verifying facts

Conferences, prices, and contact pages change. Before recommending an action:

- Fetch the actual URL to confirm dates / status.
- Verify subreddit subscriber counts and self-promo rules.
- Confirm magazine ad rate cards exist; don't assume.

## What NOT to do

- **Don't recommend spam tactics.** No mass DM scripts, no fake account posting, no astroturfing on Reddit. Founder voice, real comments, real value.
- **Don't conflate product surfaces.** Tag every entry with the surface(s) it serves.
- **Don't propose creating a sales CRM, scraper, or scoring script** in this repo unless explicitly asked. This is a research deck. Tooling lives elsewhere.

## Git workflow

- Default branch is `master`.
- Commit research updates in small, focused commits. The git log should read like a paper trail.
