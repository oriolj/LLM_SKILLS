# JSON-LD schemas by page type

Load this when you need to pick a schema for a specific page type, or
when wiring JSON-LD onto a site section for the first time.

## ⚠️ Deprecated / downgraded by Google (don't ship these for rich results)

Google phased these out — emitting them doesn't hurt ranking but won't
produce rich results, so don't invest effort chasing them:

- **`HowTo`** — fully retired (September 2023). No desktop or mobile
  rich results. Use plain HTML with headings + ordered list.
- **`FAQPage`** — Google shows the rich result only for "well-known
  authoritative government and health sites" (August 2023). On every
  other site, don't expect a rich snippet. May still be worth emitting
  on genuine Q&A content as a signal for AI ingestion (ChatGPT /
  Perplexity / Claude); it's cheap. Don't invent Q&A just to qualify.
- **`Book` Actions, `ClaimReview`, `Course Info` (list view), `Math
  Solver`, `Practice Problem`, `Vehicle`** — retired during the
  June 2025 rich-results cleanup. Check the current Google Search
  Gallery before adding any niche schema.

Retention is still fine — removing deprecated markup is low priority.
But don't add new instances on new projects.

All schemas share these framing fields — set them before any type-specific
properties:

```
@context:       "https://schema.org"
url:            <canonical URL>
inLanguage:     <ISO 639-1 code>
datePublished:  <ISO 8601>
dateModified:   <ISO 8601, only if it actually differs from datePublished>
publisher:      <shared Organization block>
```

## Page type → schema(s)

| Page                        | Schema(s)                                                      |
|-----------------------------|----------------------------------------------------------------|
| Home / landing — generic    | `Organization` + `WebSite` (+ `SearchAction` if site has search) |
| Home — news publisher       | `NewsMediaOrganization` (extends `Organization`) + `WebSite`   |
| Home — SaaS / software      | `Organization` + `SoftwareApplication` (or `Product`)          |
| Home — local business       | `LocalBusiness` (with `address`, `geo`, `openingHours`, `aggregateRating`) |
| News / article detail       | `NewsArticle` + `BreadcrumbList` (+ `Person` for author)       |
| Blog post                   | `BlogPosting` (subtype of `Article`) + `BreadcrumbList`        |
| Product detail (single)     | `Product` + `Offer` (+ `AggregateRating`, `Review`) + `BreadcrumbList` |
| Product detail (variants)   | `ProductGroup` with `hasVariant: [Product, …]`, `variesBy`     |
| Category / collection page  | `CollectionPage` (+ `ItemList` of products)                    |
| Service / pricing page      | `Service` (for services) or `Product` (for paid SaaS)          |
| Event detail                | `Event` + `BreadcrumbList` (include `location`, `offers`)      |
| Podcast program / show      | `PodcastSeries` + `BreadcrumbList`                             |
| Podcast episode             | `PodcastEpisode` + `BreadcrumbList`                            |
| Radio site home             | `RadioStation` (with `BroadcastService` + `AudioObject` for the live stream) |
| Author / journalist bio     | `Person` (with `sameAs`, `jobTitle`, `knowsAbout`) — E-E-A-T   |
| Video page (primary video)  | `VideoObject` — must be main content; min 30 s duration        |
| Recipe                      | `Recipe` (nutrition, ratings, times)                           |
| Job posting                 | `JobPosting` (required: `title`, `datePosted`, `hiringOrganization`, `jobLocation`) |
| Course (self-paced)         | `Course` + `CourseInstance` (list of instances is deprecated)  |
| Any page with breadcrumbs   | `BreadcrumbList`                                               |
| Any page with live search   | `WebSite` with `potentialAction: SearchAction`                 |

## Shared primitives (extract into utils)

```ts
// Organization publisher — same block used by every article / episode / etc.
publisher(org) → {
  "@type": "Organization",
  name: org.name,
  url: org.canonicalUrl,
  logo: { "@type": "ImageObject", url: org.logo }
}

// Breadcrumb list from an array of { name, url } items
breadcrumbList(items) → {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: items.map((item, i) => ({
    "@type": "ListItem",
    position: i + 1,
    name: item.name,
    item: item.url,
  }))
}

// Duration → ISO 8601 (PT1H15M30S) for PodcastEpisode.duration / VideoObject.duration
secondsToIsoDuration(n) → "PT<H>H<M>M<S>S"

// Canonical host — prefer tenant.custom_domain, fall back to request origin
canonicalHostFor(tenant, fallback)
//   tenant.custom_domain ?? fallback
//   e.g. canonicalHostFor({ custom_domain: "radio.com" }, "https://sub.enacast.com")
//   → "https://radio.com"
```

## `@graph` consolidation

Instead of two `<script>` tags (one for the entity, one for breadcrumbs),
put them in one under `@graph`:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "@id": "<canonical>#article",
      "headline": "...",
      "publisher": { "@id": "<org>#org" }
    },
    {
      "@type": "BreadcrumbList",
      "@id": "<canonical>#breadcrumb",
      "itemListElement": [...]
    },
    {
      "@type": "Organization",
      "@id": "<org>#org",
      "name": "...",
      "url": "..."
    }
  ]
}
```

Benefits: one script tag, one payload, schemas cross-reference via `@id`.

## Shape notes per schema

### `NewsArticle` / `Article`

Required: `headline`, `image[]`, `datePublished`, `publisher`, `author`.
Google also uses `dateModified` when present. 2026 specifics:

- `image` — at least one image ≥1200×675 px for best eligibility;
  prefer photojournalism (no text overlays, watermarks, or promo
  graphics on news articles — Google penalizes).
- `author` — must be a `Person` with `name` at minimum. `url` to a
  real bio page and `sameAs` links to LinkedIn / Google Scholar /
  Mastodon / X strengthen E-E-A-T. See `geo-and-ai-citations.md` for
  why this is load-bearing for AI Overview citation.
- `dateModified` — set only when content materially changes. Don't
  fake recency. Google 2026 news guidelines flag auto-bumped
  timestamps (every article updated together without content changes)
  as a spam signal.
- `headline` — 110 char max for Google News; truncation in rich results.
- Use `NewsArticle` for timely news (launches, events, announcements);
  use `BlogPosting` for evergreen content (guides, reviews). This
  affects whether Google puts the page into its news surfaces.

### `NewsMediaOrganization`

Replaces `Organization` for news publishers — tells Google this is a
news site, which is one of the heavier 2026 signals for entering
Google News (applications were deprecated in October 2025; inclusion
is now fully algorithmic). Should include:

- Standard `Organization` fields: `name`, `url`, `logo`
  (`ImageObject` with `url`, `width`, `height`)
- `sameAs` — array of canonical social / directory URLs
- `address`, `contactPoint` — editorial contact
- `foundingDate`, `ownershipFundingInfo`, `diversityPolicy`,
  `ethicsPolicy`, `correctionsPolicy`, `actionableFeedbackPolicy`
  (URLs pointing at those policy pages — Google reads them)
- `missionCoveragePrioritiesPolicy` for editorial scope

Emit once on the homepage (or in every page's `@graph` via `@id`
reference) and reference from every `NewsArticle.publisher`.

### `PodcastEpisode`

Required: `name`, `url`, `datePublished`, `associatedMedia.contentUrl`
(audio URL), `partOfSeries` (pointing at `PodcastSeries`).
Recommended: `duration` (ISO 8601), `image`, `description`,
`inLanguage`.

### `RadioStation`

Core: `name`, `url`, `logo`, `areaServed`, `inLanguage`. To surface the
live stream, add a nested `broadcastService`:

```json
{
  "@type": "BroadcastService",
  "name": "<radio> live stream",
  "broadcastDisplayName": "<radio name>",
  "inLanguage": "<lang>",
  "audio": {
    "@type": "AudioObject",
    "contentUrl": "<stream URL>",
    "encodingFormat": "audio/mpeg"
  }
}
```

### `PodcastSeries`

Required: `name`, `url`. Recommended: `image`, `description`, `author`
(the host as a `Person`), `webFeed` (the program's RSS URL), and
`publisher` (the parent organization).

### `BreadcrumbList`

Always list from root to current page. Google wants `item` as a URL,
not an object, on the deepest breadcrumb items — keep them URLs.

### `Product`

Google Shopping rich results require at least: `name`, `image`,
`description`, `offers` (with `price`, `priceCurrency`,
`availability`). `aggregateRating` unlocks star snippets. For
e-commerce merchant listings (free Shopping exposure), also add:

- `brand` (`Brand` or `Organization`)
- `sku` and/or `gtin` / `mpn` — Google strongly prefers GTIN when
  the product has one. Required for some verticals.
- `offers.shippingDetails` — `OfferShippingDetails` with
  `shippingRate`, `shippingDestination`, `deliveryTime`. Surfaces
  free / fast shipping in shopping cards.
- `offers.hasMerchantReturnPolicy` — `MerchantReturnPolicy` with
  `returnPolicyCategory`, `merchantReturnDays`, `returnFees`.
  Surfaces "free 30-day returns" in shopping cards.
- `offers.availability` — use the full URL form
  (`https://schema.org/InStock`, `OutOfStock`, `PreOrder`,
  `BackOrder`). Google commonly logs warnings if you use the bare
  string.
- `offers.priceValidUntil` — ISO date when the price expires. Drives
  "deal ending" annotations.
- `review` (individual reviews) or `aggregateRating` (summary). One
  only — Google dedupes.

Google recommends putting Product structured data in the initial
server-rendered HTML — merchant systems don't reliably execute JS.

### `ProductGroup` (variants: same model, different color / size / capacity)

Use when the same conceptual product has multiple SKUs that share
most attributes but differ on one or two axes. Two deployment
patterns:

1. **All variants on one URL** (e.g. color picker on one page) — emit
   a single `ProductGroup` with `hasVariant: [Product, Product, …]`
   inside. Put shared fields (`brand`, `aggregateRating`,
   `hasMerchantReturnPolicy`, `shippingDetails`) on the
   `ProductGroup`; put variant-specific fields (`sku`, `offers`,
   `color`, `size`, `image` if different) on each child `Product`.
2. **Each variant on its own URL** — emit a `ProductGroup` node
   somewhere canonical, and on each variant's page emit a `Product`
   with `isVariantOf: { "@id": "<productgroup-id>" }`.

Required on `ProductGroup`: `productGroupID` (merchant ID / item
group ID), `variesBy` (array like `["https://schema.org/color",
"https://schema.org/size"]`), `hasVariant`.

### `Event`

Required: `name`, `startDate`, `location`. `endDate` and `offers`
strongly recommended. Google de-prioritizes events without clear
`location` data.

- `eventAttendanceMode` — `OfflineEventAttendanceMode`,
  `OnlineEventAttendanceMode`, or `MixedEventAttendanceMode`. For
  online/hybrid, `location` should be a `VirtualLocation` with `url`.
- `eventStatus` — `EventScheduled` (default), `EventRescheduled`,
  `EventCancelled`, `EventPostponed`, `EventMovedOnline`. Update when
  schedules change; Google surfaces cancellation badges.
- `organizer` — `Organization` or `Person`; surfaces in rich results.
- `offers.validFrom` — ISO datetime when tickets go on sale.

### `Person` — author / journalist / public figure (E-E-A-T)

The heaviest lever for Google News + AI Overview citation quality.
Author bio pages should emit a `Person` schema and be linked from
every article's `author` field. Include:

- `name`, `url` (link to bio page), `image`
- `jobTitle`, `worksFor` (`Organization`)
- `sameAs` — canonical URLs for: LinkedIn, Google Scholar (for
  academic / technical authors), Mastodon / X, personal site,
  Wikipedia if applicable. Each one that resolves to a real identity
  adds verifiability.
- `knowsAbout` — array of topics / `Thing` URIs (e.g. subject-area
  Wikipedia links). Contributes to topical authority.
- `alumniOf`, `award` — optional, boost authoritativeness.

Emit on the bio page itself and reference by `@id` from each article:
`"author": { "@id": "https://site.com/authors/jane#person" }`.

### `LocalBusiness`

Required: `name`, `address` (`PostalAddress` with all fields),
`telephone`, `url`. Strong defaults:

- `geo` (`GeoCoordinates` with `latitude`, `longitude`) — required
  for map surfaces.
- `openingHoursSpecification` — array of `OpeningHoursSpecification`
  objects; prefer this over the legacy `openingHours` string.
- `priceRange` — e.g. `"$$"`.
- `areaServed` — for service-area businesses.
- `servesCuisine` for restaurants (use `Restaurant` subtype),
  `medicalSpecialty` for clinics (use `MedicalBusiness` subtype), etc.
  Always pick the most specific subtype you qualify for.
- `aggregateRating` + `review` — strong ranking signal in the local
  pack when you have genuine reviews.

NAP (Name, Address, Phone) must match exactly across the site, Google
Business Profile, and every directory the business appears in —
mismatches downgrade local rank. LocalBusiness schema on the site is
the cheaper half of local SEO; the heavier half is GBP maintenance
(see `references/page-types.md` → Local business).

## What to skip

- `SpeakableSpecification` — needs manually curated section selectors;
  rarely worth the upkeep unless you have real voice-assistant traffic.
- `AuthorLanguage` / niche sub-properties — stick to core fields; rich
  results don't get better from obscure props.
- Author as an `Organization` on news sites — Google prefers `Person`
  with real byline. Only fall back to Organization when no byline.
- `HowTo`, `FAQPage` (outside gov/health), `ClaimReview`, `Book`
  actions — Google retired the rich results. See "Deprecated" section
  at the top of this file.
