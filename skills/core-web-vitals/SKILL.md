---
name: core-web-vitals
description: Measure and fix Core Web Vitals (LCP, CLS, INP/TBT) on any web project. Use when the user asks to "check core web vitals", "run lighthouse", "why is LCP slow", "fix CLS / layout shift", "page speed audit", "performance score", or after shipping layout/image-heavy changes that could regress vitals. Covers headless Lighthouse CLI, CrUX field data, reading the report JSON, and per-metric fix playbooks with verified gotchas.
---

# Core Web Vitals: measure → diagnose → fix → re-measure

Always work this loop end to end: measure first (never guess), fix the single
biggest verified cause, deploy, re-measure. Report lab vs field honestly.

## 1. Measure

**Target production, not dev.** Dev servers are unminified, uncached, and
SSR-slow by design — their numbers are meaningless. If only dev exists, say so
and caveat everything.

### Lighthouse CLI (headless — works without an X server)

```bash
# Desktop
npx --yes lighthouse https://example.com/ --quiet \
  --chrome-flags="--headless --no-sandbox" --only-categories=performance \
  --output=json --output-path=/tmp/lh-desktop.json --preset=desktop

# Mobile (throttled — the harder, canonical test)
npx --yes lighthouse https://example.com/ --quiet \
  --chrome-flags="--headless --no-sandbox" --only-categories=performance \
  --output=json --output-path=/tmp/lh-mobile.json \
  --form-factor=mobile --screenEmulation.mobile
```

Note: MCP browser tools (chrome-devtools `lighthouse_audit` / trace tools) need
a display server and often fail headless ("Missing X server"); the CLI above is
the reliable path.

### Read the JSON (the useful audits)

```python
d = json.load(open('/tmp/lh-mobile.json')); a = d['audits']
d['categories']['performance']['score']            # 0..1
a['largest-contentful-paint']['displayValue']      # + FCP, CLS, TBT, speed-index
a['lcp-breakdown-insight']                         # TTFB / load delay / load / render delay + LCP element selector
a['lcp-discovery-insight']                         # checklist: fetchpriority applied? discoverable? not lazy?
a['layout-shifts']['details']['items']             # CLS culprits with selectors + per-shift score
a['network-requests']['details']['items']          # sort by transferSize to find heavy resources
```

Audit names drift between Lighthouse versions (`largest-contentful-paint-element`
vs `lcp-breakdown-insight`...). If a key is missing, list candidates:
`[k for k in a if 'lcp' in k]`.

### Field data (what Google actually ranks on)

```bash
curl -s "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=<URL-ENCODED>&category=performance&strategy=mobile"
# → .loadingExperience.metrics = CrUX p75 per metric; empty = origin below CrUX traffic threshold
```

Keyless works for occasional calls. Small sites usually have **no field data** —
then lab is all you have; say so explicitly.

### Quick in-browser spot checks (Playwright/DevTools MCP)

Buffered PerformanceObservers work after load:
`largest-contentful-paint`, `layout-shift` (sum entries without
`hadRecentInput`), `paint` entries, navigation entry `responseStart` for TTFB.
Useful to attribute CLS to specific elements interactively.

## 2. Things to have in mind

- **Thresholds (field p75):** LCP ≤ 2.5 s · CLS ≤ 0.1 · INP ≤ 200 ms.
  Lighthouse lab has no INP; TBT is the proxy.
- **Lab numbers are SIMULATED.** Lighthouse Lantern models ~1.6 Mbps / 150 ms
  RTT mobile. Crucial consequence: `lcp-breakdown-insight` subparts come from
  the real (unthrottled) trace, while the headline metric is simulated — if the
  subparts total ~300 ms but the metric says 2.7 s, the image is FINE and the
  bottleneck is the critical render chain (LCP can never beat FCP). Don't keep
  optimizing the image; either accept it or attack FCP.
- **One fix at a time, re-measure after deploy.** Verify the deploy actually
  landed before re-running (poll the prod HTML for a marker your change
  introduced — e.g. `grep -c 'fetchpriority="high"'`), not just "waited a bit".
- **Stale service workers lie.** On PWA sites the browser may serve a pre-fix
  bundle; unregister SWs + clear caches before in-browser verification.
- Run Lighthouse 2-3× if a result looks off — variance of ±5 points / ±0.2 s
  is normal.

## 3. Fix playbooks

### LCP

1. **Identify the element** (`lcp-breakdown-insight` node selector). Usually a
   hero image or heading.
2. **Hero image lazy-loaded?** The #1 finding in practice: a generic card
   component hard-codes `loading="lazy"` on every image, including the
   first/hero card. Fix by threading an `eager`/`priority` prop from the layout
   to **exactly the first instance**: `loading="eager"` +
   `fetchpriority="high"`. Then verify the served HTML has **exactly one**
   eager image (`grep -o 'fetchpriority="high"' | wc -l`) — eager-loading many
   images makes things worse.
3. **Bandwidth competitors.** Sort `network-requests` by `transferSize`. Big
   images that aren't the LCP element still steal simulated bandwidth even
   below the fold (they're eager by default). Classic source: **CMS/editor
   authored HTML** with raw `<img>` tags — no `loading` attribute, original
   camera-size files, bypassing the image CDN. Fix at the render layer with a
   server-side HTML post-process: rewrite img srcs through the project's image
   CDN with a width/quality transform, and inject
   `loading="lazy" decoding="async"` when absent. (One such image: 495 KB → 128 KB.)
4. **Confirm with the checklist**: `lcp-discovery-insight` should show
   priorityHinted ✓ / requestDiscoverable ✓ / not lazy ✓.
5. Remaining levers in order: TTFB (edge/CDN cache), preload the LCP image only
   if discovery delay is large (pointless when already discoverable + hinted),
   shrink the render-blocking CSS/JS chain, cut third-party scripts in the load
   window (multiple analytics scripts is a common silent cost).

### CLS

1. `layout-shifts` audit lists culprits with per-shift scores — fix the top one
   first, ignore the noise.
2. Images/embeds need reserved space: `width`/`height` attributes or CSS
   `aspect-ratio` / `min-height`. Lazy content growing later is the classic cause.
3. **Absolutely-positioned elements moving counts as CLS** if they're in the
   viewport. JS layout correctors (masonry, etc.) are fine if the SSR first
   paint is close to final — a one-time small nudge costs ~0.04; a full reflow
   costs 0.3+. Invest in good server-side estimates.
4. Fonts: `font-display: swap` reflows text; preload the main webfont or accept
   the small shift. Late-injected banners/players: reserve their slot.

### INP / TBT

1. Less JS on the critical path: lazy-load (`await import()`) anything not
   needed for first paint — a layout library, a player, a palette. Check what a
   static import drags in: library dist bundles are often CommonJS-wrapped and
   **un-tree-shakeable** (the whole lib ships for one function), while app code
   tree-shakes fine.
2. rAF-coalesce observers/handlers; cache `matchMedia` results; avoid
   `getComputedStyle` per tick (a zero-size `getBoundingClientRect` already
   tells you `display:none`).
3. Long tasks at startup: split hydration, use idle/visible client directives
   (`client:visible` etc. in Astro).

## 4. Gotchas learned in the field

- `--preset=desktop` exists, but mobile needs the pair
  `--form-factor=mobile --screenEmulation.mobile` — a bare `--preset=mobile`
  doesn't exist.
- `npx --yes lighthouse` avoids the install prompt in non-interactive shells.
- A 99-desktop / 96-mobile page can still have a real UX bug (e.g. overlapping
  layout) — vitals are not a layout correctness check; screenshot too.
- CDN image transforms: verify the rewritten URL actually returns 200 and is
  smaller (`curl -s -o /dev/null -w "%{http_code} %{size_download}"`), special
  characters (parentheses, spaces) in filenames survive some CDNs but not others.
- When grepping served HTML for verification, count occurrences with
  `grep -o ... | wc -l`, not `grep -c` (which counts lines — many tags share a line).
- If the site auto-deploys on push (Vercel etc.), poll prod for the change
  marker in a loop with `sleep 20` between tries before re-measuring; a
  fixed sleep either wastes time or measures the old deploy.
