---
name: pwa
description: Ship and audit Progressive Web Apps — installability, manifest, service worker, offline support, push notifications, update flow. Covers Vite + React (vite-plugin-pwa, Workbox), Next.js (next-pwa / Serwist), Astro, SvelteKit, Remix, plain HTML; cache strategies (CacheFirst / NetworkFirst / StaleWhileRevalidate), scope gating, install prompt UX, iOS Safari quirks, Cloudflare Pages / Vercel / Netlify headers, Lighthouse PWA audit, "Add to Home Screen", offline shell, background sync, Web Push. Use whenever the user asks about PWA, service workers, web app manifest, installable apps, offline-first, "make this app installable", "add offline support", "add to home screen", iOS Safari install, Workbox, vite-plugin-pwa, next-pwa, Serwist, manifest.webmanifest, navigator.serviceWorker, Cache API, runtime caching, app shell, update prompt, skipWaiting, registerSW, beforeinstallprompt, Lighthouse PWA score, maskable icons, theme-color, standalone mode, web push notifications.
---

# PWA playbook

Opinionated, stack-agnostic playbook for shipping installable, offline-capable web apps in 2026. The 80/20 path is `vite-plugin-pwa` (or framework equivalent) + Workbox + a tightly-scoped manifest. Most "PWA is broken" tickets are one of three things: missing manifest fields, wrong cache strategy for the resource, or SW scope mismatch.

## First principles

1. **PWA is opt-in per surface, not per origin.** Most apps have marketing pages and product surfaces. Scope the manifest + SW to the product surface (e.g. `/app`); leave marketing pages stale-tolerant and SW-free. A single SW that intercepts every request is how teams ship caching bugs into landing pages.
2. **Cache strategy is per resource type, not per app.** Hashed bundles want CacheFirst, navigation HTML wants NetworkFirst, public API GETs want StaleWhileRevalidate. Authenticated user data usually wants **no cache** (RLS + per-user response = leak risk).
3. **Installability is gated by the manifest.** Chrome's heuristic requires HTTPS, a registered SW (with at least a `fetch` handler), and a manifest with `name`, `short_name`, `start_url`, `icons` (192 + 512 minimum), `display: standalone`. Miss one field, no install prompt. Lighthouse's "Installable" check is the source of truth — run it.
4. **Updates need user-visible prompts.** Silent SW updates leave users on stale code for hours/days; auto-`skipWaiting` mid-session can corrupt in-flight state. Show a toast: "New version available — Reload". Done right, deploys feel instant.
5. **iOS Safari is the constraint.** No `beforeinstallprompt`, no push without manual user gesture, manifest `display: standalone` works but `start_url` quirks abound. Test on a real iPhone before shipping.

## Baseline every PWA needs

In priority order:

1. **Web app manifest** at `/manifest.webmanifest` (or `/manifest.json`), served with `Content-Type: application/manifest+json`.
2. **Manifest fields** (Chrome install criteria, 2026):
   - `name` (full name, used on first run / splash)
   - `short_name` (home screen label, ≤12 chars)
   - `start_url` — where the installed app launches. **Set this to your product surface, not `/`**, if you scope the PWA.
   - `scope` — the URL prefix the PWA "owns". Install prompt only fires while inside scope; navigations outside scope leave the standalone window.
   - `display: "standalone"` (or `"minimal-ui"` for browser-y chrome)
   - `theme_color` — must match the `<meta name="theme-color">` tag in HTML
   - `background_color` — splash screen color before JS boots
   - `icons` — 192×192 + 512×512 PNG minimum, **plus** at least one `purpose: "maskable"` icon (otherwise Android crops your icon into a circle and chops the edges)
   - `lang`, `orientation` — optional but cheap
3. **Service worker** registered from inside the scope only. Hand-rolling is rarely worth it — use Workbox.
4. **`<link rel="manifest" href="/manifest.webmanifest">`** in HTML head.
5. **`<meta name="theme-color" content="...">`** matching the manifest's `theme_color`.
6. **`<link rel="apple-touch-icon" href="/icons/icon-192.png">`** — iOS ignores the manifest icons and reads this tag.
7. **HTTPS in production.** SWs refuse to register over HTTP except on localhost.

## Scope strategy

The single most underused PWA feature. `scope: "/app"` (or wherever your product surface lives) gives you:

- **Install prompt only fires when the user is inside `/app/*`** — marketing visitors never see it. Better conversion: you're prompting users who've already engaged.
- **Tapping the installed icon launches into `/app`** (via `start_url`), not the marketing home.
- **Standalone window only stays standalone within `/app`** — clicking a link to `/blog` opens in a regular browser tab, which is usually what you want.

But — and this matters — **the SW itself is origin-scoped by default**. A SW at `/sw.js` has scope `/` and will intercept landing-page requests too. Two ways out:

1. **Register the SW conditionally**, only when the user mounts the product route (React: `useEffect` in the `/app` page; Next.js: app-router segment). Landing visitors never trigger registration. Once installed, the SW is still origin-scoped, so configure Workbox routes to ignore non-product paths.
2. **Use Workbox `navigateFallbackAllowlist: [/^\/app/]`** so the cached app shell only serves `/app/*` navigations. Non-`/app` navigations pass through to the network.

Best practice: **do both**. Conditional register prevents fresh visitors from getting a SW at all. The allowlist protects users who installed the PWA and later wander back to `/`.

If you genuinely need the SW scope tighter than `/`, serve it from `/app/sw.js` or set `Service-Worker-Allowed: /app/` on the response header. This is rarely worth the build-tool gymnastics in an SPA.

## Workbox cache strategies — pick per resource

| Resource type | Strategy | Why |
|---|---|---|
| Hashed JS / CSS / fonts (immutable URLs) | **CacheFirst** | URL changes on every deploy; the cached copy is always correct. Long TTL. |
| Navigation HTML (`/app/*`) | **NetworkFirst** with short timeout → fallback to cached app shell | Users get fresh shell when online, working app when offline. |
| Public API GETs (e.g. question bank, product list) | **StaleWhileRevalidate** | Instant from cache, refreshes in background. Tolerates ~1 deploy of staleness. |
| Authenticated API responses (RLS, per-user data) | **No cache** (let through) | A shared cache can leak user A's data to user B if cache keys aren't user-scoped. Skip unless you've audited cache key isolation. |
| Images, OG cards | **CacheFirst** with expiration plugin | Cap entry count (e.g. 60) and max age (30 days). |
| Google Fonts CSS | **StaleWhileRevalidate** | The CSS changes rarely; the font files behind it never do. |
| Google Fonts files (`fonts.gstatic.com`) | **CacheFirst** with 1-year expiration | True immutable assets. |
| HTML for marketing pages | **Pass-through (no SW route)** | Marketing wants fresh content for SEO / experiments. |

Anti-pattern: don't precache user-uploaded assets, OG images, or anything you can't bound in size. Workbox precache is meant for the deterministic build manifest (hashed bundles + a couple of static assets).

## Update flow — show the prompt

Auto-reload during a quiz is hostile. Use vite-plugin-pwa's `registerType: "prompt"` and surface a toast:

```ts
// usePwaRegister.ts — register only inside the product surface
import { useEffect } from "react";
import { toast } from "sonner";

export function usePwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    let cancelled = false;
    import("virtual:pwa-register").then(({ registerSW }) => {
      if (cancelled) return;
      const updateSW = registerSW({
        onNeedRefresh() {
          toast("New version available", {
            action: { label: "Reload", onClick: () => updateSW(true) },
            duration: Infinity,
          });
        },
        onOfflineReady() {
          toast.success("App is ready to work offline");
        },
      });
    }).catch(() => {/* dev mode, no SW */});
    return () => { cancelled = true; };
  }, []);
}
```

Then call `usePwaRegister()` at the top of your product surface's root component. Don't call it in `main.tsx` / `App.tsx` — that would register on every page.

## vite-plugin-pwa — canonical Vite + React config

```ts
// vite.config.ts
import { VitePWA } from "vite-plugin-pwa";

VitePWA({
  registerType: "prompt",
  injectRegister: false, // we register manually from inside /app
  strategies: "generateSW",
  manifest: {
    name: "...",
    short_name: "...",
    description: "...",
    lang: "es",            // match your <html lang>
    start_url: "/app",
    scope: "/app",
    display: "standalone",
    orientation: "portrait",
    background_color: "#ffffff",
    theme_color: "#2257c3",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
  workbox: {
    navigateFallback: "/index.html",
    navigateFallbackAllowlist: [/^\/app/],
    globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
    globIgnores: ["**/data/preguntas_*.json", "og-image.png"],
    cleanupOutdatedCaches: true,
    runtimeCaching: [
      {
        urlPattern: ({ url }) => url.pathname === "/api/questions",
        handler: "StaleWhileRevalidate",
        options: {
          cacheName: "questions",
          expiration: { maxEntries: 4, maxAgeSeconds: 86400 },
        },
      },
      {
        urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
        handler: "CacheFirst",
        options: {
          cacheName: "google-fonts",
          expiration: { maxEntries: 30, maxAgeSeconds: 31536000 },
        },
      },
    ],
  },
  devOptions: { enabled: false }, // SW off in dev — interferes with HMR
});
```

Add to `vite-env.d.ts`:

```ts
/// <reference types="vite-plugin-pwa/client" />
```

## Icon generation — ImageMagick one-liner

From a single 512×512 source PNG with transparency:

```sh
magick favicon.png -resize 192x192 public/icons/icon-192.png
magick favicon.png -resize 512x512 public/icons/icon-512.png
# Maskable: inset the logo, fill the safe zone with theme color
magick favicon.png -resize 410x410 -background "#2257c3" -gravity center -extent 512x512 public/icons/icon-maskable-512.png
```

The maskable variant matters: Android's adaptive-icon mask crops to a circle/squircle and lops off the outer ~20% of your icon if you ship a non-maskable PNG. Test with [maskable.app](https://maskable.app/editor).

## Framework cheat sheet

| Framework | Plugin | Notes |
|---|---|---|
| Vite + React/Vue/Svelte/etc. | `vite-plugin-pwa` | Recommended default. Workbox 7 under the hood. |
| Next.js (App Router) | `@serwist/next` (formerly `next-pwa`, now unmaintained) | Serwist is Workbox-compatible and actively maintained. |
| Astro | `@vite-pwa/astro` | Same plugin under a different name. |
| SvelteKit | `@vite-pwa/sveltekit` | Same. |
| Remix | `@remix-pwa/sw` or roll your own — Remix doesn't have a blessed solution | |
| Plain HTML / no bundler | Hand-rolled SW + manifest | Use Workbox via CDN; precache list maintained manually. |

## Hosting gotchas

### Cloudflare Pages

- `_headers` file controls cache. Make sure SW + manifest don't get long `Cache-Control` (the manifest is `application/manifest+json`, served fresh by default). Add explicit `Cache-Control: public, max-age=0, must-revalidate` for `manifest.webmanifest` and `sw.js` if your default rule is aggressive.
- `Service-Worker-Allowed` header is settable via `_headers` if you need wider scope than the SW's path:
  ```
  /sw.js
    Service-Worker-Allowed: /
  ```
- `_redirects` SPA fallback works fine with PWA — the SW's `navigateFallback` takes over for in-scope navigations.

### Vercel

- Edge cache treats `sw.js` like any other static asset; add `Cache-Control: public, max-age=0, must-revalidate` in `vercel.json` to ensure new SW gets picked up on next visit.
- For Next.js, prefer Serwist over rolling your own — interaction with the build's hashed chunks is annoying to do by hand.

### Netlify

- Same `_headers` mechanism as Cloudflare Pages. Add `Service-Worker-Allowed` there.

### Static origin (S3 + CloudFront, etc.)

- Set `Cache-Control: no-cache` on `sw.js` at the bucket / distribution level. SWs cached for hours = users stuck on old code for hours.

## iOS Safari quirks (2026)

- **No `beforeinstallprompt`.** Users install via Share → "Add to Home Screen". You can't programmatically trigger it. Show a one-time hint banner with an arrow toward the share icon on iOS.
- **Manifest support is partial.** Safari reads `name`, `short_name`, `icons` (and prefers `apple-touch-icon` if present), `display: standalone`. It ignores `theme_color` (use `<meta name="theme-color">` with `media="(prefers-color-scheme: ...)"` variants) and `background_color`.
- **`start_url` quirks.** Safari sometimes treats `start_url` as the bookmarked URL rather than re-launching at it. Test on real hardware.
- **Splash screen** requires `apple-touch-startup-image` link tags per device resolution. Annoying but a polish-stage concern.
- **No Web Push** until iOS 16.4+, and only for installed (home-screen) PWAs. Not for browser tabs.
- **Storage limits**: ~50 MB before prompting the user, evictable under pressure. Don't precache 100 MB of question images.

## Verification

Run all of these before claiming "PWA works":

1. **Build emits expected files.** After `vite build` (or framework equivalent), confirm `dist/` contains `manifest.webmanifest`, `sw.js`, and the icon files. The plugin's build log should print `precache N entries (X KiB)`.
2. **Manifest serves with correct Content-Type.**
   ```sh
   curl -sI https://example.com/manifest.webmanifest | grep -i content-type
   # → content-type: application/manifest+json
   ```
3. **SW serves with `text/javascript`** and the right scope. `curl -sI https://example.com/sw.js`.
4. **Chrome DevTools → Application tab:**
   - Manifest: all fields green, no "Installability" warnings, icons render.
   - Service Workers: registered, "running", scope shown.
   - Storage: precache entries listed under Cache Storage.
5. **Lighthouse PWA audit** (Chrome DevTools → Lighthouse → mobile + PWA category). Aim for green on Installability + PWA Optimized.
6. **Offline test:** DevTools → Network → Offline checkbox → reload `/app`. Should load from cache. Reload `/` (out of scope) → should fail (browser offline page), confirming scope works.
7. **Update flow test:**
   - Deploy v1, install PWA, leave the tab open.
   - Deploy v2.
   - Refocus or revisit `/app` in the installed PWA. The "New version available" toast should appear.
   - Tap Reload → new version active.
8. **iOS install:** open in Safari on a real iPhone → Share → Add to Home Screen → launch from home screen → confirm standalone mode (no Safari URL bar).

## Common pitfalls

- **Manifest 404.** Often a base-path issue when the app is served from a sub-path. Check the `<link rel="manifest" href="...">` URL resolves correctly.
- **"Install" button never appears.** Run Lighthouse — it tells you exactly which manifest field is missing or which install criterion fails. Common offenders: no maskable icon (warning, not blocker), missing `short_name`, `start_url` not in scope, no SW with a `fetch` handler.
- **SW stuck on old version forever.** Edge cache or CDN is caching `sw.js`. Set `Cache-Control: no-cache` on the SW. Also: skip-waiting prompts give users control instead of waiting for all tabs to close.
- **HMR broken in dev.** SW is intercepting in dev mode. Set `devOptions.enabled: false` in vite-plugin-pwa.
- **Marketing pages caching wrong.** SW scope is wider than intended — add `navigateFallbackAllowlist` and conditional registration.
- **User data leaks across accounts.** A shared runtime cache served a previous user's API response to the next user. Either don't cache authenticated endpoints, or include the user ID in the cache key (`cacheKeyWillBeUsed` plugin).
- **Icons look cropped on Android.** No `purpose: "maskable"` icon. Add one with a wide safe zone.
- **Quota errors on iOS.** Precache too large. Trim `globPatterns`, move heavy assets to runtime cache with strict expiration.
- **`Add to Home Screen` works but app boots to the wrong route.** `start_url` is wrong. Use an absolute path (`/app`), not a relative one.
- **Push notifications silent on iOS.** App must be installed to home screen and on iOS 16.4+. Browser tabs don't get push on iOS.

## Anti-patterns

- **Precaching the whole product**, including user-uploaded images and AI-generated content. Precache is for the deterministic build manifest. Use runtime cache for everything else.
- **Auto-reloading on update.** Hostile mid-session. Always prompt.
- **One PWA for marketing + product.** Two surfaces, two cache strategies. Scope to the product.
- **Caching authenticated API responses with no per-user key.** Recipe for cross-user data leaks. Audit before enabling.
- **Hand-rolling a service worker because "Workbox is overkill".** Workbox handles precache versioning, cache cleanup on activation, and bulk routing. You'll reimplement these badly. Use Workbox.
- **Forgetting `cleanupOutdatedCaches: true`.** Old cache entries linger and eat quota. Always set this.

## Quick verification one-liners

```sh
# Manifest reachable + correct content-type
curl -sI https://example.com/manifest.webmanifest | grep -i content-type

# SW reachable
curl -sI https://example.com/sw.js | head -5

# Manifest contents
curl -s https://example.com/manifest.webmanifest | jq .

# Find PWA setup in a repo
grep -rn "VitePWA\|registerSW\|virtual:pwa-register\|manifest.webmanifest" --include="*.{ts,tsx,js,jsx,html}"
```

## Launch resilience — the blank-screen class (audit any installed PWA for these)

An installed PWA can launch to a **permanent blank screen**: the cached shell (`index.html`) loads but its hashed JS is momentarily unavailable — Cache Storage eviction (common on Android under storage pressure), a stale chunk name right after a deploy, or a network blip at cold launch. React/Vue never mounts, no error boundary can help (the bundle never ran). Audit checklist, in order of impact:

1. **Bootstrap watchdog in `index.html`** — a dependency-free inline script, **placed FIRST in `<head>` before any stylesheet `<link>`** (a pending/stalled stylesheet blocks every following script, inline ones included — a watchdog placed after a hung font CDN `<link>` never arms). It should:
   - listen (capture phase) for `error` on same-origin `<script>`/`<link rel=stylesheet>`, plus `vite:preloadError` and chunk-load `unhandledrejection`s;
   - on failure: **bust Cache Storage + unregister the SW, then reload once** (a plain reload re-reads the poisoned cache — the bust is essential); a `sessionStorage` counter caps auto-attempts at 1, then it renders a branded "Couldn't finish loading / Reload" card instead of blank;
   - a ~12–20s "never mounted" timeout as safety net (plain reload if no asset error was seen — don't nuke a warm cache for mere slowness);
   - the app calls a `window.__bootReady()` to cancel the watchdog and reset the counter after first render;
   - **defer the fallback card to `DOMContentLoaded` if `document.body` doesn't exist yet** — asset errors can fire during head parsing, and an early-returning fallback that already set its "handling" flag = permanent blank;
   - don't couple asset detection to the bundler's `assetsDir` — match same-origin script/stylesheet instead.
2. **No render-blocking third-party stylesheets** (Google Fonts is the classic). Best: **self-host fonts as woff2** so the SW precaches them and offline launches render brand fonts. Second best: `rel=preload as=style` + `media="print" onload="this.media='all'"` + `<noscript>` fallback.
3. **Shell freshness**: precached `index.html` is served cache-first **forever** — that's how shells go stale. Exclude it from `globPatterns`, set `navigateFallback: null` (the plugin default binds to the precache and **throws** if it's not precached), and add a `NetworkFirst` runtime route for same-origin `request.mode === 'navigate'` with `networkTimeoutSeconds: 3` — fresh online, cached on flaky/offline.
4. **Chunk-split to shrink deploy invalidation** via `manualChunks`: one base **`vendor`** chunk (react/framework + ALL misc deps) plus leaf chunks (charts, editors). **Topology rule: never split react/the framework away from misc node_modules** — circular chunk imports give `undefined (reading 'forwardRef')` at startup. Keep dynamic-imported heavies (heic2any etc.) out of vendor. Result: app deploys only invalidate the small app chunk → smaller SW updates → smaller blank-screen window. **Always boot the production build headless after changing chunking** — this failure mode is runtime-only.
5. **Capacitor/native: disable the SW entirely** (`injectRegister: false` + register manually web-only, unregister on native). The APK bundles its own assets; a SW just serves stale JS across app updates — users keep running the old build no matter how many updates they install.
6. **Repro/verify**: serve the prod `dist/` and use Playwright request-interception to abort the entry chunk (models the missing-bundle state). Headless Chromium won't populate the Workbox precache, so "evict a precached chunk" is not a reliable repro — interception is.

## Useful references

- [vite-plugin-pwa docs](https://vite-pwa-org.netlify.app/) — opinionated defaults, examples per framework.
- [web.dev — Web App Manifest](https://web.dev/learn/pwa/web-app-manifest)
- [MDN — Making PWAs installable](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)
- [Workbox modules](https://developer.chrome.com/docs/workbox/modules/workbox-strategies) — strategy reference.
- [maskable.app](https://maskable.app/editor) — preview your icon against Android masks.
- [Lighthouse PWA audit](https://developer.chrome.com/docs/lighthouse/pwa/) — the audit, what each check means.
