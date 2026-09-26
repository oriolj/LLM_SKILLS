---
name: commercial-websites
description: Build, review and fix the commercial (marketing / landing) website of any of our products — the checklist of what a product site must answer and show, how to review one (design critique plus measured evidence), the traps we have hit (SVG mockups rendering in Times, brand-orange contrast, a stale public/ folder, captcha scripts on every page, one-language assets), how to produce its assets with the content-creation skill, how to split the fix across parallel agents without collisions, how to keep every product claim verified against production, and how to ship and verify it. Use when the user says "review the homepage / landing / web comercial", "what would you improve on our site", "fix the landing", "make the marketing site convert", "add a pricing teaser / FAQ / features section", "the site looks old", "prepare the site for launch", or works on any product's public site (BikeCRM, Panotxa, Rutakas, Licita Radar, Humans2Agents, GoalTracker, SpineGuard, BudgetBuddy, oriolj.com, EnaCast sites…). Pairs with seo, core-web-vitals, content-creation, catalan-writing, zero-cookies, eu-law and impeccable.
---

# Commercial websites

A product's public site has one job: a stranger understands what the product
is, who it is for, what it replaces, what it costs, and starts a trial or
contacts us. This skill is the house method for building, reviewing and fixing
those sites across every product, and the index into the skills that own the
details:

| Topic | Owning skill |
|---|---|
| Design critique, polish, typography, layout | **impeccable** (`critique`, `audit`, `polish`, …) |
| Video, posters, product stills, share copy | **content-creation** (makes them with `/brag-slim`) |
| Titles, canonical, hreflang, JSON-LD, AI crawlers | **seo** (load it for every site review) |
| Build-time performance: budgets, images, fonts, JS, video, cache headers per host, CI gate | **static-site-performance** (load it for every site review) |
| LCP / CLS / INP measurement and fixes | **core-web-vitals** |
| Catalan / Spanish / French copy that does not sound translated | **catalan-writing** |
| No cookie banner: engineering the site cookie-free | **zero-cookies**, legal pages **eu-law** |
| Analytics | **umami** (one shared instance for every site), **plausible** |
| Uptime and smoke checks after launch | **gatus**, **talaia** |
| Hosting | house rule: static Astro → Cloudflare Pages; Next.js → Vercel (**vercel-deploy**, **cloudflare-deploy**) |

## PRODUCT.md and DESIGN.md: every commercial site keeps both, current

Every commercial site repo has, at its root (Oriol, 2026-09-26):

- **`PRODUCT.md`** — who the site is for, what the product does, brand
  personality and tone, anti-references, design principles, accessibility
  bar, and the `## Register` (brand). The standing preferences go here
  (concept illustrations over screenshots, the market's language first, VAT
  rule for prices), marked as confirmed by Oriol; anything inferred is marked
  pending until he confirms it.
- **`DESIGN.md`** — colour tokens with their contrast ratios, type scale,
  components, page patterns (section order, CTA system), imagery rules and
  file locations, invariants.

Why the root and those exact names: the impeccable skill's context loader only
finds `PRODUCT.md` / `DESIGN.md` (root, then `.agents/context/`, then `docs/`).
BikeCRM's design system sat in `docs/design-system.md`, so the 2026-09-26
critique ran with no product context at all.

**Update them in the same change** that alters the audience, offer, copy
strategy, colours, components, section order or imagery: a site change is not
done until both files describe what is now live. On a site that has neither,
create them at the start of the work (draft `PRODUCT.md` from the repo and
the user's stated preferences, mark inferred parts as pending, and ask for
confirmation). Link both from the repo's `CLAUDE.md`.

`PRODUCT.md` also holds the **claims tables**: "verified" (each product
claim with where it was checked: code, config, pricing data, a measured
number) and "do not claim" (features not in production, unmeasured figures,
billing terms that do not exist). Copy, FAQ answers, structured data and
video text only use the verified table.

The same repo also keeps the **sources of its generated assets** (video
scenes, illustration HTML, render scripts) in a build-excluded
`content-sources/` folder; masters and intermediates are never committed,
the small web encodes may be (see content-creation for the policy).

## What every product site must have

Go through this list on every review; each line comes from a real miss.

**Message**
- **Every product claim is checked against production** code, config or
  data before it goes on the page, and an honest status line ("en beta",
  "próximamente", no number at all) beats aspirational copy. The 2026-09-26
  review of nine sites found false claims on almost every one: features not
  in production, unmeasured numbers, "free trial" and billing wording on
  products with no billing.
- One `<h1>`: what it is + who it is for, in the customer's words ("El software
  para tu taller de bicis"). The `<title>` is the category search phrase plus
  the brand ("Software para talleres de bicicletas y patinetes | BikeCRM"), not
  the brand alone.
- A hero subtitle with a concrete benefit, not an unprovable superlative ("único
  software del mercado" convinces nobody who is comparing).
- The whole product, not a third of it: if the structured data or the pricing
  page lists capabilities (POS, invoicing, integrations), the page shows them.
  A buyer comparing against a generic tool must see what we replace.
- The buyer's pre-trial questions answered on the page: price anchor, trial
  terms, compliance (VeriFactu in Spain), setup/import help, devices, support.
  A short FAQ with native `<details>` does it. Every answer verified in code,
  docs or pricing data; skip a question rather than invent an answer.
- **B2B prices are quoted excluding VAT** with "+ IVA / + VAT" beside the
  figure; consumer prices include it (house rule).
- **Pricing display (Oriol, 2026-09-26): by default show the monthly price of
  YEARLY billing**, as competitors do ("54,40 € al mes + IVA, con pago anual"),
  with the yearly total next to it and a switch to monthly billing. Teasers
  elsewhere ("desde X €") lead with that figure too. Render both states in the
  HTML so crawlers and no-JS readers see prices. The switch needs no JS: two
  radio inputs, and both price states stacked in one grid cell
  (`grid-area: 1/1`) shown with `:has(#yearly:checked)` + `visibility`, so
  the cell is always as tall as the taller state and switching never shifts
  (Panotxa `BillingPrice.astro`). Format with `Intl.NumberFormat` per locale
  ("54,40 €", never "54.4"), and keep the structured data at the monthly
  billing price with `valueAddedTaxIncluded: false` for B2B.
- Example numbers labelled as examples ("Datos de ejemplo"), or they read as
  claims.
- No heading repeated in consecutive sections (a video poster caption counts),
  and no eyebrow label that just restates its heading.

**Calls to action**
- One primary action, one label, one colour, everywhere: header, hero, after
  the moment of highest intent (right after the video), footer. Two labels
  ("Pruébalo gratis" / "Empieza ahora") in two colours read as two different
  actions.
- A trust line under it with the real terms ("30 días gratis · Sin tarjeta ·
  Sin compromiso"), taken from the product's own copy.
- Lead capture goes to the product's real signup (with the estate anti-bot kit:
  Tor block, enforced Turnstile, signed challenge, honeypot, caps, POST-confirm;
  see the global rules), not to a second footer form with its own captcha.

**Imagery**
- **Concept illustrations, not screenshots** (Oriol, 2026-09-26: "I don't like
  screenshots too much"). Each product image is a composed scene that shows
  what the software is about: a few app cards (the real top bar, status chips,
  labels and brand colours) arranged on a soft panel around one idea: the
  workshop at a glance, one repair in progress, a client's history, the
  "your bike is ready" message. Same visual language as the launch video. Raw
  screenshots are dense, tiny on phones and date quickly; use them only as the
  reference for what the cards look like. How to build them: content-creation
  skill, "Concept illustrations".
- **Phone variants for illustrations with text** (600–720 px wide, via
  `<picture>` or `srcset`), one alt true for both; a 1200 px card at 360 px
  shows its text at ~30 %. Details: content-creation.
- Current, not stale: a 2020 mockup next to a 2026 video says "abandoned".
  The illustration's cards follow today's app (labels from the i18n catalog).
- **SVG loaded through `<img>` cannot use the page's web fonts**: its
  `font-family="Roboto"` falls back to Times on every visitor without the font
  installed (most Windows and macOS machines). Screenshots must be raster (WebP)
  or have text converted to paths. Also check SVGs that merely wrap a base64 PNG
  (855 KB on BikeCRM). Ship illustrations as raster (transparent WebP rendered
  from HTML at 2x), so text always renders in the brand fonts.
- Any data inside an image is invented (names like "Marta Puig", `@example.com`,
  `+34600000xxx`), never production. If you do capture the running app for
  reference, use a local stack with a seeded fake business, and remember **the
  local environment can hold real messaging credentials** (BikeCRM's has live
  WhatsApp Cloud keys): capture confirmation dialogs, never confirm them.
- Alt text describes the scene the image shows, checked against the final
  image (an alt written before the image exists is a guess: BikeCRM's promised
  "the message on the client's phone" while the image showed a dialog).
- Every `<img>` has `width`/`height`, `alt` in the page's language describing
  what it shows; the LCP image `fetchpriority="high"`; the rest `loading="lazy"
  decoding="async"`. Stock backgrounds resized (≤1600 px WebP, <200 KB; a
  4928 px, 2 MB JPEG was loading on every visit).
- Social preview: a real 1200×630 `og:image` with width/height/alt, not a
  600×150 logo under `summary_large_image`.
- Language-specific assets (a video with Spanish text, illustrations with Spanish labels) go
  only on that language's pages, through an optional field in the per-language
  content data, never a hardcoded block.

**Accessibility**
- One `<h1>`, no skipped heading levels (subtitles are `<p>` styled large, not
  `<h4>`/`<h5>`), a `<main>` landmark.
- **Brand-colour contrast:** a saturated orange like `#ff5722` gives 3.0:1 with
  white text and 3.16:1 as text on white — both fail AA (4.5:1). Keep the hue,
  add a deeper shade token for button backgrounds and orange text, and keep the
  bright brand colour for non-text accents and for orange on dark backgrounds.
  **Compute the ratio, do not pick the shade by eye:** Material's `#d84315`
  looks deep enough and still fails (4.44:1 with white, 4.21:1 with `#f8f9fa`);
  BikeCRM uses `#c73d11` (5.12:1 / 4.85:1). Check muted greys on tinted
  panels too (`#6c757d` on `#f8f9fa` is 4.45:1).
- Controls are real `<button>`s (a language switcher built on a `<span>` with a
  click handler is unreachable by keyboard), `aria-label`s come from the i18n
  catalog, tap targets ≥ 44 px. **Measure dropdown items with the menu open**:
  daisyUI items measure ~42 px while closed (`scale(.95)`). daisyUI's default
  `menu-title` colour fails contrast; override it.

**Responsive**
- Check horizontal overflow at every width from 360 to 1440
  (`document.scrollingElement.scrollWidth > innerWidth`), not just phone and
  desktop: BikeCRM's header expanded its full nav at 768 px but only fit from
  992 px, so the live site scrolled sideways on every tablet for months.
  Collapse the nav until the width where it really fits.
- Headings: fluid sizes with `clamp()` (the desktop size as the max) so a 45 px
  h2 does not break into four lines on a phone.

**Performance and plumbing**
- Measure mobile CLS, not only LCP: a hero that reflows as fonts and images load
  scored 0.435 on BikeCRM while desktop was 0.008. Two fixes together: image
  `width`/`height`, and a metric-matched fallback `@font-face` (a local system
  font with `size-adjust` tuned per weight, listed right after the web font) so
  the text block has the same height before and after the web font arrives.
  Verify by measuring block heights with the web fonts blocked.
- **Find the element that shifts before fixing CLS** (Lighthouse `layout-shifts`
  names it). On BikeCRM the font fallback was a real but minor cause; the 0.466
  came from the mobile menu, which had no hidden state until Alpine
  initialised: it rendered open, then collapsed and pulled the hero up. Any
  element toggled by a JS framework (`x-show`, `:class`, `v-if` after
  hydration) needs its closed state in the static HTML (`class="hidden
  lg:!block"` + `:class="open && '!block'"`). Fixed: 0.466 → 0.04.
- Third-party scripts only where used: hCaptcha (~865 KB) was loading on every
  page for one footer form. Pin CDN script versions (`alpinejs@3.x.x` is a
  range). Load only the font families the site uses.
- **Booking embeds load on the first click, not on page load.** A Cal.com
  embed on load sets the `__cf_bm` cookie and dropped Lighthouse Best
  Practices to ~78: make the button a real cal.com link (the no-JS
  fallback) and load the embed script on first click, then open
  `Cal('modal', …)`. Removing one JS analytics island dropped React from
  FichaChat entirely: audit which islands pull a whole framework.
- **Trailing-slash URLs everywhere.** Cloudflare Pages 308-redirects
  `/pricing` to `/pricing/`; canonicals, hreflang and internal links must
  carry the slash (the path helper, e.g. `localizePath`, adds it) or every
  canonical points at a redirect. Details: cloudflare-deploy 1c.
- `llms.txt` entries must be markdown links (`- [Pricing](https://…/pricing/): …`),
  or Lighthouse's llms-txt audit fails.
- **Gate unreleased features on a build env var** (newsletter pages exist
  only when `PUBLIC_NEWSLETTER_TURNSTILE_SITE_KEY` is set) rather than
  holding back a shared push: parallel sessions share one site repo, and a
  gated feature can ride along safely.
- **Know the real public directory.** An Astro site with `publicDir: 'static'`
  plus a leftover `public/` folder serves nothing from `public/`: the web
  manifest 404ed for months. Check `astro.config.*` before adding any file.
- Cache headers are a host setting: `max-age=10` on every asset is the host
  default, fix it in the host or CDN configuration (Cloudflare Pages:
  `static/_headers`, `/_astro/*` immutable), not in the HTML. **While a CDN
  holds assets for hours (`s-maxage=86400`), a re-encoded video or image under
  the same file name keeps serving the old one:** give replaced media a new name
  (`-v2`, `-v3`).
- Nested landmarks: a page component that brings its own `<main>` inside a
  layout that now wraps the slot in `<main>` produces two; grep the pages when
  adding the landmark.

**Legal pages (privacy, legal notice, cookies)** (Oriol, 2026-09-26)
- **Plain language, every site language, verified facts.** The reference is
  Enantena's privacy policy (`~/git/Enantena/enantena-comercial-website/src/i18n/legal.ts`,
  live at enantena.com/privacitat/): short sections titled as the reader's
  questions (who is responsible · what data and why · cookies · how long ·
  who can see it · your rights), one short paragraph per purpose with its
  legal basis in words plus the GDPR article, the real providers by name with
  the transfer mechanism, "this website sets no cookies" when a browser check
  confirms it, rights with the supervisory authority (AEPD), a "last updated"
  date. Structured per-language data rendered by one component, never a
  pasted template.
- **Never ship a generator template** (TermsFeed & co.): BikeCRM's was a 54 KB
  English-only text on every language, with CCPA sections and Google Analytics
  and cookies the site no longer used. A policy that describes another site is
  both unreadable and wrong.
- Every claim in it is checked like product copy: grep the site and the
  product backend for the providers actually called (email, SMS/WhatsApp,
  payments, AI APIs, error tracking, hosting, analytics, fonts, widgets) and
  observe cookies in a real browser: read them with Playwright's
  `context.cookies()` (a page-side read returned an empty list and made an
  agent publish "no cookies" wrongly) and cross-check with
  `curl -sI | grep -i set-cookie`. A CDN's bot protection sets its own cookie
  (`__cf_bm`, 30 min, Cloudflare in front of DigitalOcean App Platform) that
  the site's code never mentions: disclose it as a strictly necessary security
  cookie (no consent needed) instead of claiming "no cookies". For SaaS, separate the two roles: the
  company is controller for its own customers' account data and a processor
  (art. 28, DPA) for the data those customers enter about their own clients.
- The LSSI identity block (company name, tax ID, address, email, registry
  data) must exist on every site (legal notice or the policy's first section);
  unknown values are visible placeholders plus a USER_TODO item, never
  omitted. Structure and legal checklist: the **eu-law** skill.

**Copy and languages**
- The market's language first; finish one language, then port, with the port
  written in the repo's TODO. English, Catalan, Spanish and French each get
  their own re-read pass (catalan-writing). Watch for leaks between them:
  Catalan "tiquet" in Spanish copy, English "Privacy Policy" and
  "Toggle navigation" on a Spanish page.
- Sentence case for es/ca/fr; UI labels quoted exactly as the product shows them.
- No user-visible string hardcoded in a template: per-language data files or the
  i18n catalog.
- **Type the per-language data** (`Record<Lang, HomeCopy>`) so a missing
  translation is a build error, not a silent English fallback; add a build
  check for i18n key parity across catalogs and for em dashes in copy.

## Reviewing a site

1. **Two independent assessments, then synthesis** (the impeccable `critique`
   method): a design review (hierarchy, story, copy, imagery, mobile, Nielsen
   heuristics) and a measured one (detector, Lighthouse mobile and desktop,
   headings outline, every image with bytes and dimensions, contrast, page
   weight by type, third-party origins, console errors, tap targets). Run them
   as separate agents so the numbers do not anchor the design judgement.
2. **Verify the surprising findings yourself** before reporting them (the Times
   fallback, a 404) — a screenshot or a `curl` is enough.
3. **Full-page screenshots lie on animated sites.** AstroWind-style
   intersect fade-ins and `loading="lazy"` images leave sections blank in a
   full-page capture: capture with `reducedMotion: 'reduce'` and scroll each
   image into view (wait for `img.complete`) before judging.
4. Known false positives: a third-party widget that renders late (Trustpilot's
   iframe fills a few seconds after scrolling into view) looks "empty" in a
   full-page screenshot; localhost previews log CORS and captcha-host errors
   that production does not have.
5. Known tool gaps (2026-09): the installed impeccable skill lacked its bundled
   detector (`detect.mjs` → "bundled detector not found"; the npm package
   `impeccable` works as a fallback), and injecting a localhost overlay into the
   live https site is blocked by Chromium's Private Network Access. Run the
   overlay against `astro preview` on localhost instead (with the
   `@astrojs/vercel` adapter `astro preview` fails: serve
   `.vercel/output/static` with a static server).
6. **Security findings are reported, not silently fixed** in components the
   review does not own (the app, the backend): the 2026-09-26 reviews found
   open signups without the anti-bot kit on the FichaChat app, LeadHunter
   and Accountant. Put them in the report and the owning repo's TODO.
7. Report as the user reads it: verdict, what works, prioritised issues (P0–P3)
   with the fix each, then the decisions that are theirs. Persist the snapshot
   (`.impeccable/critique/`) and say whether to commit or ignore it.

## Fixing a site with parallel agents

Split by **file ownership**, never by topic, so agents on the same working tree
cannot collide:

| Agent | Owns |
|---|---|
| Page markup and styles | the page view, the global stylesheet, small presentational components |
| Copy and data | the per-language content data file(s) |
| Site chrome | header, footer, base layout (head/meta), i18n catalog |
| Assets | `static/**` (or the real publicDir), the video working folder |

Before launching, the orchestrator writes the **contracts** into every prompt:
the exact data interface the markup codes against, and the exact asset paths
and pixel sizes the data references. Settle the product decisions up front
(which CTA, what replaces the footer form, whether a structural fix applies to
every language) so agents do not ask each other. Agents do not commit; the
orchestrator integrates, builds, runs the visual diff (only the intended pages
change), reviews the screenshots, and commits.

**Other sessions share the machine.** Never `pkill -f <pattern>`: on
2026-09-26 it matched the calling shell and other sessions' renders and
killed video builds on several sites. Kill by exact PID from `ps`, and
check a port is free with `ss -ltnp` before starting a preview.

## Shipping

- A push to the site's deploy branch is a production deploy: push only with a
  yes, and first list what else rides along (`git log origin/<branch>..`) — an
  unpushed commit from another session deploys with yours; report it.
- After the deploy: poll the live page for the new markup, fetch the new assets
  (status, content-type, range support, bytes identical to the build), and check
  in a real browser: media plays, the right cut per breakpoint, forms still
  work, other languages unchanged.
- Then the housekeeping the global rules require: the repo's deploy doc, the
  TODO for the language ports, the team mail when authorised (content-creation
  and the project's mail archive), Gatus/Talaia for any new public surface.

## Worked example: BikeCRM, 2026-09-26

Spanish home (`bikecrm.com/es/`, Astro, `bikecrm-web-comercial`) reviewed at
20/40 (Nielsen): a 2020 Bootstrap-era template around a new launch video.
Findings that became this skill's checklist: no `<h1>` and title "BikeCRM", SVG
mockups in Times, an 855 KB base64-PNG SVG, a 2 MB stock background, two CTA
labels in two colours, a footer GetForm + hCaptcha form loading on every page,
`#ff5722` contrast failures, a `<span>` language switcher, English strings on
the Spanish page, "Tiquet" (Catalan) in Spanish copy — copied into the launch
video too — a manifest 404 from the stale `public/` folder, mobile CLS 0.435.
Fixed the same day with four file-owned agents (markup, copy/data, chrome,
assets) plus an integration pass that found what no single agent owned: the
768–990 px header overflow (pre-existing on live), a nested `<main>` on the 404
page, alt texts that did not match the final screenshots, and the CDN serving
the old video under the reused file name. Deployed as `bikecrm-web-comercial`
`60dd684`.
