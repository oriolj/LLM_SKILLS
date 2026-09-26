# Static-site performance, Core Web Vitals and SEO: research notes (2026-09-26)

Sources are dated as "(src: page, last updated/published date)". [V] = fetched and verified on a primary source this session. [U] = from secondary sources only, or not verified.

## A. Core Web Vitals now

### Metrics and thresholds [V]
- LCP ≤ 2.5 s good, > 4 s poor. INP ≤ 200 ms good, > 500 ms poor. CLS ≤ 0.1 good, > 0.25 poor. Each is assessed at the **75th percentile**, split by mobile and desktop (src: web.dev/articles/vitals, updated 2024-10-31). FID was retired when INP became stable in March 2024.
- **Many 2026 blog posts claim Google lowered the LCP threshold to 2.0 s. This is FALSE.** No web.dev, Chrome or Search Central source says so; web.dev still states 2.5 s. Do not put 2.0 s in the skill as the Google threshold. It is fine as an internal stretch budget.
- web.dev says metric changes follow "a predictable, annual cadence". No new Core Web Vital was announced for 2025–2026.

### Soft navigations (SPA measurement), a recent change [V]
- The final origin trial ran in Chrome 147–149 (src: developer.chrome.com/blog/final-soft-navigations-origin-trial, 2026-04-20). It adds `SoftNavigationEntry` and `InteractionContentfulPaint`.
- The web-vitals library supports `reportSoftNavs: true` from Chrome 151+ (src: github.com/GoogleChrome/web-vitals README, fetched 2026-09-26).
- **CrUX and ranking use of soft-navigation data is undecided.** Chrome says it will decide after the API launches. This matters little for static multi-page Astro sites, where every navigation is a hard navigation.

### LCP subparts [V]
LCP breaks into four subparts. The target shares are TTFB ≈ 40 %, resource load delay < 10 %, resource load duration ≈ 40 % and element render delay < 10 % (src: web.dev/articles/optimize-lcp, 2025-03-31). The LCP resource must be discoverable in the initial HTML, carry `fetchpriority="high"` and never use `loading="lazy"`.

### INP attribution [V]
- INP has three phases: input delay, processing duration and presentation delay. The fixes are to break up long tasks and yield, batch DOM reads and writes, keep the DOM small and use `content-visibility` (src: web.dev/articles/optimize-inp, 2025-09-02).
- The web-vitals attribution build adds LCP subparts, INP with Long Animation Frame (LoAF) script attribution, and CLS largest-shift target. It is about 1.5 KB larger. `onFID` has been removed (src: web-vitals README).

### Field vs lab
- CrUX eligibility: the page must be publicly discoverable (200 status, indexable) and "sufficiently popular" at URL or origin level. Query strings are stripped (src: developer.chrome.com/docs/crux/methodology, updated 2024-06-20) [V].
- The CrUX data window is a **28-day rolling** window, and PSI shows p75 field data from it. This is widely documented, but the two CrUX pages I fetched did not state it explicitly [U, well-known]. A low-traffic small-business site will often have **no URL-level CrUX data** and fall back to origin level or nothing. In that case lab data (Lighthouse) plus our own RUM (the web-vitals library) is all we have.
- Lab tools (Lighthouse) cannot measure INP. Use TBT as its lab proxy.

### How much CWV weighs in ranking: Google's words [V]
(src: developers.google.com/search/docs/appearance/core-web-vitals, updated 2025-12-10)
- "This, along with other page experience aspects, aligns with what our core ranking systems seek to reward."
- "We highly recommend site owners achieve good Core Web Vitals for success with Search and to ensure a great user experience generally."

Interpretation: CWV is a real signal but a modest one, and relevance and quality dominate. Blog claims that INP became a "primary ranking signal in 2026" have no Google source [U, likely false].

### Lighthouse 13 (changed recently) [V]
(src: developer.chrome.com/blog/lighthouse-13-0, 2025-10-10)
- Released 2025-10-10. It reached PSI within a week and Chrome stable in version 143. It requires **Node 22.19+**.
- **Scoring is unchanged.** Old performance audits were removed from both the report and the JSON and replaced by "insight" audits shared with the DevTools Performance panel.

| New insight audit | Replaces |
|---|---|
| `lcp-discovery-insight` | prioritize-lcp-image, lcp-lazy-loaded |
| `lcp-phases-insight` | largest-contentful-paint-element |
| `image-delivery-insight` | modern-image-formats, uses-optimized-images, uses-responsive-images, efficient-animated-content |
| `render-blocking-insight` | render-blocking-resources |
| `document-latency-insight` | redirects, server-response-time, uses-text-compression |
| `network-dependency-tree-insight` | critical-request-chains, uses-rel-preconnect |
| `use-cache-insight` | uses-long-cache-ttl |
| `font-display-insight` | font-display |
| `cls-culprits-insight` | layout-shifts |
| `third-parties-insight` | third-party-summary |
| `modern-http-insight` | uses-http2 |

Other insights: `dom-size-insight`, `duplicated-javascript-insight`, `legacy-javascript-insight`, `interaction-to-next-paint-insight`, `viewport-insight`.

- Removed with no replacement: `offscreen-images`, `third-party-facades`, `preload-fonts`, `uses-rel-preload`, `font-size`, `no-document-write`, `uses-passive-event-listeners`, `first-meaningful-paint`.
- **Impact:** any Lighthouse CI assertion that names an old audit ID now breaks or silently passes, so update it to the insight ID.
- Performance budgets (`budget.json`) in Lighthouse core: the issue proposing their removal (#15203) was closed against milestone v12.0, so they were likely removed in Lighthouse 12. I did not verify this from release notes [U]. Lighthouse CI still supports its own `budgetsFile` and `resource-summary:<type>:(size|count)` assertions (src: lighthouse-ci docs/configuration.md) [V].

### bfcache [V]
(src: web.dev/articles/bfcache, updated 2026-07-02)
- Blockers: an `unload` listener (use `pagehide` instead), open IndexedDB, fetch, WebSocket or WebRTC connections at navigation time, and a non-null `window.opener` (use `rel=noopener`).
- `Cache-Control: no-store` historically blocked bfcache. Chrome is "working to change this" for non-sensitive pages. This change is recent and still in progress.
- Test with DevTools (Application → Back/forward cache) and the `notRestoredReasons` API.

### Rules for our skill (A)
1. Targets at p75 on mobile: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1. Our internal lab budget for static marketing pages is LCP ≤ 2.0 s on Lighthouse mobile and TBT ≤ 200 ms. Label it as ours, not Google's.
2. Field data is the truth for SEO. Check CrUX or PSI (28-day p75) first. If there is no CrUX data, ship the web-vitals attribution build to our own analytics rather than trusting one Lighthouse run.
3. Run Lighthouse at least 3 times (5 in CI) and take the median. Single runs are noisy.
4. Pin Lighthouse ≥ 13 on Node ≥ 22.19. When upgrading, migrate CI assertions to `*-insight` audit IDs.
5. Diagnose LCP by subpart. If load delay is > 10 % of LCP, it is a discovery problem (preload/fetchpriority); if render delay is > 10 %, it is render-blocking CSS, JS or fonts.
6. Never register `unload`. Keep every page bfcache-eligible, and verify this in DevTools once per release.
7. Do not cite "LCP 2.0 s" or "INP is now primary" as Google policy. Quote the Search Central wording.

## B. Static-site performance techniques

### Images
- Use AVIF first with a WebP fallback. AVIF has been Baseline "newly available" since 2024 and is typically about 20–25 % smaller than WebP at equal quality. Encoding is slow (seconds per large image), so encode at build time, never per request (src: web.dev/learn/images/avif; secondary sources for the numbers) [V support / U numbers].
- Set `width` and `height` (or `aspect-ratio`) on every image to prevent CLS [V].
- Use `srcset`/`sizes` so a phone never downloads a desktop hero. Astro 5.10+ has `image.layout` (`constrained`, `full-width`, `fixed`) and `image.responsiveStyles`, which generate srcset and sizes (src: Astro config reference) [V].
- For the LCP image: `fetchpriority="high"` and eager loading on **exactly one image**. Put `loading="lazy"` on everything below the fold. Lazy images start loading about 1250 px from the viewport on 4G and 2500 px on 3G (src: web.dev/articles/browser-level-image-lazy-loading) [V].
- Note that Lighthouse 13 removed `offscreen-images`, so lab tests no longer flag missing lazy loading. Grep for it instead.
- `content-visibility: auto` on long below-the-fold sections reduces rendering work and helps INP presentation delay. Pair it with `contain-intrinsic-size` or it causes CLS and scrollbar jumps [V for the INP link].

### Fonts
- Use WOFF2 only, subset to the needed `unicode-range` (e.g. latin plus latin-ext for ca/es/fr), and `font-display: swap` or `optional`. Use `optional` when zero-CLS matters more than the brand face on first view (src: web.dev/articles/font-best-practices, 2022-10-04; old but still the canonical page) [V].
- Self-host. web.dev says the speed difference versus Google Fonts is "unclear" provided a CDN and HTTP/2 are used. The deciding reasons for us are one fewer connection, no third-party request (the zero-cookies/GDPR angle, per the German court ruling on Google Fonts IP transfer), and cache control.
- Metric-override fallbacks (`size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`) remove swap CLS.
- **Astro 6 (2026-03-10) made the Fonts API stable** [V]. It downloads and self-hosts fonts from Google, Fontsource, Bunny, local files and others, generates optimized metric fallbacks by default (`optimizedFallbacks`), and has a `preload` option on `<Font/>`. Astro advises preloading only essential above-the-fold fonts. Use the Fonts API in every Astro ≥ 6 site instead of hand-written `@font-face` rules.
- Preload at most 1–2 font files (the ones the LCP text uses), with `crossorigin`.

### CSS
- Astro `build.inlineStylesheets` accepts `'auto'` (the default: inlines stylesheets under Vite's 4 KB limit), `'always'` or `'never'` [V]. For small marketing sites whose CSS per page is under about 20–30 KB compressed, `'always'` removes the render-blocking CSS request. Measure it, though, because inlined CSS is not cached across pages. This threshold is my judgement, not a documented rule [U].

### JavaScript
- Astro ships zero JS by default. Hydrate only islands that need it, and prefer `client:visible` or `client:idle` over `client:load`.
- Third parties are the usual TBT/INP killer (see `third-parties-insight`). Load analytics with `defer` or `async`, and prefer a small cookieless script (Umami or Plausible). Use no tag managers on marketing pages.
- `@astrojs/partytown` is still maintained by the Astro core team and depends on `@builder.io/partytown` 0.10 [V package / U health]. It suits heavy third parties such as GTM. It breaks scripts that need synchronous DOM access. Prefer not having the script at all.
- Load a CAPTCHA (Turnstile) only on pages that have a form.

### Video
- Use `preload="none"` (or `metadata`) plus a `poster` sized like the video. Never autoplay a big MP4 in the hero unless it is muted, short and small.
- Use a facade (for example lite-youtube-embed) for YouTube or Vimeo: a static poster that swaps in the iframe on click. Lighthouse 13 **removed** the `third-party-facades` audit, so nothing flags a raw embed anymore [V removal]. Enforce this in code review.

### Caching headers
- **Cloudflare Pages defaults:** `Cache-Control: public, max-age=0, must-revalidate` plus ETag. Assets are served from Tiered Cache, cached at the edge until the next deploy, and have an edge TTL of about 1 week that "can disappear at any time" (src: developers.cloudflare.com/pages/configuration/serving-pages) [V].
  - Override hashed assets in `_headers`:
    ```
    /_astro/*
      Cache-Control: public, max-age=31536000, immutable
    ```
  - `_headers` limits: 100 rules and 2,000 characters per line. It does **not** apply to Pages Functions responses (src: pages/configuration/headers) [V].
- **Vercel default:** `public, max-age=0, must-revalidate`. Its recommendations are `max-age=31536000, immutable` for hashed assets and `max-age=120, s-maxage=86400` for marketing HTML. `s-maxage` and `stale-while-revalidate` are consumed by the CDN and stripped before the response reaches the browser. The precedence is `Vercel-CDN-Cache-Control` > `CDN-Cache-Control` > `Cache-Control` (src: vercel.com/docs caching/cache-control-headers, updated 2026-09-14) [V].
  - Caveat: with a framework adapter that writes `.vercel/output/config.json` (the Build Output API, e.g. `@astrojs/vercel`), hand-written `vercel.json` routes, rewrites and functions can be overridden or ignored. Put headers where the adapter expects them and verify with `curl -I` after deploy (src: Astro issues #13900 and #9260, community reports) [U, verify per project].
- Leave HTML at `max-age=0` (revalidate) on Pages. The edge still serves it from cache, so no long browser TTL on HTML is needed.

### Compression and protocol [V]
- Cloudflare to visitors: the **Free plan compresses with Zstandard by default**, Pro and Business with Brotli, Enterprise with gzip. Compression Rules can override this. The minimum size is 50 bytes (src: developers.cloudflare.com/speed/optimization/content/compression). This is a recent change, so older docs say Brotli.
- HTTP/3 is on by default on Cloudflare [U, not re-verified this session].

### Early Hints (103) [V]
Early Hints is automatically on for all Pages domains and **cannot be disabled** on Pages. Pages generates `Link` headers from `<link rel=preload|preconnect|modulepreload>` that carry only `href`, `rel` and `as`. **Any extra attribute (for example `crossorigin` or `fetchpriority`) excludes that link.** Add explicit `Link:` lines in `_headers` if a font preload needs `crossorigin`. `! Link` disables only the automatic generation (src: pages/configuration/early-hints).

### Speculation Rules and prefetch [V]
- Chrome (src: developer.chrome.com/docs/web-platform/prerender-pages, updated 2026-01-23):
  - `prefetch` fetches the page; `prerender` renders it in a hidden tab.
  - Eagerness levels: `conservative` = pointer or touch down. `moderate` = 200 ms hover on desktop; on mobile (changed in 2025), a viewport heuristic of 500 ms after scrolling stops.
  - With `eager`, `moderate` or `conservative`, at most 2 speculations are kept (FIFO). `immediate` allows up to 50 prefetches and 10 prerenders.
  - Speculation is disabled under Save-Data, Energy Saver or memory pressure.
  - Requests carry `Sec-Purpose`. Prerender runs analytics, so defer pageview until activation.
  - Supported in Chromium only. Safari has it behind a flag; Firefox does not support it.
- Astro: `data-astro-prefetch` offers `hover` (default), `tap`, `viewport` and `load`; `prefetch.prefetchAll` turns it on for every link. It downgrades to `tap` on data-saver or slow connections and prefetches internal links only. The experimental `clientPrerender` flag uses Speculation Rules with eagerness (src: docs.astro.build/en/guides/prefetch) [V].
- Cloudflare **Speed Brain** adds a `Speculation-Rules` header (conservative prefetch). It is on by default on Free plans, but **not compatible with `pages.dev`** hostnames and breaks under a strict CSP (src: developers.cloudflare.com/speed/optimization/content/speed-brain) [V]. Do not stack it blindly with Astro prefetch; pick one.

### DNS and preconnect
Preconnect only to origins used in the first 1–2 s (at most about 2–3), because each one costs a connection. Self-hosting fonts and analytics removes most of the need. Lighthouse 13 folded `uses-rel-preconnect` into `network-dependency-tree-insight` [V].

### Budgets and CI
- Lighthouse CI [V]:
  - Presets: `lighthouse:recommended` and `lighthouse:no-pwa`.
  - `assertMatrix` applies different rules per URL pattern.
  - `aggregationMethod`: `median`, `pessimistic`, `optimistic` or `median-run`.
  - `budgetsFile` resource-summary assertions.
  - Example assertions: `categories:performance` `minScore`, `largest-contentful-paint` `maxNumericValue`.
- Suggested budgets for a static marketing page (our choice, not a standard):

| Page resource | Budget (compressed) |
|---|---|
| HTML | ≤ 50 KB |
| CSS | ≤ 50 KB |
| JS | ≤ 100 KB total (≤ 30 KB first party) |
| Fonts | ≤ 2 files, ≤ 100 KB |
| Hero image | ≤ 150 KB AVIF |
| Total | ≤ 1 MB |
| Third-party origins | ≤ 2 |

- Unlighthouse can crawl the whole site. Run it before launch and after big redesigns [U, not fetched].

### Rules for our skill (B)
1. Exactly one `fetchpriority="high"` image per page, which must be the LCP element. It must never be `loading="lazy"`, and it must be in the initial HTML (no JS or CSS background discovery).
2. Every `<img>` and `<video>` gets `width` and `height` or `aspect-ratio`. Every image below the first viewport gets `loading="lazy"` and `decoding="async"`.
3. Use AVIF with a WebP fallback, generated at build time (`astro:assets`). The hero stays ≤ 150 KB. Use `srcset`/`sizes` or Astro `layout`.
4. Fonts: on Astro ≥ 6 use the Fonts API; otherwise self-host WOFF2 subset to latin + latin-ext. Use `font-display: swap` with metric-override fallback, and preload ≤ 2 files. Make no request to fonts.googleapis.com.
5. Hashed assets get `Cache-Control: public, max-age=31536000, immutable` (in `_headers` on Pages, `vercel.json` or the adapter config on Vercel). HTML gets `max-age=0, must-revalidate` (edge-cached anyway). Verify both with `curl -sI` after deploy.
6. Zero JS by default. Every island needs a reason and uses `client:visible` or `client:idle`. Analytics is a deferred cookieless script. Load CAPTCHA only on form pages.
7. YouTube or Vimeo always sits behind a facade. Self-hosted video uses `preload="none"` plus a poster.
8. Enable Astro prefetch (hover or viewport). Use `clientPrerender` only after measuring, and gate analytics on prerender activation.
9. On Cloudflare Pages, remember Early Hints ignores preloads with extra attributes. Add a `_headers` `Link:` for a crossorigin font preload.
10. CI runs Lighthouse CI (≥ 13) at 5 runs with the median. Fail the build if performance is < 90 on mobile, LCP > 2500 ms, CLS > 0.1, TBT > 200 ms, or a resource-summary budget is exceeded. Assert on `*-insight` IDs only.

## C. SEO for small-business SaaS landing pages

### Structured data, 2025–2026 changes [V]
(src: developers.google.com/search/updates changelog, fetched 2026-09-26; faqpage doc, updated 2026-06-15)
- **FAQ rich results no longer appear in Google Search as of 2026-05-07.** The docs were removed on 2026-06-15. Since 2023 they had been limited to "well-known, authoritative government and health websites". Keeping on-page FAQ content is fine (it is useful to users and to AI answers), but do not expect a SERP feature from it. `FAQPage` markup is harmless but produces nothing in Google.
- **HowTo** rich results had already been removed in 2023. They do not appear in the current search gallery.
- Deprecated on 2025-06-12 and removed from the docs on 2025-09-09: Course info, Estimated salary, Learning video, Special announcement, Vehicle listing. ClaimReview was deprecated the same day. Book actions was deprecated, but its banner was removed on 2025-11-05 ("still in use").
- Practice problem structured data was deprecated on 2025-11-05, with support ending January 2026.
- Sitelinks search box was dropped in October 2024. Since January 2025, breadcrumbs show on desktop only.
- Still useful for a SaaS site: `Organization` (logo, sameAs), `SoftwareApplication` (the "Software app" feature is still in the gallery), `Product` with `Offer` for pricing, `BreadcrumbList`, `Review snippet` (only for genuine first-party reviews; a July 2026 guideline targets fake and undisclosed incentivized reviews), `LocalBusiness` for a physical shop, `Article` for the blog, and `VideoObject` (`creator` was added 2026-09-24).
- The search gallery (updated 2026-06-15) lists about 28 features.

### AI Overviews / AI Mode and llms.txt [V]
- Google: "There are no additional requirements to appear in AI Overviews or AI Mode, nor other special optimizations necessary." Also: "You don't need to create new machine readable files, AI text files, or markup". There is no special schema (src: search/docs/appearance/ai-features, updated 2025-12-10).
- Google's generative-AI optimization guide (published 2026-05-15, updated 2026-07-10) says GEO and AEO are "still SEO". Chunking, llms.txt, long-tail keyword variants and special schema are listed as unnecessary. A page must be indexed and snippet-eligible to be used.
- Changelog, 2026-06-15: llms.txt files "aren't needed for Google Search" and do not affect rankings.
- AI Mode counts toward Search Console totals (2025-06-16). There is no separate filter for it.
- Controls: `nosnippet`, `data-nosnippet`, `max-snippet` and `noindex` limit use in AI features. The `Google-Extended` token controls use for training and grounding in other Google products, not Search AI features.
- Evidence on llms.txt beyond Google [U, secondary sources]:
  - Log studies (Ahrefs, others, 2026) report that major AI crawlers almost never fetch it.
  - Perplexity reportedly uses it.
  - IDE agents and MCP tooling do fetch it.
  - Verdict: cheap to ship for docs sites and developer-facing products; zero expected SEO value for a small-business landing page.

### Quality systems [V]
- The helpful content system is no longer separate. Google now points to a whole-site self-assessment within core updates. Smaller core updates happen unannounced. Recovery "could take several months", or until the next core update (src: core-updates doc, 2025-12-10).
- People-first guidance: "trust is most important". Show Who, How and Why (bylines and author pages, disclosure of AI use). Mass-produced or AI content made to manipulate rankings is spam (src: creating-helpful-content, 2025-12-10).
- Site reputation abuse (third-party content published on a trusted host to rank) remains a spam policy. It was updated in August 2026, including an EEA-specific enforcement approach (changelog 2026-08-28). I could not read the post body, so the details are unverified [U]. New spam policy on 2026-04-13: "back button hijacking".
- E-E-A-T for a small SaaS:
  - A real company identity, meaning the LSSI aviso legal with CIF and address.
  - Named founders and team.
  - Real customer logos and testimonials with names.
  - Your own screenshots and data, not stock images.
  - A pricing page.
  - Contact details.
  - Consistent `Organization` sameAs links.

### Technical basics (well established; no 2025–26 changes found)
- One unique `<title>` of about 50–60 characters, a meta description of about 150–160 characters (Google rewrites it often), and one `<h1>` per page.
- A self-referencing canonical on every page, and a single host (redirect www or apex, and http to https).
- `sitemap.xml` with only canonical, indexable, 200-status URLs and accurate `lastmod`, submitted in Search Console. `robots.txt` points to it.
- hreflang [V] (src: search/docs/specialty/international/localized-versions):
  - Use one method only (HTML, HTTP header or sitemap).
  - Every version lists itself **and** all the others; missing return links make Google ignore the set.
  - Add an `x-default`.
  - Codes are ISO 639-1 language, optionally followed by an ISO 3166-1 region (`ca`, `es`, `es-ES`). Never a region alone.
  - Each canonical must point to its own language version, never across languages.
- Search Console essentials:
  - Verify with a Domain property through DNS.
  - Submit the sitemap.
  - Check the Page indexing report, CWV report and Manual actions.
  - Use URL Inspection after launch.
  - Use the Change of Address tool when moving domains (the June 2026 update covers domain variants).
- Local SEO, if the business has a physical shop: a Google Business Profile, the same name, address and phone number on the site, and `LocalBusiness` markup. Local business query support in aggregator units was added 2026-09-18 [V changelog].

### How performance feeds SEO
CWV is part of the page-experience signals that "core ranking systems seek to reward". It is modest but real, and it acts as a tiebreaker between similarly relevant pages. The bigger indirect effects are crawl efficiency (fast TTFB and small HTML), user behaviour, and conversion. There is no Google source for "fast site = big ranking jump", so do not promise one.

### Rules for our skill (C)
1. Every page has a unique title (≤ 60 characters, with the product name), a meta description (≤ 160 characters), exactly one `<h1>`, a self-canonical, `og:*` tags and a 1200×630 og:image.
2. JSON-LD: `Organization` site-wide, `SoftwareApplication` or `Product`+`Offer` on the pricing and home pages, `BreadcrumbList` on deep pages. Validate with the Rich Results Test. **Do not add FAQPage or HowTo expecting rich results.** Both are gone (FAQ as of 2026-05-07). Keep FAQ content as visible HTML.
3. Multilingual sites need reciprocal hreflang including a self link and `x-default`, per-language canonicals, and ISO 639-1 codes. Check with a crawler before launch.
4. `sitemap.xml` holds only canonical 200 URLs with real `lastmod`. Submit it in a Search Console Domain property and look at Page indexing 7 days after launch.
5. There is no special GEO/AEO work for Google: indexable, snippet-eligible, unique, people-first content is the whole recipe. llms.txt is optional, only for docs or developer products, and never claimed to help rankings.
6. Show E-E-A-T concretely: legal identity page, named people, real testimonials and logos, original screenshots, visible contact and pricing, and disclosed AI use.
7. Watch Search Console's CWV report (field data) monthly. Tie a performance regression to a deploy through the CI Lighthouse history.

## References fetched this session
- https://web.dev/articles/vitals (2024-10-31)
- https://web.dev/articles/optimize-lcp (2025-03-31)
- https://web.dev/articles/optimize-inp (2025-09-02)
- https://web.dev/articles/bfcache (2026-07-02)
- https://web.dev/articles/font-best-practices (2022-10-04)
- https://web.dev/articles/browser-level-image-lazy-loading
- https://developers.google.com/search/docs/appearance/core-web-vitals (2025-12-10)
- https://developers.google.com/search/docs/appearance/ai-features (2025-12-10)
- https://developers.google.com/search/docs/fundamentals/ai-optimization-guide (2026-07-10)
- https://developers.google.com/search/updates (changelog through 2026-09-24)
- https://developers.google.com/search/docs/appearance/structured-data/faqpage (2026-06-15)
- https://developers.google.com/search/docs/appearance/structured-data/search-gallery (2026-06-15)
- https://developers.google.com/search/docs/appearance/core-updates (2025-12-10)
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content (2025-12-10)
- https://developers.google.com/search/docs/specialty/international/localized-versions
- https://developer.chrome.com/blog/lighthouse-13-0 (2025-10-10)
- https://developer.chrome.com/blog/final-soft-navigations-origin-trial (2026-04-20)
- https://developer.chrome.com/docs/web-platform/prerender-pages (2026-01-23)
- https://developer.chrome.com/docs/crux/methodology (2024-06-20)
- https://github.com/GoogleChrome/web-vitals
- https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md
- https://docs.astro.build/en/reference/configuration-reference/
- https://docs.astro.build/en/guides/prefetch/
- https://docs.astro.build/en/guides/fonts/
- https://astro.build/blog/astro-6/ (2026-03-10)
- https://developers.cloudflare.com/pages/configuration/headers/
- https://developers.cloudflare.com/pages/configuration/early-hints/
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/speed/optimization/content/compression/
- https://developers.cloudflare.com/speed/optimization/content/speed-brain/
- https://vercel.com/docs/headers/cache-control-headers (2026-09-14)

## Unverified or flagged items
- The "LCP threshold now 2.0 s" and "INP primary ranking signal 2026" claims come from SEO blogs with no Google source. Treat them as false.
- The 28-day CrUX window is standard knowledge, but no page fetched this session states it.
- Removal of `budget.json` from Lighthouse core in v12 is inferred from issue #15203 and its milestone.
- I could not read the body of the August 2026 site-reputation policy update.
- llms.txt crawler statistics come from third-party log studies (Ahrefs and others).
- The Vercel Build Output API override of `vercel.json` comes from community and issue reports, not official docs.
- HTTP/3 defaults on Cloudflare were not re-verified.
- DigitalOcean App Platform static hosting was not researched: no CDN, header or compression facts were collected.
