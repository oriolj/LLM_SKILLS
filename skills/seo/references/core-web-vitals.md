# Core Web Vitals + image SEO

Load this when the user asks about Core Web Vitals, PageSpeed, LCP /
INP / CLS, or image-related SEO (formats, dimensions, `alt`, `<img>`
attributes). These two topics share the same root: what the browser
renders and how fast, both as a ranking signal and a user-experience
baseline.

## The three Core Web Vitals (2026 thresholds)

| Metric | Good (p75) | Needs improvement | Poor   | What it measures |
|--------|-----------|-------------------|--------|------------------|
| LCP    | ≤ 2.5 s   | 2.5–4.0 s         | > 4 s  | Largest Contentful Paint — time until the biggest above-the-fold element finishes loading |
| INP    | ≤ 200 ms  | 200–500 ms        | > 500 ms | Interaction to Next Paint — responsiveness to real user interactions (replaced FID on March 12, 2024) |
| CLS    | ≤ 0.1     | 0.1–0.25          | > 0.25 | Cumulative Layout Shift — visual stability during load |

**Evaluation:** Google uses the p75 of real-user measurements from the
Chrome User Experience Report (CrUX). Lab scores (Lighthouse, PSI
"Analysis") are a debugging tool; CrUX is what ranks. To pass, at
least 75% of visitors to a URL must get "good" on all three.

## LCP — what usually dominates it

The LCP element is typically the hero image, the main `<h1>` + first
paragraph, or a video poster. Speed it up by:

1. **Preload the LCP image** — `<link rel="preload" as="image" href="...">`
   in `<head>`. Skips the HTML-parse → image-discovery gap.
2. **`fetchpriority="high"`** on the LCP `<img>`. The browser fetches
   it ahead of other images.
3. **Modern image formats** — AVIF (best compression) or WebP
   (broader support). JPEG only as fallback.
4. **Responsive `srcset`** — serve the right size per viewport; avoid
   downloading a 2000px image on mobile.
5. **CDN with image-optimization** — Cloudflare Images, Vercel Image,
   Next Image, `imgproxy`. Format conversion + resize on the edge.
6. **Server response time** — if TTFB is > 500 ms, no amount of
   front-end tuning helps. Fix backend latency / CDN caching first.
7. **Font loading** — use `font-display: swap` on custom fonts, and
   preload the critical woff2. A blocking font stall delays text LCP.
8. **Hero video autoplay** — if the LCP is a video poster, make the
   poster image optimized separately; the video loads after.

## INP — what usually dominates it

INP measures the worst interaction on the page (p98 roughly). One
slow click or tap tanks the whole score. Usual suspects:

1. **Heavy JavaScript on main thread** — third-party analytics,
   tagging, A/B test frameworks. Audit: Chrome DevTools → Performance
   → record a click → look for long tasks.
2. **React hydration / rehydration** — after SSR, the JS bundle
   hydrates the page; clicks during the first 1-2 seconds can
   block. Partial hydration / islands (Astro, Qwik) dodges this.
3. **Synchronous layout work** inside click handlers. `yield` via
   `requestIdleCallback` or `scheduler.postTask` where possible.
4. **Input event handlers calling heavy libraries** — date pickers,
   chart redraws. Debounce, or defer to rAF.
5. **Third-party widgets** (chat, consent banners, social embeds) —
   often the single biggest INP regression. Lazy-load, or embed
   after first interaction.

## CLS — the usual fixes

Layout shift is almost always about elements appearing without
reserved space. Fix by:

1. **Width/height on every `<img>` and `<video>`.** The browser
   reserves intrinsic-ratio space before the asset loads. Missing
   dimensions is the #1 CLS bug.
2. **Aspect-ratio boxes for embeds** — YouTube iframes, Twitter
   cards, ads. Wrap in `aspect-ratio: 16/9;` or equivalent.
3. **Font fallback metric matching** — `size-adjust` / fallback font
   tuning so the swap doesn't reflow text. Modern CSS handles most
   of this via `font-display: swap` + `size-adjust`.
4. **No content injected above existing content** after initial
   render. If you load a promo banner / cookie bar, reserve space
   from SSR or insert *below* the fold.
5. **Skeleton UIs that match final layout** — don't swap a
   200px-tall skeleton for a 600px-tall article.

## Image SEO (tied to CWV)

### Required for every `<img>`

- **`alt` attribute** — descriptive for content, `alt=""` for
  decorative. Missing alt is an accessibility + SEO bug.
- **`width` and `height`** — intrinsic dimensions prevent CLS (covered
  above).
- **`loading="lazy"`** on below-the-fold images; default eager for LCP.
- **`decoding="async"`** on non-critical images.

### Format + size strategy

- **Modern formats first** — AVIF → WebP → JPEG (fallback). Deliver
  via `<picture>` with `type="image/avif"` first.
- **Responsive `srcset`** at 1×, 2×, 3× for common viewport sizes.
- **Quality ~80%** for JPEG/WebP — above that is all file-size, no
  visual gain.
- **SVG for icons / logos / simple illustrations.**

Schema-specific image dimension requirements (`Article.image`,
`Product.image`, `VideoObject.thumbnailUrl`, etc.) live in
`schemas-by-page-type.md`. `og:image` specifics follow because it's
not a schema.

### `og:image` specifics

Separate from content images:

- **Absolute URL** (no relative paths — social scrapers don't resolve
  them).
- **≥ 1200×630** — smaller dimensions trigger tiny-thumbnail fallback
  on Slack / LinkedIn / X.
- **Under 5 MB**, ideally under 1 MB.
- **JPEG or PNG** — AVIF / WebP are unevenly supported by social
  scrapers; use conservative formats for OG.
- **Force-refresh cache** after changing: Facebook Debugger /
  LinkedIn Inspector / Twitter Card Validator all cache aggressively.

## Common regressions to catch

- **New image-heavy feature** added without CWV audit — typical:
  infinite-scroll feed, new hero component.
- **Third-party script** added via GTM without review — chat widget,
  A/B test SDK, consent platform. Each costs ~100-300 ms INP on
  mobile.
- **Bundle size creep** — every unrestrained bundle grows. Budget
  the main JS under 150 KB compressed for content sites, 300 KB for
  apps.
- **Font additions** without preload — marketing team adds a second
  font, LCP tanks.

## Verification

PSI mobile + CrUX is the source of truth; lab metrics (Lighthouse,
synthetic runs) differ from what ranks. Validator URLs listed in
`verification-commands.md` → Performance section. For live INP
debugging: Chrome DevTools → Performance → record interaction → look
for long tasks > 50 ms.
