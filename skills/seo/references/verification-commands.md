# Verifying SEO output

Load this when auditing an existing site or verifying a change. Run
these on every page after an SEO change.

## Structural basics (one-liner grep)

```bash
curl -s https://example.com/some-page \
  | grep -E 'rel="canonical"|og:|description|application/ld\+json|<title>' | head
```

Confirms `<title>`, `<meta description>`, canonical, OpenGraph tags,
and at least one JSON-LD block are present.

## robots.txt + sitemap

```bash
curl -s https://example.com/robots.txt
curl -s https://example.com/sitemap.xml | head -30
```

Check: `Sitemap:` directive points at a reachable absolute URL; sitemap
`<loc>` entries all use the canonical host; no `301`/`404` URLs listed.

## llms.txt

```bash
curl -s https://example.com/llms.txt
curl -s https://example.com/llms-full.txt | head -40
```

Check: short file is one screen; full file stays under ~30 KB.

## Pretty-print JSON-LD

```bash
curl -s https://example.com/some-page \
  | grep -oP '(?<=<script type="application/ld\+json"[^>]*>)[^<]+' \
  | python3 -c 'import json,sys; [print(json.dumps(json.loads(l), indent=2, ensure_ascii=False)) for l in sys.stdin if l.strip()]'
```

Verify schema types, canonical `url` field, `datePublished`/`dateModified`
correctness. If `dateModified == datePublished`, drop `dateModified`.

## Multi-tenant / canonical-host check

```bash
# Verify subdomain 301s to custom domain
curl -sI https://subdomain.platform.com/some-page | head -5
# Expect: HTTP/1.1 301, Location: https://customdomain.com/some-page

# Verify the canonical serves 200 on the custom domain
curl -sI https://customdomain.com/some-page | head -5
# Expect: HTTP/1.1 200

# Same path must NOT redirect on the canonical host (would be a loop)
```

## Podcasting 2.0 tags

```bash
curl -s https://example.com/podcasts/program/rss.xml \
  | grep -E 'podcast:guid|podcast:transcript|podcast:chapters' | head

# Transcript endpoints return 404 when empty (not an empty document)
curl -sI https://example.com/podcasts/program/ep-slug/transcript.vtt
```

## Status codes

```bash
# 404 pages MUST return 404
curl -sI https://example.com/this-page-does-not-exist | head -1
# Expect: HTTP/1.1 404

# Trailing-slash policy enforced consistently
curl -sI https://example.com/some-page  # 301 to /some-page/
curl -sI https://example.com/some-page/
```

## Online validators (source of truth)

### Search / structured data
- **Google Rich Results Test** — https://search.google.com/test/rich-results
  (JSON-LD validation + rich-snippet preview)
- **Schema.org Validator** — https://validator.schema.org/
  (pure schema correctness, independent of Google's rich-result rules)
- **Google URL Inspection** (inside Search Console) — live + indexed
  snapshots, renders the page with Googlebot

### Performance / Core Web Vitals
- **Google PageSpeed Insights** — https://pagespeed.web.dev/
  (CrUX field data + Lighthouse lab; mobile is the default surface)
- **Chrome UX Report (CrUX) dashboard** — https://developer.chrome.com/docs/crux
- **WebPageTest** — https://www.webpagetest.org/ (filmstrip, waterfall)

### Social cards
- **Facebook Sharing Debugger** — https://developers.facebook.com/tools/debug/
  (also forces re-fetch of the OG image cache)
- **LinkedIn Post Inspector** — https://www.linkedin.com/post-inspector/
- **Twitter / X Card Validator** — https://cards-dev.twitter.com/validator

### Feeds
- **Podcast Index validator** — https://podcastindex.org/podcast/feed-check
  (RSS 2.0 + Podcasting 2.0 compliance)
- **W3C Feed Validator** — https://validator.w3.org/feed/

### International
- **Merkle Hreflang Tester** — https://technicalseo.com/tools/hreflang/
  (bidirectionality + ISO code validation)

### Ops / index monitoring
- **Google Search Console** — https://search.google.com/search-console
  (coverage, indexing, query analytics, Core Web Vitals report)
- **Bing Webmaster Tools** — https://www.bing.com/webmaster
  (Bing index + Copilot citation exposure + IndexNow submission)
- **IndexNow (one-time POST)** — https://www.indexnow.org/
  (Bing + Yandex real-time URL push; no Google support)

### Competitor / AI surface checks
- Manually run target queries in **ChatGPT** / **Perplexity** /
  **Claude** / **Gemini** (Google AI Overviews) — note which sources
  they cite. No API shortcut; periodic manual spot-checks are the
  current state of the art.

## Live-fix workflow

1. Change a schema / meta tag locally.
2. `curl` the rendered page; grep for the affected tags.
3. Paste the rendered HTML into Google Rich Results Test before shipping.
4. After ship, paste the live URL into the same validators to confirm
   CDN serves the new version.
5. Force-refresh Facebook / LinkedIn / Twitter caches if the OG image
   changed — their caches are sticky and won't re-crawl on their own.
