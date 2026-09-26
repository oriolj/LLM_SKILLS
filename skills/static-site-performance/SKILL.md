---
name: static-site-performance
description: Build and keep static marketing sites fast (Astro / SSG on Cloudflare Pages, Vercel, DigitalOcean App Platform) — the house performance budget, image / font / CSS / JS / video rules with thresholds, caching and compression headers per host, Early Hints and prefetch, what Lighthouse 13 no longer checks, the CI gate, and the traps we hit in production (Cloudflare Pages ignoring video Range requests so iPhones cannot play the MP4, soft 404s, JS-toggled menus causing CLS, same-name media stuck in a CDN, captcha scripts on every page, 5 MB stock backgrounds, sites that score Lighthouse 100 while scrolling sideways). Use when building or reviewing a static/marketing site's performance, adding images, fonts, video or third-party scripts, setting cache headers, choosing a host config, setting up Lighthouse CI or budgets, or when the user says "make the site faster", "performance", "page weight", "lighthouse", "web vitals on the landing", "cache headers", "the video does not play on iPhone". Measurement and per-metric fix loops live in core-web-vitals; search visibility in seo; the whole-site checklist in commercial-websites.
---

# Static-site performance

Performance on a static marketing site is mostly **decided at build time**:
what the HTML asks for, in what order, how big it is, and how long the CDN and
browser may keep it. This skill is the house rulebook for that. It sits
between three siblings:

| Need | Skill |
|---|---|
| Measure, read Lighthouse/CrUX, fix one metric in a loop | **core-web-vitals** |
| Titles, canonicals, hreflang, structured data, AI search | **seo** (performance is one of its inputs) |
| The whole commercial-site checklist, review and shipping | **commercial-websites** |

Sourced research behind these rules (dates, Google quotes, what changed in
2025–2026, what is unverified): [references/research-2026-09.md](references/research-2026-09.md).

## Targets

- **Google's thresholds (unchanged since 2024):** LCP ≤ 2.5 s, INP ≤ 200 ms,
  CLS ≤ 0.1, at the 75th percentile of real users, mobile and desktop
  separately. SEO blogs claiming "LCP is now 2.0 s" or "INP became a primary
  ranking signal" have no Google source: do not repeat them.
- **Our lab budget for a static marketing page** (ours, stricter on purpose):
  Lighthouse mobile performance ≥ 90 (median of 3–5 runs), LCP ≤ 2.0 s, TBT ≤
  200 ms, CLS ≤ 0.05, and:

| Resource (compressed) | Budget |
|---|---|
| HTML | ≤ 50 KB |
| CSS | ≤ 50 KB |
| JS | ≤ 100 KB total, ≤ 30 KB first party |
| Fonts | ≤ 2 files, ≤ 100 KB |
| LCP image | ≤ 150 KB |
| Whole first load | ≤ 1 MB |
| Third-party origins | ≤ 2 |

- **How much it matters for SEO**, in Google's words: Core Web Vitals "align
  with what our core ranking systems seek to reward" and Google "highly
  recommend[s]" good scores. A real but modest signal: a tiebreaker between
  equally relevant pages, plus crawl efficiency and conversion. Never promise
  a ranking jump from speed alone.

## Rules

**Images**
1. Exactly one `fetchpriority="high"` image per page, and it must be the LCP
   element, in the initial HTML (not a CSS background, not injected by JS),
   never `loading="lazy"`.
2. Every `<img>`/`<video>` has `width`+`height` (or `aspect-ratio`); every
   image below the first viewport has `loading="lazy" decoding="async"`.
   **Lighthouse 13 removed the offscreen-images audit**: grep the markup for
   missing `loading` instead of waiting for a warning.
3. AVIF first with WebP fallback (or WebP only), encoded at build time
   (`astro:assets`, or ffmpeg/sharp in the content-sources scripts). `srcset`
   +`sizes` (Astro `image.layout`) so a phone never downloads the desktop
   hero. Stock photos: ≤ 1600 px wide, ≤ 200 KB (BikeCRM shipped a 4928 px,
   2 MB JPEG and a 5.6 MB pricing hero behind a 65 % black overlay).
4. Illustrations that carry text need a **phone version** (600–720 px wide,
   `<picture>` or `srcset`, narrow crop or larger type): a 1200 px card shown
   at 360 px shrinks its text to ~30 % (20 px becomes 6 px). How to design
   them: content-creation.
5. `content-visibility: auto` with `contain-intrinsic-size` on long
   below-the-fold sections (never without the intrinsic size: CLS).

**Fonts**
6. Self-host WOFF2, subset to what the languages need (latin + latin-ext for
   ca/es/fr), no request to fonts.googleapis.com (also the GDPR/zero-cookies
   angle). On Astro ≥ 6 use the stable **Fonts API**, which self-hosts, preloads
   and generates metric fallbacks.
7. A **metric-matched fallback** (`size-adjust`, `ascent-/descent-/line-gap-
   override` on a local system font) so text keeps its height when the web
   font swaps in. Tune it by comparing block heights with web fonts blocked
   vs loaded at several widths; canvas `measureText` ignores variable-font
   weight and gives wrong ratios. Never regex-replace `size-adjust` globally
   (it also hits `-webkit-text-size-adjust`).
8. Preload at most the 1–2 files the LCP text uses, with `crossorigin`.

**CSS and JS**
9. Astro `build.inlineStylesheets: 'auto'` (default, inlines < 4 KB);
   consider `'always'` when page CSS is small (~20–30 KB compressed, our
   judgement) and measure: inlined CSS is not cached across pages.
10. Zero JS by default. Each island needs a reason and `client:visible` or
    `client:idle`. A whole framework can leave with one island (FichaChat
    dropped React by removing an analytics component; Licita Radar replaced
    a React FAQ with `<details>`). Native `<details>`/`<summary>` for FAQs
    and simple menus.
11. **Anything a JS framework toggles needs its closed state in the static
    HTML** (`class="hidden lg:!block"` + `:class="open && '!block'"`), or it
    renders open and collapses after hydration: BikeCRM's mobile menu did
    exactly that, mobile CLS 0.466 → 0 when fixed.
12. Third parties are the usual TBT/INP cost: analytics is one small, deferred,
    cookieless script (Umami); no tag managers on marketing pages; a CAPTCHA
    (Turnstile/hCaptcha) loads **only on pages with a form** (hCaptcha cost
    ~775–865 KB on every page of BikeCRM and EnaCast). Pin CDN script versions.

**Video**
13. `preload="none"`, a poster with the video's aspect ratio, click to play,
    per-breakpoint cuts as separate elements (see content-creation). The
    poster of a CSS-hidden `<video>` still downloads; the MP4 does not.
14. YouTube/Vimeo only behind a facade (Lighthouse 13 removed the facade
    audit, so nothing warns you).
15. **iPhone/Safari will not play an MP4 served without byte ranges (206).**
    Cloudflare Pages static assets ignore `Range` (200 + whole file): ship a
    Pages Function that serves `/video/*` from `env.ASSETS` with 206/416
    (reference: `~/git/oriolj/public_contract_scanner/comercial-website/functions/video/[[path]].js`).
    Vercel and DigitalOcean answer 206 natively. Check every deploy:
    `curl -s -o /dev/null -D - -H 'Range: bytes=0-99' https://<site>/video/<file>.mp4`
    → `206` + `content-range`.

**Caching, compression, delivery**
16. Hashed assets: `Cache-Control: public, max-age=31536000, immutable`. HTML:
    `max-age=0, must-revalidate` (the edge still serves it from cache).
    - Cloudflare Pages: default is `max-age=0, must-revalidate`; add rules in
      `static|public/_headers` (≤ 100 rules; they do **not** apply to Pages
      Functions responses).
    - Vercel: default `max-age=0, must-revalidate`; precedence
      `Vercel-CDN-Cache-Control` > `CDN-Cache-Control` > `Cache-Control`; with
      an Astro adapter (Build Output API) `vercel.json` headers do not apply
      (verified 2026-09-26; see vercel-deploy).
    - DigitalOcean App Platform (behind its Cloudflare): `max-age=10,
      s-maxage=86400` on everything, not configurable from the repo.
    - Always verify with `curl -sI` after deploying.
17. **Media that changes gets a new file name** (`-v2`): with any edge TTL, a
    re-encode under the same name keeps serving the old file.
18. Compression is the CDN's job (Cloudflare Free now serves zstd, Pro
    Brotli); do not pre-compress by hand.
19. Cloudflare Pages always sends **Early Hints** from `<link rel=preload|
    preconnect>` that carry only `href`, `rel`, `as`: a preload with
    `crossorigin` (fonts) is skipped, so add an explicit `Link:` line in
    `_headers` for it.
20. Prefetch: Astro `prefetch` (hover or viewport) for internal links; use
    Speculation Rules prerender only after measuring and defer the analytics
    pageview until activation. Do not stack Astro prefetch with Cloudflare
    Speed Brain; Speed Brain does not work on `pages.dev` anyway.
21. Preconnect only to origins used in the first 1–2 s, at most 2–3.
22. Keep pages bfcache-eligible: never register `unload` (use `pagehide`),
    `rel=noopener` on new-window links.

**Correctness that looks like performance**
23. A real 404 page: Cloudflare Pages without one answers every unknown URL
    with the home page and 200 (a soft 404 that also makes `/favicon.ico`,
    `/llms.txt` and `/manifest.webmanifest` "exist").
24. Check horizontal overflow at every width from 360 to 1440
    (`scrollWidth > innerWidth`): Licita Radar scored Lighthouse 100 on
    mobile while the page was 680 px wide at 390 px; BikeCRM scrolled
    sideways at 768–990 px for months.
25. Files in the real publicDir: an Astro site with `publicDir: 'static'` and
    a stale `public/` served its manifest as a 404.

## Measuring (see core-web-vitals for the loop)

- **Lighthouse 13** (≥ Node 22.19): scoring unchanged, but most performance
  audits became `*-insight` audits (`lcp-discovery-insight`,
  `image-delivery-insight`, `render-blocking-insight`,
  `document-latency-insight`, `use-cache-insight`, `cls-culprits-insight`,
  `third-parties-insight`, …) and `offscreen-images`, `third-party-facades`,
  `preload-fonts` are gone. Update CI assertions to the new IDs. Full mapping
  in the research reference.
- Median of 3 runs (5 in CI); a single run is noise.
- Field data (CrUX/PSI, 28-day p75) is what Google uses; small sites often have
  none, so ship the `web-vitals` attribution build to our analytics if the
  numbers matter.
- **Local previews:** other sessions use the same machine. Check the port is
  free (`ss -ltnp`) — `astro preview` silently moves to the next port, and an
  agent once measured another site's preview. Stop your own server by PID;
  never `pkill -f <pattern>` (it matched the calling shell and other agents'
  processes the day this skill was written).
- `astro preview` fails with the `@astrojs/vercel` adapter: serve
  `.vercel/output/static` with a static server.
- Local `astro preview` is uncompressed: compare lab numbers live-to-live.

## CI gate (recommended)

Lighthouse CI ≥ 13, 5 runs, median: fail when mobile performance < 90, LCP >
2500 ms, CLS > 0.1, TBT > 200 ms, or a `resource-summary` budget above is
exceeded; assert only on `*-insight` IDs. Plus two shell checks a lab tool
does not do: overflow at 360–1440 px and `Range` → 206 on every video.
