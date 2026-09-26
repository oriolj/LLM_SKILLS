---
name: content-creation
description: Make marketing content for any of our products — launch/brag videos (via the /brag-slim skill), Reels/Shorts vertical cuts, share copy, posters, concept illustrations for product sites (composed app cards, not screenshots; HTML rendered to transparent WebP with a checked contact sheet), putting the finished video on the product's website, keeping every asset's sources in the site repo (build-excluded `content-sources/`, no MP4s in git), and showing video in newsletters (a linked still or GIF, never an embedded MP4). Carries Oriol's content preferences (the real product shown as concept illustrations rather than raw screenshots, the product's own copy and claims, the market's language, no generic SaaS phrasing), the field lessons from the BikeCRM launch video (2026-09-26: render pipeline, verifying a soundtrack you cannot hear, vertical safe zones, transition collisions), and the web-embedding rules (self-hosted H.264 MP4, click-to-play vs muted autoplay, preload, posters, per-breakpoint cuts, per-locale pages, file-size budgets). Use when the user says "make a video / launch video / promo / brag about this", "/brag", "make a vertical version for reels/tiktok/shorts", "write the share copy / post", "add the video to the website / landing page", "how do we embed this video", "is mp4 the right format", or asks for social or marketing content for BikeCRM, EnaCast, Panotxa or any other project.
---

# Content creation

Marketing content for our products: short launch videos, their vertical cuts,
share copy, and getting the result onto the product's website. The video
itself is made by the **/brag-slim** skill; this skill holds what that skill
does not know — our preferences, what went wrong the first time, and how the
output goes live.

## Preferences (Oriol)

- **Show the real product, as a concept.** The app doing its job (its real top
  bar, components, status chips and copy) beats a landing page describing it,
  and beats stock or abstract visuals. Build it as composed HTML cards from the
  project's own styles and assets (colours and fonts read from the source, not
  guessed), not as raw screenshots: Oriol prefers concept illustrations that
  show what the software is about over screenshots (2026-09-26), in videos and
  still images alike.
- **The product's own words.** Headlines, feature names and figures come from
  the marketing site / catalogs (`home.ts`, i18n files, `llms.txt`). Illustrative
  UI text (a customer name, a task price) is fine; invented claims, numbers or
  testimonials are not. No generic SaaS language ("streamline your workflow").
- **The market's language.** BikeCRM's video is in **Spanish** (its home market
  and the site's x-default). EnaCast team-facing material is Catalan. Other
  languages get their own cut, never a Spanish video on an English page. Catalan
  or Spanish copy → load **catalan-writing** and apply sentence case (global i18n
  rule).
- **Nothing ships without being seen.** Stills from every scene and from every
  transition, checked before the full render; the published page checked with
  the site's visual diff.
- **Outward-facing steps need a yes.** Committing the website change is part of
  the job; pushing it (production deploy on most of our sites) and posting to
  social accounts wait for Oriol's explicit go.

## Making the video: /brag-slim

`/brag-slim` (installed in `~/.agents/skills/brag-slim`, symlinked into
`~/.claude/skills/`) turns a project directory or URL into a ~20 s video with
music, a poster and share copy, written to `brag-output/` in the current
directory with every intermediate file in `brag-output/work/` (a scratch location: move the sources into the site repo's `content-sources/` afterwards, see below). Options:
`--tone default|polished|yc-parody|chaotic|deadpan|cinematic|app-store`,
`--format landscape|vertical|square`, `--duration`.

Run it from the **product's parent folder** when the product is several repos
(BikeCRM: `~/git/BikeCRM`), so it can read the marketing site, the app and the
docs together. Tell it the angle up front if there is one (a new feature, a
release).

### What worked (BikeCRM, 2026-09-26)

- **Story shape:** hook on the customer's pain in their own terms (handwritten
  workshop slips: "¿Dónde está la Orbea?") → logo + the site's headline → one
  object followed through the product (one bike: service sheet → timer → tasks
  complete → "Notificar al cliente" → SMS on a phone → dashboard stats) → CTA
  with the site's real offer ("Pruébalo gratis · 30 días · sin tarjeta").
  Following ONE object makes three features read as one flow.
- **Render pipeline:** one HTML page where every element's style is a pure
  function of `t` (`window.render(t)`), fonts awaited with `document.fonts.load`
  for every weight used (Material Icons included), captured with Playwright
  borrowed from a project's `node_modules` (`createRequire(<repo>/package.json)`)
  and `executablePath: '/usr/bin/chromium'`, JPEG screenshots piped into
  `ffmpeg -f image2pipe`. 630 frames at 1080p took a few minutes.
- **Measure, don't guess, click targets:** a simulated cursor must land on real
  buttons — read their centres with `getBoundingClientRect()` at the target time
  and subtract the pointer's tip offset. Chromium's CSS `zoom` is honoured by
  those rects, which makes `zoom` the easy way to shrink a whole app window for a
  vertical layout.
- **Soundtrack in numpy** (no scipy on the box): additive plucks/pads/bells in
  one key and tempo, FFT filtering for noise, one shared FFT-convolution room
  for music and effects, every cut on a beat (120 BPM → cuts on multiples of
  0.5 s).
- **Checking audio you cannot hear:** `showspectrumpic` + `showwavespic` images
  and `ebur128`. Targets: about **−14 LUFS integrated, true peak ≤ −1 dBFS**.
  The first mix measured −11.5 LUFS (squashed), the hook was a quarter of the
  drop's amplitude (a hook must not be the quiet part) and hi-hats were
  full-band click lines; fixed with a band-limited, 1.5 ms-attack hat, a
  half-level kick and a louder pad in the hook. Still tell Oriol to listen
  before posting.
- **Transition collisions only show mid-transition.** Two found by stills at
  in-between times: an entering phone rising over a still-visible app window
  (fix: stagger — old out, then new in) and a window exiting leftwards across
  the caption (fix: exit away from the text).
- **Poster = frame 0:** the strongest settled frame (text fully in), replacing
  frame 0 via `overlay=enable='eq(n,0)'` so duration and audio sync stay exact.
  Check the cursor does not cover a label in the chosen frame.

### Vertical (Reels / Shorts / TikTok)

Re-lay out the scenes for 1080×1920; never crop the landscape cut. Same timings,
so the soundtrack is reused unchanged. Keep text and key UI clear of:

- the top ~200 px (status bar, account header),
- the bottom ~380 px (caption, audio credit, CTA overlays),
- the right ~130 px from mid-height down (like/comment/share column).

Captions go on top in two lines, the product below; headlines rewrap
(`¿Tu taller vive<br>en papelitos?`); the CTA stacks centre-frame. Around 15 s
loops best on Reels; offer a tighter cut if the landscape one is 20 s+.

**Wide app screens: re-capture the real app at phone width, don't crop the
desktop capture** (EnaCast Insights, 2026-09-26). A desktop card scaled into a
940 px column shrinks its text to ~12 px. Load the same page with a narrow
viewport (`deviceScaleFactor: 3`) so the app's own responsive layout rewraps
the cards, then crop those. Check the width first: at 430 px EnaCast Studio
truncated the marker titles and clamped the summary. At 560 px it stayed one
column with full titles. Measure line boxes with
`Range.getClientRects()`, and remember a line-clamped paragraph reports its
hidden lines too. Table-shaped UI (lists, grids) crops fine as column subsets:
title + status columns side by side, or three days of a week grid. For
headlines, set line breaks per format rather than trusting the wrap: a
one-word last line ("show?", "itself.") showed up in both the vertical and
square cuts.

### Deliverables and where they live

`brag.mp4` + `brag.jpg`, `brag-vertical.mp4` + `brag-vertical.jpg`,
`share-copy.txt`, `brag-plan.md`, and the reproducible sources in `work/`
(`video.html`, `video_v.html`, `audio.py`, `capture.mjs`).

**The sources belong in the product's commercial-site repo, not in a loose
working folder** (Oriol, 2026-09-26): a `content-sources/` folder at the repo
root, next to `src/` and outside everything the build reads, holding the HTML
scenes, soundtrack generator, capture/render scripts, a `make-video.sh vN` and
`make-illustrations.sh` that write the web-ready files into the site's public
folder, the brand assets they use, the plan and share copy, and a README.
**Git-ignore the outputs and intermediates — never commit the MP4s** (masters,
silent renders, stills, WAV): they are regenerated by the scripts. Make the
scripts self-contained (Playwright from the site's own `package.json`, paths
relative to the script), no credentials in them, and prove it: rerun them from
the repo and compare the outputs with what is live byte for byte. BikeCRM:
`bikecrm-web-comercial/content-sources/` (`f52914f`). A re-roll of one scene
is then an edit and a rerun, by anyone, on any machine.

## Concept illustrations (the site's product images)

The default product image for a website, a newsletter or a deck is a **concept
illustration**: a still scene in the launch video's visual language, not a
screenshot. BikeCRM's four (2026-09-26,
`bikecrm-web-comercial/content-sources/illustrations.html`, one `?s=<scene>` per image, built by its `make-illustrations.sh`):

| Scene | Idea | What is on it |
|---|---|---|
| `hero` 1600×1000 | the workshop at a glance | sidebar card, two counters, a bike card with its timer, two task rows, a "client notified" toast, the + button |
| `sheet` 1200×900 | one repair, step by step | the service sheet: step bar, four tasks with status chips, total, a floating running timer |
| `history` 1200×900 | every client's history | client card, a timeline of past service sheets, a wear warning |
| `notify` 1200×900 | the bike is ready | the "Notificar cliente" button and the message the client receives on a phone, plus a "sent" toast |

How to make them:
- **Brief first, one line per image:** the product truth it shows ("a client's
  whole history is one tap away") and its visual hook (the timeline). If the
  line is vague, the image will be too. Across a set, vary the device (a list,
  a timeline, a phone, a step bar) so the page does not repeat one composition.
- **One idea per image**, three to six cards, overlapping slightly on a soft
  rounded panel (`#f4f1ec`), generous shadows, lots of air. A viewer should get
  the idea in a second, at phone width, so text is large (≥ 20 px at 1x) and
  there are few rows.
- **The app's own words:** every label on a card comes from the app's i18n
  catalog for that language (BikeCRM: `Completada`, `Pendiente`, the step bar
  `Iniciado › Cerrado › Notificado › Pagado`, `Notificar cliente`), so the
  illustration matches the product a trial user opens. Invented data only.
- **Render:** one HTML file, fonts awaited (`document.fonts.load` for every
  weight plus the icon font), Playwright `deviceScaleFactor: 2`,
  `locator('#stage').screenshot({ omitBackground: true })`, then
  `ffmpeg -vf scale=W:H:flags=lanczos -c:v libwebp -pix_fmt yuva420p
  -quality 88` for a transparent WebP at the exact size the page reserves
  (40–70 KB each).
- **Render with [`scripts/render-illustrations.mjs`](scripts/render-illustrations.mjs)**
  (`--html`, `--scenes name:WxH,...`, `--out`, `--require <a package.json whose
  node_modules has playwright>`, `--fonts "Lexend,Roboto,Material Icons"`,
  `--min-text 20`). It writes each WebP at its exact size, a 2x PNG, and one
  `contact-sheet.png` of every scene over white, and it checks automatically:
  every listed font family has a loaded face (a missing one means a fallback
  font, the Times trap), no text overflows its box, and which text is smaller
  than the minimum (a decision, not always an error: a phone's clock is small
  on purpose). The HTML contract: one scene per `?s=<name>` inside `#stage`,
  and a `window.ready` promise that resolves after fonts and images load.
- **Look at the contact sheet** before shipping: wrapped labels, empty card
  bottoms and collisions only show up there. Then check the images in the real
  page at desktop and phone width: an image displayed at 60 % of its size
  shrinks its text too (20 px becomes 12 px), so the phone view decides whether
  the text is still readable.
- **Report honestly:** say what the script checked, what you looked at, and
  what nobody has checked yet.
- Per language: the labels are text, so each language gets its own render.

## Reference captures of the running app

Only to check what current cards look like (not to ship):

- Run the app locally with an **invented** business seeded for the purpose
  (BikeCRM: `bikecrm-web-comercial/content-sources/seed_marketing_business.py`, run in
  the local backend; business slug `qa-marketing-bikeshop`, clients such as
  Marta Puig with `@example.com` emails and `+34600000xxx` phones). Never
  production data.
- Capture at `deviceScaleFactor: 2`, then downscale (Lanczos) to the exact
  size the page reserves, as WebP around q82. Agree the paths and pixel sizes
  with whoever writes the page before capturing.
- **Local environments can hold live messaging credentials.** Capture the
  "notify the client?" dialog; never confirm it.
- Stop the containers and dev servers you started; leave the ones that were
  already running.

## Putting a video on a website

### Format: self-hosted MP4

- **H.264 (High) + AAC in MP4, `-movflags +faststart`** — plays everywhere and
  starts before it has fully downloaded. Web re-encode of a 21 s 1080p UI video:
  `-preset veryslow -crf 23 -c:a aac -b:a 128k` → ~1.9 MB (from 3.4 MB at CRF
  17) with no visible loss on UI text.
- **Self-host it** with the site's static files. A YouTube embed loads heavy
  third-party JS, sets tracking cookies (see **zero-cookies** — that brings the
  consent banner back) and brands the player; use it only when YouTube reach is
  the goal. Cloudflare Stream / Mux (adaptive bitrate) are for long videos, not
  a 2 MB clip.
- Optional extra: an AV1 WebM listed *before* the MP4 (often 30–50 % smaller; browsers
  that cannot decode it fall back). Not worth it under ~5 MB.
- **Re-encoding under the same name does not reach visitors** while a CDN holds
  the old file (BikeCRM: `s-maxage=86400`); version the file name
  (`bikecrm-es-v2-16x9.mp4`) whenever the content changes.
- **Size limits:** Cloudflare Pages rejects single files over 25 MiB — anything
  near that belongs in R2 or a video service. Cloudflare's CDN caches `.mp4` by
  extension, so origin cost is a non-issue for short clips.

### Playback: pick one deliberately

1. **Click to play, with sound** (default when the soundtrack matters):
   `controls playsinline preload="none"` + `poster`. Nothing downloads until the
   visitor presses play.
2. **Muted autoplay loop** (hero ambience): `autoplay muted loop playsinline`,
   plus an unmute control; browsers only autoplay muted, so most visitors never
   hear the music. Pause it under `prefers-reduced-motion: reduce`.

### Markup rules

- **Posters as WebP** (~30 KB at 1280 w vs 168 KB JPEG) — the poster is often
  the page's largest early image. Always set `width`/`height` on `<video>` so it
  reserves space (no CLS).
- **Per-breakpoint cuts: two `<video>` elements toggled by CSS**
  (`hidden md:block` / `md:hidden`), each with `preload="none"`. Not
  `<source media>`: the `poster` attribute cannot switch with it, so the phone
  would show a letterboxed 16:9 poster. With `preload="none"` the hidden element
  never downloads anything.
- **Per-locale:** a video whose copy is in one language appears only on that
  language's pages — make it an optional field in the per-language content data
  (BikeCRM: `video?` in `src/data/home.ts`, set for `es` only) rather than a
  hardcoded block. Section copy and `aria-label` go in that data, never inline.
- Captions (`<track>`) are needed only when there is speech; a music-only video
  needs an `aria-label`.
- Run the site's visual diff: only the pages that received the video may
  change. BikeCRM result: `es_home` desktop/mobile changed, the other 52
  screenshots 100 %.

## Video in newsletters and emails

An MP4 cannot be embedded in an email: Gmail and Outlook do not play `<video>`
(Apple Mail is the exception, and a newsletter is written for the worst
client). The BikeCRM newsletter's own
[email-HTML rules](../../../../BikeCRM/bikecrm-newsletter/.agents/skills/bikecrm-email-html/SKILL.md)
already forbid videos, iframes and forms. The pattern that works:

- **A still that links to the video.** A settled frame (the poster rule above)
  with a drawn play button, as an absolute-URL PNG/JPEG with explicit
  width/height and real `alt` text, linking to a web page that plays the clip
  (the product site, one page or anchor per feature). Most readers see it; the
  click lands where sound and controls work.
- **Or a short animated GIF** for a feature that is pure motion (a click and
  its result): 3-6 s, 600 px wide, few colours, under ~1 MB. Outlook desktop
  shows only frame 0, so frame 0 must stand alone as a still (the poster rule
  again). Link it to the full video.
- **Size budget:** images do not count toward Gmail's ~102 KB HTML clipping
  limit, but a multi-MB GIF delays the first screen on mobile data; keep one
  animated image per issue.
- **Per-feature clips:** `/brag-slim --duration 8` scoped to one feature, in
  the issue's language, same identity as the launch video. The web copy goes in
  the site's `static/video/`; the email only gets the still/GIF plus the link.

## Per-project notes

- **BikeCRM** (`~/git/BikeCRM`): brand `#ff5722` / `#1f1f1f`, Lexend headings,
  Roboto UI; isologos in `bikecrm-web-comercial/public/svg/`
  (`isologo_BikeCRM_white.svg` = white wordmark + orange bike, for dark
  backgrounds). The marketing site's `publicDir` is **`static/`** (a stale
  `public/` also exists — do not put new files there); videos in
  `static/video/bikecrm-<lang>-<16x9|9x16>.{mp4,webp}`; section on the Spanish
  home via `HOME.es.video`. The site deploys on push to GitLab `master`
  (DigitalOcean App Platform behind Cloudflare) — push only with Oriol's go.
  Launch video (2026-09-26): sources, video and illustration build scripts in
  `bikecrm-web-comercial/content-sources/` (`make-video.sh vN`,
  `make-illustrations.sh`); live encodes `static/video/bikecrm-es-v2-*`;
  illustrations `static/images/illustrations/es/`.
- **EnaCast** (`~/git/EnaCast`, commercial site `enacast-comercial-website`,
  Astro, `publicDir` = `public/`, deploys to Vercel on push to `master`):
  brand Signal Green `#2DD4A8`, Studio Navy `#0A1628`, Inter; vector
  wordmark SVGs in `enacast-ramen/public/enacast/`. Product UI comes from
  EnaCast Studio (`enacast-ramen`) on its local dev server
  `ramen.localhost:3203`, which **talks to production**: capture as the
  `oriol.radiotest` test account, read-only (never submit a form or press
  "Genera notícia"), and skip its transcript view (radiotest airs music, so it
  holds song lyrics). Promo videos (2026-09-26, `265dee8`): launch + Insights,
  English headlines over the Catalan UI, sources in
  `content-sources/brag/` (`make-video.sh vN`, rebuilt masters decode
  frame-identical to the delivered ones), encodes
  `public/video/brag/enacast-<launch|insights>-en-<vN>-<16x9|9x16>.{mp4,webp}`,
  wired through `src/data/brag-videos.ts` (per-cut versions) into the home
  and podcasting pages of each language that has a cut. **ca and es cuts
  added the same day** (`d03e82f`): copy per language in
  `content-sources/brag/copy/<lang>.json`, written from that language's
  catalogs (never translated), with `key.v`/`key.q` line breaks and a
  `_layout` override where a language runs longer; the es cuts show the
  **Spanish Studio UI**. Studio re-sets its `ui_language` cookie from the
  radio's language on every boot, so the capture browser blocks cookie writes
  to it (`addInitScript` on `document.cookie`) and sets its own: a
  per-browser language switch with no write to the account
  (`content-sources/brag/capture-common.mjs`). **fr added the same day**
  (`589b195`), with the Studio UI in French and the site's French typography
  in the video copy: a narrow no-break space (U+202F) before `?` `:` `;` and
  inside « », "11 h" rather than "11:00" (check the site's own catalog for
  which space it uses before writing any French). de/it have no cut yet.
  **Claims in a video are claims on the site:** v1 said "More than 560
  radios"; the site review found ~233 active radios, so launch en went to v2
  with the site's line ("Local, municipal and community stations work with
  EnaCast"). Check a video's figures against the site's verified-claims table
  (`PRODUCT.md`) before rendering, because a baked-in number needs a
  re-render to fix.
