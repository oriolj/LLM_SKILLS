# State-of-SEO tracker template

Every non-trivial project that ships SEO work should keep a living
tracker doc (typically `docs/seo.md` at the repo root). Without it, the
next session re-audits what's already been done and the backlog drifts
into scattered TODOs.

Three living tables, in this order. Copy this skeleton into the project
verbatim and fill in as you go:

````markdown
# SEO

Umbrella doc for this project's SEO surfaces. See also: `docs/rss.md`,
`docs/llms-txt.md` (link any related docs).

[… a few sections documenting the current implementation: canonical
host strategy, robots policy, sitemap architecture, JSON-LD schemas,
OpenGraph, RSS. Write these as you ship, keep them current.]

## State of SEO

### ✅ Implemented

| Surface                     | Where                                  |
|-----------------------------|----------------------------------------|
| `<link rel="canonical">`    | `src/layouts/LayoutBase.astro`         |
| `<meta name="description">` | `src/layouts/LayoutBase.astro`         |
| Open Graph + Twitter        | `src/components/OpenGraph.astro`       |
| `robots.txt` (SSR, per-host)| `src/pages/robots.txt.ts`              |
| Sitemap index               | `src/pages/sitemap.xml.ts` → main / archives / episodes |
| JSON-LD `NewsArticle`       | `src/pages/news/[slug].astro`          |
| JSON-LD `BreadcrumbList`    | News detail, episode detail            |

### ❌ Not implemented

| Surface                                | Priority | Rough effort |
|----------------------------------------|----------|--------------|
| JSON-LD `PodcastSeries` on program     | **High** | Small — mirror the episode wiring |
| Episodes in sitemap                    | Medium   | Medium — needs sitemap-index split |
| Per-radio news RSS                     | Medium   | Small — mirror the podcast rss |
| `twitter:site` / `twitter:creator`     | Low      | Trivial — plumb social handle |
| `og:locale` per actual language        | Low      | Trivial — expand the switch |
| Hreflang                               | Deferred | Not applicable today |

### 🤔 Open questions / future considerations

- **Per-tenant robots policy.** If any tenant wants to opt out of AI
  training while keeping retrieval, we'd add a `robots_policy` field to
  the tenant API and branch the `robots.txt` route.
- **Sitemap-episodes split.** Current cap is 10k URLs; past that we need
  per-program sitemap files linked from the index.
- **IndexNow on publish.** Real-time URL push to Bing + Yandex when
  content publishes. No Google support, but Bing + Copilot traffic is
  non-trivial.
- **Core Web Vitals pass** on detail pages (font display, image sizing,
  player lazy-load). Non-functional but impacts ranking.
````

## Maintenance rules

1. **Update after every SEO-related commit.** If you ship something,
   move its row from ❌ to ✅ with a link to the file. If you defer
   something, add a row in ❌ with a priority (High / Medium / Low /
   Deferred) and an effort estimate.
2. **Promote stale open questions.** Once an open question becomes
   actionable, move it into ❌ with a priority.
3. **Don't duplicate ✅ rows between this doc and `CHANGELOG.md` /
   `RELEASE_NOTES.md`.** The tracker is "what exists now". The
   changelog is "what shipped when". Different audiences.
4. **Flag architectural constraints** inline in the relevant section,
   not in the tables. Example: "Sitemap URLs must use the canonical
   host" is a doc sentence, not a table row.

## Priority guidance (when to call something High vs Low)

**High** — unlocks rich results in Google, fixes a correctness bug, or
addresses a visible SEO gap that impacts indexing or social previews.
Examples: JSON-LD for a major content type, canonical host redirect,
missing sitemap.

**Medium** — materially improves crawl coverage or citation visibility
but the site works without it. Examples: sitemap-index at scale,
per-tag archive URLs, news RSS.

**Low** — polish, coverage completeness, or defensive improvements.
Examples: `twitter:site` handle, `og:locale` for long-tail languages,
`BreadcrumbList` on non-detail pages.

**Deferred** — not applicable today; track so it's obvious when it
becomes applicable. Examples: hreflang (single-language site), Google
Search Console ops task (not code).
