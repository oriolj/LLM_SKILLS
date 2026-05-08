---
name: seo
description: Ship and audit SEO on any kind of site — SaaS / marketing landing pages, e-commerce / shops, news / magazines, podcasts, blogs, local business, events, product sites, documentation, multitenant SaaS. Covers classic SEO (canonical URLs, robots.txt, sitemap.xml, Open Graph, JSON-LD / schema markup), AI search / GEO (AI crawler policy, AI Overview citation, llms.txt), RSS / Podcasting 2.0, Core Web Vitals (LCP / INP / CLS), hreflang / international, and multitenant canonical-host redirects. Use whenever the user asks about SEO, Google / Bing / DuckDuckGo indexing, AI Overviews, GEO / AEO, schema markup / structured data, rich results, merchant listings, Google News, Google Business Profile, crawl budget, deindex, site verification, social preview / Twitter / LinkedIn / Facebook cards, llms.txt, GPTBot / ClaudeBot / PerplexityBot / Googlebot / Google-Extended policy, Core Web Vitals / LCP / INP / CLS / PageSpeed, hreflang, or says their site isn't on Google / isn't in ChatGPT / isn't being cited by Claude / Perplexity. Also: "fix our SEO", "make this indexable", "add a sitemap", "add product schema", "rank in AI overviews", "get into Google News", "why isn't this on Google", "social preview is broken", "search visibility", "add structured data".
---

# SEO playbook

Opinionated, stack-agnostic playbook for classic search (Google, Bing)
and AI search / GEO (ChatGPT, Claude, Perplexity, Google AI Overviews,
Copilot). Strong classic SEO is the prerequisite for AI citation — GEO
layers on top, doesn't replace. Code is TypeScript; patterns apply to
Next.js, Django, Rails, Express, and any HTML-rendering stack.

Reference files in `references/` — load on demand:

- `ai-crawler-policy.md` — GPTBot / ClaudeBot / Google-Extended / Meta / Apple / Amazon / Perplexity; policy tiers.
- `schemas-by-page-type.md` — JSON-LD per page type, `@graph`, deprecated schemas, `Person` / `ProductGroup` / `NewsMediaOrganization`, shared primitives.
- `page-types.md` — per-vertical playbooks: e-commerce, news, local business, events, SaaS landing, blogs, video.
- `geo-and-ai-citations.md` — GEO / AEO content structure; how to get cited in AI Overviews.
- `core-web-vitals.md` — 2026 LCP / INP / CLS thresholds + image SEO.
- `hreflang.md` — international SEO pitfalls.
- `rss-feeds.md` — RSS 2.0 + Podcasting 2.0 (UUID v5 `podcast:guid` helpers).
- `verification-commands.md` — `curl | grep` one-liners + validator URLs.
- `state-of-seo-template.md` — tracker doc with ✅ / ❌ / 🤔 tables.

## First principles

1. **Server-render the content that matters.** JS-only content doesn't
   get indexed reliably by Google (delay ranges from seconds to weeks),
   and almost no AI crawler renders JavaScript at all — GPTBot,
   ClaudeBot, PerplexityBot fetch raw HTML. If primary content appears
   only after JS execution, you're invisible to AI search entirely.
   Fix that first; everything else is downstream.
2. **Every project gets a living tracker doc** (typically `docs/seo.md`
   at repo root) with three tables: ✅ Implemented, ❌ Not implemented
   (priority + effort), 🤔 Open questions. Load
   `references/state-of-seo-template.md` when creating or maintaining
   it.
3. **Pick canonical surfaces early.** One URL per piece of content.
   Every other reachable URL either 301s to it or advertises it via
   `<link rel="canonical">`.
4. **Ship fundamentals before rich features.** Title, meta description,
   canonical, robots.txt, sitemap.xml, Open Graph come before JSON-LD,
   IndexNow, video sitemaps.
5. **Match the project's vertical.** A shop needs `Product` +
   `ProductGroup` + shipping/returns structured data to show up in
   merchant listings; a news site needs `NewsMediaOrganization` +
   `NewsArticle` to enter Google News (fully algorithmic since Oct
   2025); a SaaS landing page barely needs anything beyond
   `Organization` + `WebSite`. Don't cargo-cult schemas that don't
   apply. `references/page-types.md` has the per-vertical playbooks.

## Baseline every site needs

In priority order:

1. **Unique `<title>` per page** — pattern `"<specific> - <site name>"`.
2. **`<meta name="description">`** per page, ≤160 chars, **distinct
   per page**. The single most-skipped piece of SEO. When N pages
   share a near-identical description — usually because a base
   layout supplies one site-wide fallback that uncustomized pages
   inherit — Google ignores the meta and *synthesizes* the snippet
   from page text, typically the first long run of words below the
   title. On most sites that's the footer or contact block, so
   every page snippets as the contact line. See **Case study: when
   Google ignores your meta description** below the list, and
   **Composition / CMS pages** for the derive-from-blocks fix.
3. **`<link rel="canonical">`** per page, absolute URL. Same string
   appears in `og:url`, sitemap `<loc>`, RSS `<link>`, JSON-LD
   `url`/`mainEntityOfPage`. One source of truth.
4. **`<html lang="…">`** matching the page's actual language.
5. **Open Graph + Twitter Card** (see below).
6. **`robots.txt`** (see below).
7. **`sitemap.xml`** (see below).
8. **Correct HTTP status codes** — 404 must return 404 (never 200 with
   a pretty page). 301 for permanent redirects, 302 for temporary.
9. **Single `<h1>` per page.**
10. **`alt=""` on every `<img>`** — descriptive for content images,
    empty string for decorative.
11. **Width/height on every `<img>`** — prevents CLS (layout shift is
    one of the three Core Web Vitals). For responsive images, set the
    *intrinsic* ratio, not viewport units. Details + 2026 LCP/INP/CLS
    thresholds in `references/core-web-vitals.md`.

### Case study: when Google ignores your meta description

Real Google SERP for a multitenant radio site where five pages all
inherited the same site-wide fallback `<meta description>`:

> **Ràdio Desvern: Inici** — `https://www.radiodesvern.com`
> emissora@radiodesvern.com. Tel 933723661. Instagram. Ràdio
> Desvern. emissora@radiodesvern.com +34610777015 Can Ginestar,
> Sant Just Desvern, 08960 Barcelona ...
>
> - **Podcasts** — "Descobreix tots els podcasts i programes de
>   ràdio disponibles ..."  ✅ unique meta, used as snippet
> - **Entrevistes en Video** — "emissora@radiodesvern.com
>   +34610777015 Can Ginestar ..."  ❌ footer scraped
> - **Notícies** — "emissora@radiodesvern.com +34610777015 Can
>   Ginestar ..."  ❌ footer scraped
> - **La Rambla** — "emissora@radiodesvern.com +34610777015 Can
>   Ginestar ..."  ❌ footer scraped
> - **Història** — "emissora@radiodesvern.com +34610777015 Can
>   Ginestar ..."  ❌ footer scraped

Only `/podcasts/` had a hand-written description. Every other page
fell back to `${siteName} — ${tagline}` (the same string verbatim)
and Google replaced it with the first long block of visible text
on each page — the site footer's contact line. The fix isn't to
nuke the fallback, it's to **derive a page-specific description
for every page**, including CMS-composed pages with no per-page
description in the data model. See **Composition / CMS pages**
below.

## Composition / CMS pages

Pages composed from a CMS or page-builder (modular pages, hub
pages, dashboards) often have no per-page description in the data
model — the user only sets a name and drops in content blocks.
Don't fall back to a site-wide tagline (see case study above):
**derive a description from the blocks actually rendered on this
page**.

Pattern: enumerate the page's blocks, map each block type to a
short localized noun, dedupe, join with a localized connector,
prefix with `<page name> on <site name>:`.

```ts
const BLOCK_LABEL: Record<BlockType, TranslationKey> = {
  PodcastBlock: 'moduleLabel.podcasts',
  NewsBlock:    'moduleLabel.news',
  GalleryBlock: 'moduleLabel.gallery',
  AgendaBlock:  'moduleLabel.agenda',
  WeatherBlock: 'moduleLabel.weather',
  // ...
};

const CONNECTOR: Record<Lang, string> = {
  en: 'and', es: 'y', fr: 'et', ca: 'i', de: 'und', pt: 'e', it: 'e',
};

function joinLocalized(items: string[], lang: Lang): string {
  if (items.length <= 1) return items[0] ?? '';
  const conn = CONNECTOR[lang] ?? CONNECTOR.en;
  if (items.length === 2) return `${items[0]} ${conn} ${items[1]}`;
  return `${items.slice(0, -1).join(', ')} ${conn} ${items.at(-1)}`;
}

export function buildPageDescription(
  page: { name: string },
  site: { name: string },
  blocks: { type: BlockType; visible: boolean }[],
  lang: Lang,
): string {
  const labels = [...new Set(
    blocks
      .filter(b => b.visible)              // honour the renderer's visibility
      .map(b => BLOCK_LABEL[b.type])
      .filter(Boolean)
      .map(k => t(k, lang)),
  )];
  if (!labels.length) {
    return t('og.discoverPage', lang, { page: page.name, site: site.name });
  }
  return t('og.modularPageWithContents', lang, {
    page: page.name,
    site: site.name,
    contents: joinLocalized(labels, lang),
  });
}
```

Output examples (real, from the case-study site after the fix):

- `"Inici a Ràdio Desvern: notícies, podcasts, vídeos, el temps i galeria."`
- `"Història on Ràdio Desvern: gallery and podcasts."`

Distinct per page, factual, surfaces what the page actually
contains. Honour the same `show_on_desktop / show_on_mobile`
visibility flags the renderer uses, so blocks hidden from viewers
don't appear in the description. When no blocks have a mapped
label, fall through to a per-page-name fallback (`og.discoverPage`)
— don't emit nothing.

The same helper works for the homepage when the homepage is itself
a composed page. While you're there, also wire `og:image` from the
page's cover field — without it, social previews fall back to the
site logo.

## Canonical host strategy (multitenant / preview domains)

If the same content is reachable on multiple hosts — custom domain +
platform subdomain, preview deploys, legacy paths — pick one canonical
host and 301 the others. Decision:

- Tenant has `custom_domain` set → canonical = custom domain
- No custom domain → canonical = platform subdomain
- Legacy path-based URL → 301 to canonical

### 301 rules (request-level middleware)

Redirect `GET`/`HEAD` only. Skip redirect for:
- `/api/*` — client code bound to a specific host must keep working
- `/embed/*`, `/embeds/*` — iframes from third-party sites
- Asset download routes (`/media/*`, `/download/*`) — may have their
  own redirect logic already
- Non-idempotent methods (POST, PUT, etc.)

### `<link rel="canonical">`

Emit on every page as a belt-and-braces in case the 301 misses an edge.
Paginated / filtered pages should override canonical back to page 1.

## robots.txt

**Make it SSR-backed when hosts differ per tenant** — a static
`public/robots.txt` can't emit a per-host `Sitemap:` absolute URL.

### Minimal policy template

```
User-agent: *
Disallow: /api/
Disallow: /embed/
Disallow: /embeds/
Disallow: /admin/
Allow: /

# Always block these (low-signal scrapers)
User-agent: Bytespider
Disallow: /
User-agent: Diffbot
Disallow: /
User-agent: DataForSeoBot
Disallow: /
User-agent: PetalBot
Disallow: /

Sitemap: https://<canonical-host>/sitemap.xml
```

### AI crawler policy — decision required

Three archetypes: **Publisher** (allow everything, default for content
sites), **Content-protective** (block training crawlers, allow
retrieval — you appear in AI answers but not in model weights),
**Closed** (classic search only). The specific bot names, per-tier
blocklists, and decision questions are in
`references/ai-crawler-policy.md` — load it when choosing a policy.

## sitemap.xml

**Start simple**: one `<urlset>` with home + indexable pages. Only
graduate to a sitemap-index when:
- >10k URLs (spec caps at 50k per file)
- Need per-content-type grouping (episodes vs articles vs archives)
- Multiple hosts share one app → per-host sitemaps with an index

### Sitemap-index pattern

```
/sitemap.xml              → <sitemapindex> listing:
  /sitemap-main.xml       → home, static pages, top categories
  /sitemap-archives.xml   → tag pages, year archives
  /sitemap-content-1.xml  → articles / episodes, first 10k
  /sitemap-content-2.xml  → ... next 10k
```

### Helpers

Share one `xmlEscape` + date helper between sitemap and RSS generators
— full implementation in `references/rss-feeds.md`. Route helpers
(`renderSitemap`, `renderSitemapIndex`, `sitemapHeaders`) alongside.

### Key pitfalls

- **Never use `he.encode` or any HTML-entity encoder for XML.** XML
  only needs 5 characters escaped; `he.encode` aggressively escapes
  non-ASCII (`Ràdio` → `R&#xE0;dio`) — valid but inflates the feed by
  several KB per thousand items.
- **`<lastmod>` should reflect real content change**, not `updated_at`
  that ticks on any field touch.
- **Don't list the same URL twice** (`/?page=1` and `/`). Pick one.

## llms.txt / llms-full.txt

Proposal at [llmstxt.org](https://llmstxt.org/). **Cheap hedge, not a
traffic mechanism today.** Single-party proposal (2024, no W3C); none
of the major LLM crawlers fetch it on their own as of early 2026.
Tools (Cursor, Claude Code, some MCP integrations) fetch it when a
user pastes a URL, and providers may adopt it later.

- **`/llms.txt`** — short markdown index (one screen).
- **`/llms-full.txt`** — longer dump: content excerpts inlined so a
  tool can ingest the site without following links. Cap at ~30 KB.

Per-tenant on multitenant sites; URLs inside use the canonical host.
What moves AI-engine traffic today is classic SEO fundamentals +
citation-friendly content — see `references/geo-and-ai-citations.md`.

## Open Graph & Twitter Cards

Emit on every share-worthy page.

### Minimum set

```html
<meta property="og:title" content="..." />
<meta property="og:description" content="..." />
<meta property="og:url" content="<canonical URL>" />
<meta property="og:type" content="website|article|product|music.song|..." />
<meta property="og:image" content="<absolute 1200x630>" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:locale" content="<ll_CC>" />
<meta property="og:site_name" content="..." />
<meta name="twitter:card" content="summary_large_image" />
```

### Pitfalls

- **`og:url` MUST match `<link rel="canonical">`.** If they disagree,
  Facebook and LinkedIn cache one and serve another.
- **`og:locale` is full `ll_CC`** (`en_US`, `es_ES`, `ca_ES`, `fr_FR`),
  not just `ll`. Keep a map per language.
- **`og:image` must be absolute URL** and ≥1200×630 — Slack / X /
  LinkedIn fall back to tiny thumbnails otherwise.
- **Articles also emit** `article:published_time`, `article:modified_time`,
  `article:author`, `article:tag`.
- **Don't emit `<meta name="description">` from both your base
  layout and your OG component.** Two identical tags per page is a
  symptom of split ownership: layout author thought they owned the
  basic description, OG author added a "fallback" copy of the same
  thing. Pick one — `<meta name="description">` belongs in the
  layout (or whichever component owns `<head>` baseline); the OG
  component should only emit `og:*` and `twitter:*`. Easy to miss
  because both tags resolve to the same string in the common case;
  only diverges when one path passes `description` but not
  `ogDescription` or vice versa, leaving inconsistent dupes.

## JSON-LD structured data

One `<script type="application/ld+json">` per page (or one `@graph`
combining multiple schemas) in `<head>`. Use a reusable component
that **escapes `</` sequences** to prevent script-tag breakout:

```ts
const json = JSON.stringify(schema).replace(/<\//g, '<\\/');
// emit: <script type="application/ld+json">{json}</script>
```

Shared primitives (`publisher`, `breadcrumbList`, `secondsToIsoDuration`,
`canonicalHostFor`) — full signatures in `references/schemas-by-page-type.md`.

### Common fields on every schema

- `@context: "https://schema.org"`
- `url`: canonical URL
- `inLanguage`: actual language code
- `datePublished` / `dateModified`: ISO 8601. **Don't set both equal** —
  `dateModified` only matters when it differs.
- `publisher`: shared `Organization` block
- `mainEntityOfPage`: `{ "@type": "WebPage", "@id": <canonical> }`

For the full page-type → schema mapping (15+ schemas, shape notes per
type, `@graph` consolidation example, E-E-A-T author wiring,
`ProductGroup` variants, `NewsMediaOrganization`, and which schemas
Google retired as rich results — `HowTo` completely, `FAQPage` except
gov/health), load `references/schemas-by-page-type.md`.

## RSS feeds

Worth shipping when the site has a stream of content. Baseline is RSS
2.0 + `<atom:link rel="self">`. For podcasts, Podcasting 2.0 is the
modern bar — `<podcast:guid>` (UUID v5 at channel level),
`<podcast:chapters>`, `<podcast:transcript>`.

Full implementation (with the UUID v5 helper, both Node + Python, and
per-feed-type guidance) is in `references/rss-feeds.md`.

## `noindex` policy

Explicitly noindex to protect index quality:

- **Search-result pages** (user-supplied query → infinite unique URLs)
- **Embed pages** (iframed from third-party sites, no standalone value)
- **Admin / account / settings** pages
- **Paginated pages past page 1** — or canonicalize back to page 1,
  pick one approach, don't do both
- **Filter-stacked views** that create near-duplicate content
- **Preview / staging environments** (also robots.txt, also HTTP auth)

Pattern: a `noindex` prop on your layout that emits
`<meta name="robots" content="noindex, nofollow">`.

## Edge / middleware pitfalls

1. **Don't clobber route-level `Cache-Control`** in a final-response
   hook. Guard with:
   ```ts
   if (!response.headers.has('Cache-Control')) {
     response.headers.set('Cache-Control', 'public, max-age=300, ...');
   }
   ```
2. **Never cache 4xx/5xx at CDN.** Set
   `Cache-Control: private, no-cache, no-store` on non-2xx, or the CDN
   serves error pages for minutes after recovery.
3. **Always use absolute URLs** in cross-document payloads (sitemap,
   RSS, JSON-LD, Open Graph). Relative breaks when shared.
4. **Fetch tenant info once per request**, pass via `locals` / context.
   Don't re-fetch per SEO route.
5. **Accidental production `noindex`.** `<meta name="robots" noindex>`
   copied from staging is the most common SEO outage. Grep for it
   before shipping.

## State-of-SEO doc

Every project keeps `docs/seo.md` (or equivalent) with three tables:
✅ Implemented | ❌ Not implemented (priority + effort) | 🤔 Open
questions.

**Update after every SEO commit** — moves ❌ rows to ✅, adds new ❌
rows for deferred work, promotes 🤔 questions when they become
actionable. Without this, the next session forgets what's been done.

Template + priority guidance in `references/state-of-seo-template.md`.

## Starting on a new project

1. **Audit**: `curl` the homepage and a detail page; grep for
   `canonical|og:|description|application/ld|robots`. See what exists.
2. **Check `/robots.txt` and `/sitemap.xml`.** Both should exist and be
   valid.
3. **Create the tracker doc** (`docs/seo.md` at repo root). Use the
   template in `references/state-of-seo-template.md`. Fill ✅ with
   what's there, ❌ with priority-ordered gaps.
4. **Ship the baseline first** (title, description, canonical, robots,
   sitemap) before rich features.
5. **Then pick the highest-priority ❌ item** and execute.
6. **Update the tracker** on every commit.

For verification commands after each change, load
`references/verification-commands.md`.

## Backlog ideas worth tracking

When there's nothing urgent, consider (roughly highest-ROI first):

- **JSON-LD** for every primary content type (rich results)
- **E-E-A-T author pages** — `Person` schema with `sameAs` LinkedIn /
  Google Scholar / etc. Heavy weight in AI Overview citation
  decisions; near-free if you already have author bios.
- **AI-citation audit** — for news / blog / docs, check how your pages
  surface in ChatGPT / Claude / Perplexity for target queries. Load
  `references/geo-and-ai-citations.md` for the structural fixes.
- **Sitemap-index** when >10k URLs
- **Per-tenant RSS** aggregating content streams
- **IndexNow push on publish** — Bing + Yandex accept real-time URL
  submissions. No Google support; Bing traffic (+ Copilot citations)
  still non-trivial.
- **Video sitemap** when pages have video
- **Core Web Vitals pass** — font loading, image sizing (CLS), INP
  (<200 ms p75). Load `references/core-web-vitals.md`.
- **Google Search Console + Bing Webmaster** verification per
  canonical host — operational, not code.
- **Hreflang** — only when there are actually parallel translations
  or same-language-different-country targeting (e.g. `en-US` vs
  `en-GB`). Load `references/hreflang.md`; implementations break
  often, validate on every release.

## When NOT to use this skill

- **Pure API backends** with no HTML output.
- **App Store / Play Store ASO** — mobile app store optimization is a
  different discipline (keyword fields, screenshots, review velocity).
- **Internal tools / dashboards** not meant to be indexed (set
  `noindex` on everything and move on).
- **Ad-network / monetization tuning** — AdSense, ad density, and
  revenue optimization are a different domain. Note that ad-heavy
  layouts often tank Core Web Vitals; this skill covers the CWV
  side of that tradeoff but not the ad-ops side.
- **Link-building / outreach** — this skill covers what ships inside
  the codebase. Off-site SEO (backlinks, digital PR, directory
  submissions) is ops / marketing work.
