# Per-project-type SEO playbooks

Load this when starting SEO work on a specific vertical, or when the
user says "it's a <type of site>". Covers the SEO priorities, schemas,
and content-structure choices that actually move the needle for each
type — not just the schema name (see `schemas-by-page-type.md` for the
full schema reference).

Each playbook lists: what's unique to this vertical, priority baseline,
unique pitfalls, and a "minimum to ship" checklist.

## E-commerce / online shops

Built around the product detail page (PDP) as the machine-readable
contract between your store and Google Shopping / Merchant Center.
Product data gets ingested everywhere: Shopping tab, Google Images,
AI Overviews, Amazon Alexa, ChatGPT product research.

### Priorities (in order)

1. **Server-render the PDP** — price, stock, variants, reviews must
   be in the initial HTML. Merchant systems + AI crawlers don't run
   JS. Storefronts on Shopify / BigCommerce / Medusa get this; SPA
   PDPs commonly break it.
2. **`Product` or `ProductGroup` schema** with `offers` (price,
   priceCurrency, availability URL-form), `shippingDetails`,
   `hasMerchantReturnPolicy`, `sku`/`gtin`, `brand`. Shape details in
   `schemas-by-page-type.md`.
3. **`AggregateRating` + `Review`** when you have real reviews. Don't
   invent — Google's reviews policy is strict and violations trigger
   manual actions.
4. **Category / collection pages indexable** with `CollectionPage` +
   `ItemList`. Give each one unique intro copy; empty or boilerplate
   category pages are thin content.
5. **Merchant Center** feed running alongside structured data. The
   two should agree on price, availability, GTIN. When they diverge,
   Google distrusts both and your products flicker in/out of
   Shopping surfaces.
6. **Faceted navigation hygiene** — filter + sort combinations
   generate near-infinite URLs. `noindex, follow` on filtered views,
   canonicalize back to the base category, or use parameter handling
   in Search Console. Pick one strategy, not three.
7. **Internal search URLs** (`/search?q=…`) — always noindex.

### Pitfalls specific to e-commerce

- **Out-of-stock pages serving 404**: don't do it. `availability:
  OutOfStock` keeps the URL live and preserves link equity; 404'ing
  the product kills both. Only 404 permanently discontinued SKUs.
- **Product URLs tied to category**: `/electronics/phones/iphone-16`
  breaks the day you recategorize. Prefer `/p/iphone-16` or
  `/products/iphone-16` (flat) with breadcrumb-derived
  `BreadcrumbList` schema pointing at the category.
- **Inconsistent variant handling**: pick either "one URL per
  product, variants in picker" or "one URL per variant" and stick to
  it. Mixing both creates duplicate content.
- **Price / availability drift** between the visible page and JSON-LD:
  the JSON-LD must come from the same data source as the rendered
  page. Google re-crawls price-eligible URLs aggressively; stale
  JSON-LD pulls the whole product out of Shopping results.

### Minimum to ship

- [ ] PDP server-rendered with complete `Product` schema
- [ ] `offers.availability`, `shippingDetails`, `hasMerchantReturnPolicy`
- [ ] Category pages with unique intro copy, `CollectionPage` schema
- [ ] Sitemap lists only canonical product URLs (no `?color=` variants)
- [ ] Merchant Center feed matching the PDP data
- [ ] Faceted nav handled (noindex / canonical / param config)
- [ ] `/search` noindexed

## News / magazines / journalism sites

Google News is now **fully algorithmic** — manual applications were
deprecated in October 2025. Inclusion depends on emitting the right
structured-data and publisher-trust signals. AI Overviews favor news
sources with strong E-E-A-T; weak author attribution is the most
common missed lever.

### Priorities (in order)

1. **`NewsMediaOrganization` on the homepage** with the full trust
   block: `correctionsPolicy`, `ethicsPolicy`, `ownershipFundingInfo`,
   `diversityPolicy`, `missionCoveragePrioritiesPolicy` — each one a
   URL pointing at a real policy page, not a placeholder. Policy
   pages should be indexable themselves.
2. **`NewsArticle`** on every article with: `headline` (≤110 chars),
   `author` as `Person` (not a faceless "Editorial team"), image ≥
   1200×675 photojournalism, `datePublished`, `dateModified` only when
   content changed, `publisher` referencing the
   `NewsMediaOrganization` by `@id`.
3. **Author bios** — real pages, one per author, `Person` schema
   with `sameAs` to LinkedIn / Google Scholar / Mastodon / X / byline
   archives. Identifiable authors are the heaviest single lever for
   both Google News inclusion and AI Overview citation.
4. **AI-content disclosure** when applicable. Google's 2026 news
   policy expects a visible, machine-readable note when AI assisted
   generation. Hidden AI content gets down-ranked when detected.
5. **News sitemap** (`<news:news>` namespace) for articles ≤ 48 h
   old, in addition to the main sitemap. Google fetches the news
   sitemap aggressively for Top Stories surfaces.
6. **Timestamps** — `datePublished` matches the visible byline;
   `dateModified` only when the article materially changed. Don't
   fake it. See `schemas-by-page-type.md` → NewsArticle for field
   specs.
7. **Core Web Vitals** — news audience is mobile-heavy; ad-heavy
   layouts tank LCP and CLS. Budget JS/ads against the CWV floor
   (see `core-web-vitals.md`).

### Pitfalls specific to news

- **Author = organization** — Google prefers a named byline. Fall
  back to `Organization` as author only for true staff / wire
  content.
- **Recycled stock images with text overlays** in the lead image
  field — news rich results drop them. Photojournalism (no logos,
  no captions baked in, ≥ 1200×675) is the baseline.
- **Missing corrections policy** — without a URL-backed
  `correctionsPolicy` in the publisher schema, Google treats the
  site as a low-quality outlet regardless of content.
- **Taxonomy pages** (tag / section indexes) — these are the second
  entry point for Google News. Make each `section/<topic>` URL have
  a unique description + indexable tag archive sitemap.

### Minimum to ship

- [ ] `NewsMediaOrganization` on homepage with full policy URLs
- [ ] Corrections, ethics, ownership policies live at their URLs
- [ ] `NewsArticle` on every article with `Person` author
- [ ] Author bio pages per author with `Person` schema + `sameAs`
- [ ] News sitemap for ≤48 h old articles
- [ ] AI-content disclosure visible + structured when applicable
- [ ] Mobile Core Web Vitals pass on article detail template

## SaaS / marketing landing pages

Less about rich results (there's no `Product` snippet for B2B SaaS),
more about being the best result for bottom-of-funnel keywords and
getting cited by AI when users ask "what's the best <tool> for <job>".

### Priorities (in order)

1. **Unique `<title>` + `<meta description>`** per page — the marketing
   site is typically 10-30 pages, so each can be hand-tuned.
   Outcome-first phrasing beats feature dumps ("Cut NPS-survey response
   time 4×" > "Real-time survey platform").
2. **`Organization` + `WebSite` + `SearchAction`** on homepage. Add
   `SoftwareApplication` (or `Service` for consulting) to mark the
   product type.
3. **`BreadcrumbList`** on secondary pages.
4. **`Person` schema on founder / leadership bios** — links outbound
   to LinkedIn / scholarly work / past employers drive both E-E-A-T
   and AI Overview citation probability.
5. **Pricing page indexable** — users explicitly search for "<product>
   pricing". Keep the tier labels + price points in the initial HTML,
   not behind a calculator.
6. **Hub-and-spoke content** — one pillar page per major topic, linked
   to 5-15 detailed supporting posts. Topical depth is a stronger
   2026 signal than individual page authority.
7. **Bottom-of-funnel keywords** — "vs" pages, "alternatives to"
   pages, integration pages. These convert disproportionately well
   and AI engines cite them when users ask comparative questions.
8. **Case studies with numbers** — original data is the highest
   correlation with AI Overview citations. "Reduced churn 23%"
   specific numbers + named customers get picked up.

### Pitfalls specific to SaaS landing

- **Docs on a subdomain** (`docs.example.com`) — whether to treat as
  one site or two. If it's one brand, canonical consolidation + cross-
  linking; don't compete with yourself. Common mis-setup: the main
  marketing site and the docs both rank for the same how-to queries,
  splitting equity.
- **Login / app subdomain leaking** — `app.example.com/` often
  returns a login page indexable by default. Noindex the entire
  app-subdomain via robots.txt + meta.
- **Changelog pages** — worth indexing (link equity from release
  announcements) but each entry should be individually addressable
  with its own `<h2 id=…>` anchor. AI engines cite version-specific
  releases, not "see latest".

### Minimum to ship

- [ ] Unique title + description per marketing page
- [ ] `Organization` + `WebSite` with `SearchAction`
- [ ] `SoftwareApplication` or `Service` for the product
- [ ] Founder / team bios with `Person` + `sameAs`
- [ ] Pricing page indexable
- [ ] At least 2-3 pillar pages with supporting spokes
- [ ] App subdomain noindexed

## Local business / single-location sites

The Google Business Profile (GBP) is the heaviest lever for local-pack
ranking — usually more impactful than the website itself. Schema on
the site is the cheap half; GBP maintenance is the heavier half.

### Priorities (in order)

1. **GBP claim + verification** (operational, not code) — if not done,
   nothing else matters.
2. **NAP consistency** — Name, Address, Phone exactly matching
   across: the website footer, `LocalBusiness` schema, GBP, and every
   directory the business appears in (Yelp, Apple Maps, Facebook,
   Bing Places, industry-specific directories). Mismatches
   downgrade local rank.
3. **`LocalBusiness` schema** (or most-specific subtype — `Restaurant`,
   `MedicalBusiness`, `AutoRepair`, `HomeAndConstructionBusiness`, etc.)
   with `address`, `geo`, `openingHoursSpecification`, `telephone`,
   `priceRange`, `aggregateRating`.
4. **Location page per physical location** for multi-location
   businesses. Each URL should have: the full NAP, local area
   references in body copy, its own `LocalBusiness` schema with the
   correct `geo` for that location, embedded map.
5. **Service / product pages** for each major offering, with
   location + service crossover ("plumber near <city>" → dedicated
   page). Don't cram service pages into the homepage.
6. **Reviews on-site** — embed GBP reviews or collect first-party
   reviews, display with `AggregateRating`. Reviews are the #1 local
   conversion driver.
7. **Mobile + CWV** — local users are overwhelmingly mobile (maps,
   directions, click-to-call). LCP on mobile matters more than
   anything else.

### Pitfalls specific to local

- **Keyword stuffing in GBP business name** — Google is enforcing
  hard against this in 2026. "Joe's Plumbing" is the name; "Joe's
  Emergency 24 Hour Plumbing Drain Cleaning" is a suspension risk.
- **Service area vs storefront** — pick one mode in GBP. If you're
  service-area (plumber visiting customers), hide the physical
  address in GBP; if you're storefront (salon), show it. Mixed signals
  confuse the local algorithm.
- **Duplicate GBP listings** — a common mess after ownership changes.
  Consolidate before building out schema; serving clean data to a
  duplicate profile just prolongs the confusion.
- **Scraped / fake reviews** — Google detects patterns and penalizes.
  Organic review velocity > spikes.

### Minimum to ship

- [ ] GBP claimed, verified, NAP matching site
- [ ] Homepage + contact page: `LocalBusiness` schema with full NAP,
      geo, hours, priceRange
- [ ] One indexable page per location (for multi-location)
- [ ] Service / product pages with "near <city>" variants where
      the business actually serves that area
- [ ] Reviews displayed with `AggregateRating`
- [ ] Mobile CWV pass

## Events / conferences / ticket sites

Google's Events rich result surfaces are carousel-heavy and
quality-sensitive. Incomplete `location` or `startDate` knocks an
event out of the surface entirely.

### Priorities

1. **`Event` schema** with: `name`, `startDate` (ISO 8601 with
   timezone), `location` (full `Place` with `address`, or
   `VirtualLocation` with `url`), `eventAttendanceMode`,
   `eventStatus`, `organizer`, `offers.url` + `offers.price` + `offers.
   availability` + `offers.validFrom`.
2. **Status updates** — when an event is postponed, cancelled, or
   moved online, update `eventStatus` immediately. Google surfaces
   cancellation badges to searchers.
3. **Recurring events** — emit one `Event` node per instance, not
   one parent with date ranges. Each instance has its own URL.
4. **Sold-out vs. cancelled** — `SoldOut` availability on `offers` is
   different from `EventCancelled` status; don't conflate.

### Pitfalls

- **Passing only city + state as location**: Google wants a full
  street address for in-person events. Missing `streetAddress` or
  missing `geo` drops the event from map-integrated surfaces.
- **Times without timezone**: `"2026-06-14T09:00:00"` is ambiguous;
  always use `"2026-06-14T09:00:00-05:00"` or similar.

## Blogs / content sites

The classic case. Modern priorities shift toward author authority + AI
citation readiness.

### Priorities

1. **`BlogPosting`** per post (subtype of `Article`).
2. **`Person` author** with `sameAs` — same lever as news sites.
3. **Topical clustering** — group posts into hubs; internal-link from
   pillar → spoke; makes every post discoverable in 1-2 hops.
4. **Freshness signals** — update evergreen posts, bump
   `dateModified` *only when the content actually changes*, add a
   "Last updated" visible line.
5. **Original data / quotes / primary sources** — the strongest
   predictor of AI citation. Aggregator-style roundups don't get
   cited; original experiments / interviews / benchmarks do.
6. **RSS feed** — still the lowest-effort distribution channel; feeds
   Apple News, Feedly, and many AI tools.

### Pitfalls

- **Tag page explosion** — tag archives with 1-2 posts are thin
  content. Merge tags below a threshold; noindex empty archives.
- **Date in URL** (`/2021/03/my-post`) — makes the content look
  stale regardless of real modification time. Prefer category + slug.
- **Syndicated content duplicating originals** — if reposting from
  another site, use `<link rel="canonical">` pointing at the
  original. Otherwise you cannibalize your own post by out-ranking
  the source.

## Video-first sites / YouTube-adjacent

`VideoObject` is required for video rich results, but the 2026 bar is
higher: the video must be the *main content* of the page.

### Priorities

1. **One video per page**, video visible + playable in the server-
   rendered HTML (not lazy-loaded-on-scroll).
2. **`VideoObject`** with `name`, `description`, `thumbnailUrl`
   (publicly accessible, no auth redirects), `uploadDate`, `duration`
   (ISO 8601 `PT15M30S`), and either `contentUrl` or `embedUrl`.
3. **30-second minimum duration** — Google filters short clips from
   rich-result eligibility.
4. **Video sitemap** (`<video:video>` namespace) when ≥ 10 videos.
5. **Transcript** on-page — improves accessibility + gives AI
   crawlers the content they can't extract from the video itself.
