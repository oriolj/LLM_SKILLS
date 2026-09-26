---
name: content-creation
description: Make marketing content for any of our products — launch/brag videos (via the /brag-slim skill), Reels/Shorts vertical cuts, share copy, posters, putting the finished video on the product's website, and showing video in newsletters (a linked still or GIF, never an embedded MP4). Carries Oriol's content preferences (real product UI over mockups, the product's own copy and claims, the market's language, no generic SaaS phrasing), the field lessons from the BikeCRM launch video (2026-09-26: render pipeline, verifying a soundtrack you cannot hear, vertical safe zones, transition collisions), and the web-embedding rules (self-hosted H.264 MP4, click-to-play vs muted autoplay, preload, posters, per-breakpoint cuts, per-locale pages, file-size budgets). Use when the user says "make a video / launch video / promo / brag about this", "/brag", "make a vertical version for reels/tiktok/shorts", "write the share copy / post", "add the video to the website / landing page", "how do we embed this video", "is mp4 the right format", or asks for social or marketing content for BikeCRM, EnaCast, Panotxa or any other project.
---

# Content creation

Marketing content for our products: short launch videos, their vertical cuts,
share copy, and getting the result onto the product's website. The video
itself is made by the **/brag-slim** skill; this skill holds what that skill
does not know — our preferences, what went wrong the first time, and how the
output goes live.

## Preferences (Oriol)

- **Show the real product.** The working app doing its job (its real top bar,
  its components, its status chips, its copy) beats a landing page describing
  it, and beats stock or abstract visuals. When the app cannot be run with data,
  rebuild its screens in HTML from the project's own styles and assets — colours
  and fonts read from the source, not guessed.
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
directory with every intermediate file in `brag-output/work/`. Options:
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

### Deliverables and where they live

`brag.mp4` + `brag.jpg`, `brag-vertical.mp4` + `brag-vertical.jpg`,
`share-copy.txt`, `brag-plan.md`, and the reproducible sources in `work/`
(`video.html`, `video_v.html`, `audio.py`, `capture.mjs`). Keep the sources:
a re-roll of one scene is a few edits and a re-render, not a new video.
`brag-output/` is a working folder — it is not committed to a product repo;
only the web-optimised encodes are.

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
  Launch video v1 (2026-09-26): sources in `~/git/BikeCRM/brag-output/`,
  committed to the site as `394f8e3`.
