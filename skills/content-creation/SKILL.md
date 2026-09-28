---
name: content-creation
description: Make marketing and product content for any of our products — edit filmed customer interviews (transcribe, trim head/tail, cut flubs/retakes/unanswered questions into a lossless raw cut, a long YouTube episode with sections and chapters, speaker-framed vertical clips with LLM-reviewed subtitles, a content plan with the publishing order), feature videos made in parallel on a shared kit and joined into a compilation (the newsletter / WhatsApp-channel / YouTube video) with a channel message, publishing through Postiz (Instagram Reels, YouTube Shorts, a publication register, a pacing monitor), and four kinds of made video, each with its own pipeline (a PROMO launch/brag video via the /brag-slim skill; a FEATURE HIGHLIGHT, one feature at a readable pace with music; an ANIMATED HOW-TO series of short step-by-step clips on a shared HTML kit; a SCREEN RECORDING of the real app driven by Playwright with redaction, captions and phone framing), assembling clips into a size-capped deliverable (tenders, 25 MB H.265), Reels/Shorts vertical cuts, share copy, posters, concept illustrations for product sites (composed app cards, not screenshots; HTML rendered to transparent WebP with a checked contact sheet), putting the finished video on the product's website, keeping every asset's sources in the site repo (build-excluded `content-sources/`, no masters or intermediates in git), per-language renders, byte-reproducible re-encodes, and showing video in newsletters (a linked still or GIF, never an embedded MP4). Carries Oriol's content preferences (the real product shown as concept illustrations rather than raw screenshots, the product's own copy and claims, the market's language, no generic SaaS phrasing), the field lessons from the BikeCRM launch video (2026-09-26: render pipeline, verifying a soundtrack you cannot hear, vertical safe zones, transition collisions), and the web-embedding rules (self-hosted H.264 MP4, click-to-play vs muted autoplay, preload, posters, per-breakpoint cuts, per-locale pages, file-size budgets). Use when the user says "make a video / launch video / promo / brag about this", "feature video / highlight this feature", "tutorial / how-to video", "record the screen / screen recording of the app", "edit / transcribe / cut this customer interview", "make feature videos of what we shipped", "compile the feature videos", "schedule these on Postiz / Instagram / YouTube", "write the WhatsApp channel message", "videos for a tender / licitació", "/brag", "make a vertical version for reels/tiktok/shorts", "write the share copy / post", "add the video to the website / landing page", "how do we embed this video", "is mp4 the right format", or asks for social or marketing content for BikeCRM, EnaCast, Panotxa or any other project.
---

# Content creation

Marketing and product content for our products: videos, their vertical cuts,
share copy, and getting the result onto the product's website. Only the
**promo** kind of video is made by the **/brag-slim** skill; the three other
kinds have their own pipelines below. This skill holds what /brag-slim does not
know — our preferences, what went wrong the first time, and how the output
goes live.

## Four kinds of video — pick one first

They answer different questions, so they differ in length, sound, data and
truth rules. Decide which one is being asked for before building anything;
"a video of feature X" is usually a feature highlight; "how do you do X"
is a how-to; "prove it works" is a recording; a promo is for the whole product.

| | **Promo** (launch / brag) | **Feature highlight** | **Animated how-to** | **Screen recording** |
|---|---|---|---|---|
| Answers | "why should I care about the product?" | "what does this ONE feature do for me?" | "how do I do it?" (and "what does it look like?") | "does the real product really do it?" |
| Made with | `/brag-slim` + [its section](#making-a-promo-video-brag-slim) | a scene file + the shared soundtrack engine, [below](#feature-highlight) | the how-to kit, [below](#animated-how-to-series) | Playwright + CDP screencast, [below](#screen-recordings-of-the-real-app) |
| Shape | one piece, 15–25 s, fast cuts, the whole product | one piece, 30–45 s: hook (the problem) → the feature in 2–4 UI beats → outro | a SERIES of 10–20 s clips, one per task, each standing alone; assembled into longer tutorials with curtains | the same clips as the how-to, shot on the running app |
| On screen | headlines + concept cards of the app | a headline per beat (left) + one concept card of the feature with a pointer (right); brand wordmark scene and outro | numbered steps that tick off (left), an enlarged concept card of the real screen with a pointer doing the steps (right), one caption (bottom) | the real app, a drawn pointer, one caption, phone clips in a phone frame |
| Sound | music bed + UI events | a calmer bed + UI events (clicks, plucks, typing) on the beats | none by default (tutorials, tenders), optional | none |
| Data | invented, plausible | invented, plausible; labels copied exactly from the catalogs | invented, plausible; **labels copied exactly** from the catalogs | the account it is recorded on (test account for rehearsals, the client's for the deliverable) |
| Truth rule | the product's own claims only | the feature as it ships; published only after its deploy | **only what the product does**: a step the product can't do is not drawn | the product as it is, bugs included; sobre-C-style data redacted |
| Uses | site hero, social | release announcements, the feature's section on the site, newsletter issue, WhatsApp/social share | help centre, onboarding, commercial showcase, the storyboard/checklist for a recording | tenders and proofs, support, "is this real?" |
| Reference | BikeCRM / EnaCast launch videos | EnaCast "Seccions habituals" v2, `enacast-content-creation/videos/2026-09-27-seccions-habituals/` | Ràdio Sant Vicenç tender, `enacast-content-creation/videos/2026-09-27-licitacio-rsv/animated/` | same folder, `recorded/` |

The how-to and the recording are usually made **together, clip by clip**: the
animation is the precise storyboard (what must be visible, in what order), the
recording proves it on the real app, and the gaps between them are product
findings. A fifth kind, **customer interviews**, is filmed footage that
is edited rather than built: [its own pipeline](#customer-interviews-real-footage-edited). A promo or a feature highlight can reuse how-to concept cards, and a
feature highlight is the natural companion of a release: the highlight sells
the feature, its how-to clips teach it.

## Preferences (Oriol)

The cross-product preferences, the shared newsletter pattern and the register
of what content exists per product live in hq
[`growth/content/README.md`](../../../../../Syncthing/Syncthing-mobile-docs/hq/growth/content/README.md).
Read it first. A new preference Oriol states goes there (and here only when it
changes how this skill's pipeline works).

- **Pace feature videos for reading the UI** (Oriol, 2026-09-27: "you move a
  little bit too fast, I don't have time to see what I am seeing"). Our videos
  are almost always feature showcases, so the **feature highlight** (below) is
  the usual kind and its pacing is this rule; a promo keeps /brag-slim's
  15–25 s only when a fast teaser is asked for; how-to clips have their own
  10–20 s budget per task. The rule: one UI step per beat; after each action the result holds, settled,
  for ≥ 2 s before anything moves again; UI scenes of 6–8 s; 30–45 s in total
  for 4–5 steps; cursor moves ≥ 0.6 s; lists fill one row every ~0.6 s, not
  0.3–0.4 s. Pass `--duration` accordingly and check the storyboard against
  this before building. A short teaser is the exception, and only when asked.
  Stressed again 2026-09-28: **every** change on screen counts as an action
  (a list filling, a status or badge appearing, a screen opening), the UI is
  shown big enough to read at phone width, each caption says what the step
  shows (not a slogan), and when in doubt take the longer hold — EnaCast's
  first cut at 22.5 s was too fast, the re-paced 39.5 s was right. Before
  rendering, write in the video README a table of each beat: when the
  action happens and how long its result holds.
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

## Making a promo video: /brag-slim

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
  vertical layout. **`zoom` on an absolutely positioned layer also scales its
  `left`/`top`**: zoom an inner wrapper, not the positioned element.
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
  Check the cursor does not cover a label in the chosen frame. On a web page
  the poster must not repeat the page's `<h1>`: pick the settled product
  frame, not the headline card.
- **Reproducible renders:** parallel Chromium renders are not
  byte-reproducible, so render serially when the output must prove
  identical; single-threaded x264 (`-threads 1` plus `-fflags +bitexact
  -flags:v +bitexact -flags:a +bitexact`) makes re-encodes byte-identical.
  Mux the final audio from the WAV master (re-encoding an existing AAC track
  pushed true peak to −0.2 dBTP). Make render scripts resumable per cut, so a
  killed run does not restart from zero.

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
**Masters, stills, silent renders and WAVs are never committed**: the
scripts regenerate them. The small web encodes in the public folder are a
per-site choice, written in `content-sources/README`: either commit them
(BikeCRM, Enantena, FichaChat do; git-connected deploys need them), or, when
the deploy is a direct upload from a machine that has them, git-ignore them
and add a prebuild check that fails with the regenerate command (EnaChat,
Panotxa). Make the
scripts self-contained (Playwright from the site's own `package.json`, paths
relative to the script), no credentials in them, and prove it: rerun them from
the repo and compare the outputs with what is live byte for byte. BikeCRM:
`bikecrm-web-comercial/content-sources/` (`f52914f`). A re-roll of one scene
is then an edit and a rerun, by anyone, on any machine.

## Feature highlight

One feature, told like a promo but slow enough to read the UI. It is the kind
Oriol asks for most ("a video of <feature>"). **Always an animation of concept
cards, never a screen recording** (Oriol, 2026-09-27: "I prefer the brag-like
animations for feature announcements"). Recordings are for proofs and
tenders; an announcement shows the idea, clean, on-brand and unaffected by
test data or UI bugs. Reference: EnaCast "Seccions
habituals" (`enacast-content-creation/videos/2026-09-27-seccions-habituals/`,
v2 = 39.5 s; v1 at 22.5 s was judged too fast). Not /brag-slim: its
fast-cut defaults are what made v1 unreadable.

- **Story, 30–45 s**: a navy **hook** that states the listener's/user's
  problem in their words (4–6 s) → the **wordmark + feature name + one-line
  promise** (3–4 s) → **2–4 UI beats**, each a headline on the left and one
  concept card on the right where the pointer does ONE thing and the result
  holds ≥ 2 s (6–8 s per beat) → a navy **outro** with the feature name, the
  promise and the product URL (3–4 s).
- **One idea per beat, one action per beat.** If a beat needs two clicks, it is
  two beats or it belongs in a how-to.
- **Concept cards from uncommitted code are fine** (the feature may not be
  deployed yet): copy every label from the catalogs, invented data, cite the
  keys in the video README. Publishing waits for the deploy.
- **Pointer targets measured, never guessed**: at `window.ready`, from the
  untransformed layout (`getBoundingClientRect` of the real buttons);
  hand-placed coordinates missed by 100+ px.
- **Sound**: the shared engine (`shared/audio/synth.py`: `Track(dur,
  cuts).bed()` + the video's events on the scene times + `.transitions()`),
  softer than a promo; every cut on the beat.
- **Re-pace with a time map, never by re-animating**: author the scene once
  and define cuts in `timing.js` as `holds` (`[t, seconds frozen]`) and
  `slows` (`[from, to, factor]`); the page (`?cut=v2`) and `soundtrack.py`
  read the same file, so picture and sound stay in sync; holds in multiples
  of the beat. `video.conf` lists `CUTS`, per-cut `DUR_`, `POSTER_T_`,
  `STILLS_`.
- **Check before rendering**: `make check V=<video> [C=<cut>]` renders a still
  of every scene and every transition into a contact sheet; look at it, then
  `make video`.
- **Built for a muted feed**: social autoplays without sound, so every beat's
  headline carries the story on its own; the hook states the problem in the
  first 2 s; frame 0 is the poster (feature name + the card), readable as a
  still.
- **Lessons from BikeCRM V1 "Terminal compartido"** (2026-09-28, the kit
  ported to `bikecrm-content-creation/shared/`):
  - **One scene page for both formats** (`?fmt=9x16` + a per-format layout
    object), not a second scene file: same timings, one soundtrack, pointer
    targets measured per format.
  - **Use the frame.** The first cut left the 9:16 bottom half empty and the
    16:9 card at a third of the width, unreadable on a phone: the card fills
    the 9:16 frame down to the bottom safe zone (~984×1026 px) and ~57 % of the
    16:9 width; list text ≥ 28 px on screen. Look for empty space on the
    stills as hard as for clipped text.
  - **Draw only what the product shows.** A beat planned as "an action signed
    with your name" was dropped because the app never renders who finished
    a line; the traceability went to the owner's switch log instead.
  - Tooltips go on the side away from the pointer (it covered them).
  - The build normalises loudness to −14 LUFS with a fixed gain capped at
    −1 dBTP (sidecar), converts JPEG frames to limited-range BT.709
    (`scale=in_range=pc:out_range=tv`, else the MP4 is `yuvj420p`), and
    fails when a font does not load.
  - A time map can also shorten: a slow with factor < 1 compresses a stretch
    where nothing moves, trimming the tails left after adding holds.
- **One claim, the site's claim**: the promise line comes from the feature's
  release note or site copy; figures only if the site's verified-claims table
  has them (a baked-in number needs a re-render to fix).

**Cadence** (Oriol, 2026-09-28): feature announcements are time-sensitive
and go out as soon as possible — the compilation first (so the WhatsApp
channel and newsletter can link it the same day), then the single videos one
a day; interview content is evergreen and drips weekly over weeks.

### The compilation (the "novedades" video)

Oriol, 2026-09-28: several feature highlights **joined one after another
with a good transition** make one video, and **this is the kind of video
sent in the newsletter and the WhatsApp channel and uploaded to YouTube**
(the single highlights stay for social and the feature's own place).
- Join the finished cuts in order, no re-authoring; a brand transition
  between them (a short wipe/crossfade in the brand colours, the sound
  crossfaded), the repeated per-video outros removed so only the last
  one remains (cut each video where its outro starts), one intro/title
  if it helps.
- One encode at the end: 16:9 1080p H.264 for YouTube (chapters in the
  description, one per feature, first at 00:00); the newsletter gets a
  poster still / GIF linking to it (never an embedded MP4); for the
  WhatsApp channel, the file itself (as a document) or the YouTube link.
- Loudness −14 LUFS on the whole; check every seam on stills and by ear.
- First run (BikeCRM, 2026-09-28): `make compile V=<folder>` in the content
  repo (`scripts/compile_videos.py`, spec `compilation.json` with each item's
  `outro_start`), V1→V5 = 3:21, xfade `smoothleft` 0.6 s + acrossfade, both
  formats in one run (~1 min each), chapters.md written. Five feature videos
  were made in parallel by one agent each on the shared kit, then reviewed
  from sampled frames before joining.

### The announcement package

A feature lands when the video arrives with everything around it. Plan the
whole set in the video README before rendering, and ship it together, after
the feature's deploy (Oriol's go for anything public):

| Piece | Spec | Where it goes |
|---|---|---|
| Video 16:9 | 30–45 s, H.264 MP4 + poster | the feature's section on the site, the release-note entry, YouTube/LinkedIn |
| Video 9:16 | the same beats re-laid for vertical safe zones (not a crop), ≤ 30 s | Reels/Shorts/TikTok, WhatsApp status |
| Square still | the poster frame re-composed 1:1 | LinkedIn/X image post, link previews |
| Newsletter GIF | 3–6 s of the key beat, 600 px, ≤ 1 MB, frame 0 standalone, linked to the video | the next issue ([below](#video-in-newsletters-and-emails)) |
| Share copy | per channel and language: LinkedIn (3–5 lines, the problem → the feature → the link), X (1–2 lines), WhatsApp (2 lines, first person from the team) | `copy/<channel>-<lang>.txt` next to the scene |
| Release note | one line in the product's words, the same promise as the video | the product's changelog / release notes |
| How-to clip (optional) | the matching animated how-to clip for "how do I use it?" | help centre, linked from the release note |
| Team mail | Catalan, labels quoted from the `ca` catalog, what changed + how to try it | only when Oriol asks |

- **Same words everywhere**: the feature name, the promise line and the UI
  labels are identical in the video, the copy, the release note and the site;
  write them once in the README and copy from there.
- **Per language, from that language's catalogs**, never translated; a
  language without a cut gets no video on its page.
- **Delivery to Oriol first**: the 16:9 on WhatsApp as a document for review;
  the rest after his verdict.

## Animated how-to series

A series of short, silent, precise tutorials, one per task, on a shared kit so
every clip reads as one product. Built 2026-09-27 for the Ràdio Sant Vicenç
tender (32 clips, two assembled tutorials); copy that folder to start a new
series: `enacast-content-creation/videos/2026-09-27-licitacio-rsv/`
(`README.md` is the full brief, `kit/kit.js` documents the API, `animated/A3.html`
is the reference clip).

- **A manifest is the single source**: `clips.json` holds id, section, title,
  caption (rètol), duration, device (desktop/phone) and a `show` line (what
  must be visible). Pages, overlays, assembly and `status` all read it
  (`kit/clips.js` is generated from it for the pages).
- **One layout for every clip**: left = section, title and 3–4 numbered
  imperative steps that go pending → active → ✓ (so the clip doubles as a
  checklist); right = a window with NO address bar, or a phone; bottom = the
  caption. `K.clip({id, steps:[{at,text}], html, cursor:[[t, selector, {click}]],
  render(t,U)})`; every style a pure function of `t`, so the shared
  `render.mjs` renders it like any scene.
- **Concept cards are the real screen, enlarged**: look at the running app
  first (screenshot it), copy the layout and the labels EXACTLY from the
  catalogs and cite the keys in the clip's header comment; text ≥ 17 px so it
  survives a 720p export. Invented station and data.
- **Never draw a feature the product lacks.** The how-to is a promise; a step
  the product cannot do is reported, and the title/caption rewritten (the
  tender's "automatic news" clip became "news from a transcribed program").
- **Pointer targets are selectors measured live** each frame (a moving or
  scrolling element keeps the pointer on it); keyboard shortcuts get
  on-stage keycaps, since a pointer cannot show them.
- **Pacing per clip**: 10–20 s, ≥ 1.5 s settled after every click, the last
  ~1.5 s holds the finished state with every step ticked.
- Kit class names are global: prefix kit selectors (`.k-win > .bar`, not
  `.k-win .bar`), or a clip's own `.bar` restyles the window.

## Screen recordings of the real app

The same clips shot on the running product, fully scripted so a take can be
redone on another account by changing four env vars (`SITE_URL`,
`STUDIO_URL`, user, password). Reference: `recorded/rec.mjs` + `recorded/A3.mjs`
in the tender folder.

- **Capture the page, not the screen**: headless Chrome + CDP
  `Page.startScreencast` (JPEG q92, per-frame timestamps) → an ffconcat with
  each frame's real duration → 30 fps CFR. No browser chrome is ever captured,
  so no URL can leak; Wayland/X grabs are never needed.
- **Legibility**: desktop = a 1280×720 viewport at `deviceScaleFactor` 1.5 →
  1920×1080 frames with the UI 1.5× larger than a 1080p screen, readable after
  a 720p/480 kbps export. Phone = 390×798 (844 minus a 46 px status bar) at 2×,
  touch, iPhone UA; post-production draws the status bar and the phone frame,
  so the frame's dynamic island never covers the site header.
- **A drawn pointer** (headless has none): an init script draws an arrow (or a
  touch dot on phones) and a click ripple, moved by the helper's eased
  `moveTo`; its position survives navigations via `sessionStorage`. Every
  click is followed by ≥ 1 s. `addInitScript(fn, arg)` takes ONE argument:
  pass an object, or the second value arrives `undefined`.
- **Redaction in the page, before capture**: a MutationObserver hides any
  element whose text matches a forbidden list, with its card (walk up to the
  grid child), and any text that is only a domain or URL (a panel sidebar
  prints the tenant's domain). Hide dev badges (`nextjs-portal`,
  `astro-dev-toolbar`) and the PWA install banner. Still check every frame.
- **Locale**: set the app's language cookie AND run Chrome with
  `LANG=ca_ES.UTF-8` (process env) — `<input type=time>` follows the process
  locale ("10:00:00 AM" otherwise).
- **Post-production** (ffmpeg): caption PNG rendered from the same kit and
  faded in; on desktop it **fades out after ~6 s**, because a bottom caption
  covers the site's player bar; fades from/to the kit background. Bound every
  encode with `-t <duration>`: looped PNG inputs plus `anullsrc` make
  `-shortest` never end (one encode reached 1,033 s and 2.6 GB before it was
  killed).
- **Data**: rehearse on the test account (EnaCast: `oriol.radiotest` on the
  LOCAL stack, ramen `start-local` against the local backend, astro dev with
  `.env.local`); note originals before a write and restore them after the take
  (API or Django shell; the backend's per-process cache can hide shell
  writes, so restore through the API). Warm every route before `s.start()`
  (dev servers compile on first visit). Cache slow AI answers before the take
  rather than waiting on camera.
- **Parallel agents** (one per section worked well: 7 agents, 64 renders in ~70
  min): give each its own data (which episode it may edit, which is read-only),
  forbid edits to the shared kit/recorder (they report needed changes; the
  coordinator applies them), no commits from agents, per-agent scratch
  subfolders. Replace a script other processes may be running with
  write-new-then-`mv` (bash reads scripts as it runs), and use `command mv -f`
  / `command rm -f`: the shell aliases them to `-i` and an agent's command
  hangs on the prompt.

### Assembling a size-capped deliverable

Curtain + clips in manifest order + curtain → a CRF 14 master → the last step
is a two-pass encode whose bitrate is derived from the master's duration and
a byte target (`client-requests/radio-sant-vicenc-public-tender/export.sh`:
target 24,000,000 B for a "25 MB" cap, H.265 Main 8-bit, `hvc1`, BT.709
limited range, stills for a legibility check, fails over the cap). Always
encode from the master, never re-compress an export. H.265 was Oriol's call
for the tender (VLC plays it; stock Windows players may need the HEVC
extension); H.264 stays the default for anything public.

## Customer interviews (real footage, edited)

A fifth kind, and the only one that is **filmed, not made**: a customer
talking in their own shop, which Claude edits as Oriol's video editor
(Oriol, 2026-09-27). First one: BikeCRM × Sprint Bike (Sant Feliu de
Llobregat, recorded 2024-12-17), in
`~/git/BikeCRM/bikecrm-content-creation/interviews/`. The format is
recurring: a still camera (DJI Osmo Pocket, 4K HEVC, ~11 GB per 20 min),
two people seated in the workshop, the product person in the product's
t-shirt. Unlike the four made kinds, the words and faces are real, so the
truth rule is **cut, never rewrite**: an edit may remove, it may not make
anyone say something they did not say, or reorder answers so that they
answer a different question.

The pipeline, in order. Each step leaves a committed file in the
interview's folder, so the next session can pick up where this one stopped.
**The step-by-step operating manual (commands, inputs, outputs, times,
costs, traps) is the content repo's `docs/interview-workflow.md`**
(BikeCRM: `~/git/BikeCRM/bikecrm-content-creation/docs/interview-workflow.md`);
this section keeps the rules and the lessons.

1. **File it.** Intake (Oriol, 2026-09-27): the camera file lands in
   `~/inbox/`, one file per interview, and Oriol says the shop and town;
   move it (don't copy) into `raw/`, sha256 it, and record the backup
   location. One folder per interview, `interviews/YYYY-MM-DD-<shop>-<town>/`,
   with the footage in the git-ignored `raw/` and a README: who is on screen
   (name, side, role), where, the date, the raw file with its sha256, where
   the backup copy is, the language, and the **consent**: who agreed, when,
   and for which uses. `make probe` / `make sheet` for the facts.
2. **Detect the language, don't ask.** Cut three 40 s samples (at ~10 %,
   45 % and 80 % of the running time) and run `whisper-cli -l auto` on each:
   Sprint Bike came back `es` on all three (p = 0.79–0.88). An interview can
   switch language partway, so one sample is not enough.
3. **Transcribe everything first, twice, and have two LLMs review it.**
   Every later decision is made on the transcript's timecodes, so it
   comes before any cut. Quality first (Oriol, 2026-09-27), in this order:
   - **Pass 1, no prompt**: `make transcribe I=… NAME=pass1 PROMPT=0`,
     whisper.cpp **`large-v3-turbo`** (`~/llm_models/`, the model ansible
     puts on every host; Oriol's choice for both passes: ~105 s for 20
     min on the Radeon 780M, vs ~300 s for full large-v3) → 16 kHz mono wav
     in `work/`, then srt/vtt/txt/json in `transcript/pass1.*` (committed,
     never edited).
   - **Review pass 1** (`make review-transcript I=… INPUT=pass1`): two models from two
     labs (default `openai/gpt-6-sol` + `anthropic/claude-opus-5.5`, the
     `llm-bench` panel) each correct it on their own (mishearings, names,
     punctuation, hallucinations, speaker turns, editor notes); then, for
     every segment where they differ in words or speaker, each sees the
     other's version and argument and answers, up to two rounds. Agreed
     text becomes the run's `transcript.md`; what stays disputed is
     marked ⚠ and listed in `report.md`. The run also writes
     `glossary-candidates.md`: every word the reviewers agreed to change.
   - **Feed the glossary**: product and trade terms from the candidates go
     into `shared/glossary.<lang>.md` (its "Whisper prompt" block when
     Whisper keeps missing them; everyday slips like "Fíticamente" →
     "éticamente" go into its reviewer-only list), proper nouns into the
     interview README's "Proper nouns".
   - **Pass 2 with the prompt** (`make transcribe I=… NAME=pass2`): the glossary's
     Whisper prompt + the interview's proper nouns (whisper.cpp's
     `--prompt`, ~220 tokens max), then **review pass 2 the same way with
     `PROMOTE=1`**: its transcript becomes `transcript/transcript.md`, the
     one every later step reads.
   Findings from Sprint Bike (2026-09-27), same reviewers on both passes:
   pass 1 (no prompt) 61 disputes → 40 after discussion, $0.94; pass 2
   (prompt) 23 → **1**, $0.57. The prompt fixes some names ("Sprint
   Bike" 2 of 3 vs 0) but not all ("San Feliu", "BicRM" persist), so the
   review is never optional, and the second pass is what makes the
   reviewers converge. A cheap pair (gpt-6-luna + gemini-3.8-flash, $0.10)
   was tried first; quality won (Oriol). Whisper does not tell speakers
   apart and text cannot settle who said a short "sí"/"vale" (the one
   dispute left). **WhisperX** (24k★: faster-whisper + word timestamps by
   forced alignment + pyannote diarization) is the fix and what
   word-by-word subtitles need. It lives in its own venv
   (`.venv-whisperx`, `uv pip install --torch-backend cpu whisperx`):
   its CTranslate2 engine has no AMD/ROCm support, so on the Radeon boxes
   it runs on CPU: 327 s for 20 min with turbo int8 plus alignment,
   word timestamps on every word, and names better than whisper.cpp with
   the same prompt ("Sprint Bike" 3/3, "BikeCRM" 2/2). Its diarization
   model (`pyannote/speaker-diarization-community-1`) is gated **per
   account**: a valid token still gets "not in the authorized list"
   until the owner accepts the model's terms on huggingface.co. The
   token is the shared read-only one (hq `huggingface.env`, all scopes),
   installed with `hf auth login` into `~/.cache/huggingface/token`.
   **Check the channels before any voice model.** The BikeCRM interviews
   are shot with two mics recorded one per channel (left = interviewer,
   right = interviewee): per-word L−R level (± 3 dB threshold) names the
   speaker for 95 % of the words and fixed every line the voice model
   got wrong. It costs nothing and needs no model; pyannote and the LLM
   judges are for the undecided ~5 % (crosstalk, overlaps) or a
   single-mic shoot. Mixing to mono (`-ac 1`) before transcription is
   what hid this on the first run. It also means the delivered audio
   needs a mix (as recorded, each person is in one ear).
   Measured on Sprint Bike: diarization adds ~690 s on CPU (1,070 s for
   the whole WhisperX run, 1.1× real time), and it is **not reliable on
   its own**: run on the mono mix, with two male voices and a workshop's
   echo, it gave several of the interviewer's longer questions to the
   interviewee (264 of 327 segments agree with the LLMs' speakers). The
   LLMs, conversely, miss short interjections. Both are now only the
   fallback: speakers come from the two mic channels (above), and the
   voice model and the LLM judges handle the ~5 % the channels leave
   unclear.
   **Bad audio** (noisy shop, wind, a weak mic): denoise the working
   audio with DeepFilterNet (4.8k★) before transcription and diarization,
   and measure it (review fix count with vs without). On Sprint Bike's
   delivered audio it was A/B-tested (+4 dB speech-to-noise); a blind
   headphone test decides whether it joins the chain. `oj-transcribe` (the fleet's memo tool, same whisper.cpp turbo)
   is not used here: it gives neither word timestamps nor speakers.
   Both reviewers independently found the real start and end, a phone
   call, a walk-in customer and a private third-party story: their
   editor notes are the first draft of the raw cut.
   PydanticAI trap: `claude-opus-5.5` rejects forced tool calls (400
   "tool_choice … not supported"), which is PydanticAI's default way to
   get structured output: use `NativeOutput(...)` (works on both).
4. **Mark the raw cut** in `edit.tsv` (committed; one row per removal:
   `in`, `out`, `category`, `note`):
   - `head` / `tail`: the camera rolls before the interview starts and
     after it ends (setup, "vale, pues empezamos", getting up). IN is the
     first settled frame before the first real line; OUT is just after
     the last answer. Confirm both on frames, not only on the transcript.
   - `flub`: false starts, stumbles, a sentence restarted: keep the
     clean take.
   - `retake`: a question asked again: keep the better question and the
     better answer, never half of each.
   - `no-answer` / `declined`: a question the interviewee could not
     answer or chose not to answer is removed entirely. A declined topic
     is gone from **every** cut, not just this one.
   - `chatter`: off-topic talk, interruptions (a customer, the phone),
     camera adjustments.
   - `private`: third parties named without their consent (clients,
     relatives, famous customers), other people's prices, anything
     the interviewee would not want public. Flag it and let Oriol decide.
   The LLM pass (a PydanticAI script, like every LLM step here, with the
   full glossary) reads a **phrase view** of the transcript, not the
   raw segments: one line per phrase with `[start–end]` and the speaker,
   a new line at every silence ≥ 0.5 s or speaker change (the
   `takes_packed.md` idea of browser-use/video-use, 27k★, the best
   agent editing skill found on 2026-09-27). Retakes show up as a
   repeated n-gram within ~30 s whose first copy ends abruptly: keep the
   last complete take. Cut points go in silences ≥ 0.4 s, never
   mid-word. Every row carries its reason, and Oriol reviews `edit.tsv`
   against the transcript before the raw cut is assembled. The **raw cut** is the full interview minus those rows: the
   How it runs now (`make settle-speakers`, then `make propose-cuts`, BikeCRM
   content repo, 2026-09-27):
   - **Speakers first, combined**: every segment where the reviewers'
     speaker and the diarized voice disagree goes to the two models with
     its context and the audio share; agreed → settled, split → one more
     round, then ⚠ for a person. Sprint Bike: 64 disagreements → 2, $0.44.
   - **The phrase view comes from WhisperX's word timestamps**, not from
     whisper.cpp segments: whisper.cpp's segment times drift by up to
     several seconds and the two engines segment differently, so they
     cannot be matched 1:1.
   - Both models propose removals as phrase ranges; overlapping proposals
     are agreed as their intersection (when in doubt, keep), a one-sided
     one goes to the other model to accept or reject. Sprint Bike: 6
     agreed (setup, phone call, walk-in customer, a declined and an
     unanswered question, the Contador/Iniesta story) + 1 contested
     (a sale with its price: sol cut, opus kept), $0.38, 20:16 → 16:21.
   - **Placement for a stream copy**: a removal's `in` (the kept part's
     end) can be anywhere; its `out` (the next kept part's start) is a
     keyframe, snapped inside the pause when one falls there, otherwise
     the row says how much removed speech stays or kept speech is lost.
     Adjacent or overlapping rows are joined at assembly.
   - **Phrase granularity is the limit at the edges**: the head's "vale,
     pues empezamos. Venga." and the tail's "Ay, no, estaba grabando" sat
     inside phrases (pauses under 0.5 s), so both models left them; the
     editor fixed them from word times. Improvement to make: also split
     phrases at sentence-final punctuation followed by ≥ 0.25 s.
   - The editor's own adjustments are marked `proposed_by: editor
     (Claude)` in `edit.tsv`, which carries a `decision` column for Oriol.

   master every later cut is taken from.
5. **Assemble the raw cut without re-encoding** (Oriol, 2026-09-27: every
   re-encode loses quality, and cutting does not need one). Stream-copy
   each kept segment from the original (`-ss <in> -i raw -t <len> -map 0:v:0
   -map 0:a:0 -c copy`; the DJI file also carries data tracks and an
   MJPEG thumbnail, so map only video and audio) and join them with the
   concat demuxer, still `-c copy`. A copy can only start on a keyframe,
   so **snap every `in`/`out` to a keyframe** and put the cut points in
   pauses, where half a second either way does not matter. The Osmo Pocket
   writes one keyframe every 1.001 s (30 frames), so a snap is never more
   than 0.5 s off. List them with `ffprobe -skip_frame nokey -show_entries
   frame=pts_time`. Cutting mid-word is the exception that needs pixels
   re-made: move the cut to a pause instead. Re-encoding happens **once**,
   at the end, and only for outputs whose pixels change (a crop, a
   punch-in, burned subtitles), always from the original, never from an
   export. Keep the source's 10-bit HEVC in the raw cut; a deliverable
   for the web is the H.264 encode from that step. On a still two-shot
   every cut is a jump cut. 4K footage delivered at 1080p leaves room for
   a punch-in on whoever speaks (a 2× crop) in the final encode, which
   hides it. **Check before handing over** (also from video-use): a frame
   at ±1.5 s around every cut, the output's `ffprobe` duration against the
   sum of the kept segments, a full decode with `ffmpeg -v error -i out -f
   null -` (a clean stream copy prints nothing), and a listen at each join.
   Frame-accurate "smart cut" (re-encoding only the GOP at a cut) exists
   (LosslessCut, `smartcut`) but is unreliable on HEVC (freezes, black
   frames at seams); keyframe snapping in pauses is the method.
   **Built (Sprint Bike, 2026-09-27, `make episode`)**: the stream-copy
   concat of scenes and camera footage works once the scenes are
   encoded to the camera's exact HEVC parameters (no B-frames) and every
   keyframe carries its parameter sets in-band, which forces the `hev1`
   tag (`hvc1` strips them; fine for YouTube, may fail on Apple players).
   Chapter starts are chosen by audio level on keyframes inside pauses;
   one without a keyframe in its pause re-encodes only up to the next.
   Loudness traps: measure on the **dual-mono** signal (mono measured and
   duplicated is ~3 LU too loud), and speech with peaks ~17 dB over its
   loudness makes loudnorm go dynamic: use one linear gain + a limiter.
6. **The long episode for YouTube** (Oriol, 2026-09-27): the main
   deliverable is a podcast-like long version of the raw cut, not only
   clips. Sections by topic, each opened by a short title card (the
   question, or the topic in a few words); an **animated product intro**
   (the brand wordmark scene of the feature-highlight kit, a few seconds,
   with the soundtrack engine's sting); the names and sides of the people
   on screen at their first appearance; an outro with the product URL.
   The same section list becomes the **YouTube chapters** in the
   description (first one at `00:00`, at least three, each ≥ 10 s, or
   YouTube ignores them), and the title, description and thumbnail are
   written in the interview's language from the transcript's own lines.
   To keep the interview itself un-re-encoded, render the intro and cards
   to **the raw cut's exact stream parameters** (resolution, frame rate,
   HEVC Main 10 `yuv420p10le`, BT.709, AAC 48 kHz stereo) and concat them
   `-c copy` between its segments; YouTube re-encodes the upload anyway,
   so what we send should be the best we have. (Not yet verified: that
   x265 cards and the DJI encoder's stream concat cleanly. Check the
   joins in a player and with `ffprobe` before relying on it; if they
   do not, fall back to one final encode of the whole episode at high
   quality.) Anything overlaid on the interview picture (a lower third,
   a punch-in) forces that re-encode, so prefer putting names and topics
   on the cards.
**Audio, before any deliverable** (Oriol, 2026-09-27): the two mics are
   L/R, so every file a person watches is **automixed** (the speaking
   mic up, the other −12 dB, never silent) into centred mono at −16 LUFS;
   a voice in one ear is "very distracting" on headphones. Only the
   audio is re-encoded; the video stays a stream copy. Measure the mics
   first (speech per person on their own mic, separation, noise floor,
   peaks, hum) and A/B the chain on one excerpt (automix alone,
   DeepFilterNet full / limited to 15 dB, + high-pass and gentle
   compression, other mic lower) before picking it: on Sprint Bike the
   workshop noise sat only ~23 dB under the speech, DeepFilterNet full
   gained ~4 dB of speech-to-noise, and compression lifted the noise
   back up.
   **Built (Sprint Bike, 2026-09-27, `make shorts`)** with Oriol's
   feedback: every short **opens on the interviewer's question**
   (verbatim, trimmed only at word boundaries), shown whole on a
   **question card** styled differently from the subtitles (no asker's name
   on it, Oriol); it ends with
   a 0.5 s fade to black into a **shared brand outro** rendered once and
   tracked in the repo (`shared/brand/`), never regenerated per clip.
   The crop follows the mic channels (frame side ≠ channel side: check
   `framing.json`), and a switch that looks wrong on the contact sheet
   is checked against the channels before "fixing" it.
7. **Vertical clips, framed on whoever speaks** (Oriol, 2026-09-27):
   selects of 30–60 s from the raw cut, one idea each, standing alone
   without the question (or with the question as a title card). The
   camera is still, so each person has **one fixed 9:16 crop box**,
   measured once on a frame of the 4K picture (a 1216×2160 window leaves
   room for a 1080×1920 output). The speaker turns in the clean
   transcript decide which box is on screen, switching at the turn
   boundaries (hold short interjections, a "sí" or a "vale", on the
   current speaker instead of cutting to them). **Subtitles are never
   the raw Whisper text**: an LLM review pass (PydanticAI, per the global
   rule, with the full glossary) corrects mishearings, names and punctuation against the
   glossary and the audio's context, keeping the segment timings and
   never changing what was said. It writes `transcript/subtitles.<lang>.srt`
   plus a diff against the raw text, which a person reads before burning
   anything. Style (Oriol, 2026-09-27): **word by word**, 2–4 words on
   screen with the spoken word highlighted in the brand colour, built
   from the word timestamps; burned in, placed in the vertical safe zone (see [Vertical](#vertical-reels--shorts--tiktok)),
   in the interview's language, with loudness-normalised audio. These
   clips change pixels, so they are the one encode, made from the
   original.
8. **The content plan** (built 2026-09-27: `make plan`, opus drafts, sol
   reviews, opus revises; the script checks the hooks verbatim and the
   ranges; opus left the publishing order empty twice, so a focused call
   fills it; Sprint Bike $0.52 for 10 chapters, 10 shorts, 11 weeks). All
   times are on the **raw cut's timeline** (`make raw-cut-transcript`).
   A **podcast export** is an idea on the list: audio-only episode opening
   with a cold open of the best questions and the start of each answer,
   the key part beeped as a teaser. The content plan, `content-plan.md` in the interview folder
   (Oriol, 2026-09-27), written from the clean transcript once the
   selects exist. It is the editorial brief a person can approve in one
   read: the long episode (title, one-paragraph description, chapters) and
   one entry per short (working title, the hook line as said on camera,
   what it talks about in one sentence, speaker, source timecodes in the
   raw cut, length, caption and hashtags in the interview's language,
   platforms), then the **publishing order** with dates or a cadence and
   the reason for it (e.g. the strongest standalone short first, the
   episode once two or three shorts can point to it, shorts that answer
   the same question kept apart). Nothing in it is a claim the transcript
   does not contain. Platforms (Oriol, 2026-09-27): YouTube (the episode,
   and the verticals as Shorts), Instagram Reels, TikTok and LinkedIn;
   the plan says which pieces go where and adapts the caption to each.
**Thumbnails are a reproducible step** (Oriol, 2026-09-28: "be smart with
   thumbnails"): a spec per interview (frame time on the raw cut + three
   text lines from the plan or the transcript) rendered through a brand
   scene (`make thumbnails`). The editorial part comes first and is done
   by eye: contact sheets of the plan's moment, then full-resolution
   candidates; pick the most expressive sharp face with the object the
   plan names. Real person, real words, brand type; check the render
   (word wraps, a gradient over the face).
   **Publishing through Postiz** (first run: BikeCRM, 2026-09-27). Load the
   **`postiz` skill** first (`~/.agents/skills/postiz/SKILL.md`, linked into
   `~/.claude/skills/` and `~/.claude-enacast/skills/`; Postiz's official
   skill + `postiz` CLI): it owns the CLI mechanics and its four hard
   rules (authenticate; every media file through `postiz upload`; TikTok
   `DIRECT_POST`; read `integrations:settings <id>` first because
   inapplicable settings are silently dropped). Account facts, keys and
   the MCP endpoint are in hq `shared/docs/postiz-cloud.md` (**one Postiz
   Cloud account per company**; the multi-company "customer groups" were
   not available in the UI). What we learned:
   - The account key works both in the MCP URL and as `POSTIZ_API_KEY`
     for the CLI; a stored `postiz auth:login` in `~/.postiz/` **overrides
     the env key**, so check `postiz auth:status` (it prints the
     organization) before acting when several companies exist.
   - `npx -y postiz@<version>` needs no global install; in zsh never keep
     the command in a variable (`$P args` does not split → nothing runs).
   - Channel settings seen: Instagram requires `post_type` (`post`; a
     single video posts as a **Reel**: Postiz sends `media_type=REELS`,
     verified in its `instagram.provider.ts` 2026-09-28; `VIDEO` is only
     for carousels; Reels need 9:16, 5–90 s), caption ≤ 2,200; YouTube requires `title`
     (≤ 100) and `type` (`public`/`private`/`unlisted`), plus
     `selfDeclaredMadeForKids`, `tags`, description ≤ 5,000. Instagram
     videos ≤ 100 MB (our shorts are 44–70 MB).
   - JSON mode (`posts:create --json`) with one `posts[]` entry per
     channel, the uploaded media `{id, path}`, and `settings.__type`;
     answers `[{postId, integration}]`, and `posts:list` then shows each
     as `QUEUE` at the UTC date.
   - Repeatable in the content repo: `scripts/schedule_postiz.py`
     (`make schedule`): the plan's weeks → Mondays at a Madrid time,
     one upload per short, one post per short across connected channels
     (TikTok/LinkedIn skipped until connected), and **a copy of
     everything kept in the repo** (Oriol: the schedule in
     `publish/schedule.md|json`, the exact payload + Postiz's answer per
     post in `publish/posts/`, and the register `publications.tsv`, one row
     per piece × platform). Create one post first and check it with
     `posts:list` before the batch; `--dry-run` shows the schedule.
   - `postiz upload` refuses files over **2 GiB**, so only the shorts go
     through Postiz; the long episode is uploaded by Oriol in YouTube
     Studio (full-quality master, no re-encode), with the generated
     `youtube-description.md`. A delivery encode under 2 GiB is the
     fallback if it ever must go through Postiz.
   - **A pacing monitor per product account** keeps the queue from
     silently running dry: a Cloudflare Worker with a daily cron reads
     Postiz's public API (`/public/v1/posts`, `Authorization: <key>`;
     posts carry `state` and `releaseURL`) and alerts by Pushover + email
     when nothing is queued in 14 days, the queue ends within them, or a
     post failed (BikeCRM: `monitors/postiz-queue/`, hq growth/pacing.md).
     Fetch far enough ahead (180 days) or "runs out on" is wrong.
   - Postiz's API can answer **502** mid-batch (it did on the 3rd of 10):
     before retrying a `posts:create`, list the posts at that date and
     channel, since a failed call may still have created them.
9. **Show Oriol** (contact sheet, then the render via the
   `whatsapp-waha` skill as a document) and publish only with his go plus
   the recorded consent covering that use.

**The LLM steps are meant to get better with every interview** (Oriol,
2026-09-27: that is the point of a PydanticAI script over an agent doing
it by hand). So: the prompts and output schemas live in the content repo
(`shared/prompts/`), versioned; each interview keeps what the LLM
proposed next to what the human finally accepted (the subtitle diff, the
reviewed `edit.tsv`), and those pairs are the eval set. A prompt or model
change is measured on the past interviews with the `llm-bench` skill
before it replaces the current one, and the traces go to Langfuse with
the product as `user_id`.

**Every step leaves a sidecar and a cost line** (Oriol, 2026-09-27):
a metadata JSON next to its output (`raw-whisper.meta.json`,
`review/<run>/run.json`: inputs and prompts with sha256, models and
parameters, host, timing, code commit, tokens and cost per stage), and
one line per model in the interview's `ai-costs.jsonl`; `make costs`
sums them per interview and step. A local model logs $0 so the ledger
is complete; a run whose cost was lost logs `null` with a note rather
than a guess. The content repo's README keeps a **Measured speeds**
table (step, engine, wall time, × real time, and the machine's specs),
filled from the sidecars' `wall_seconds`, so a machine change has a
baseline (Oriol, 2026-09-27).

**It is a repeatable workflow** (Oriol does many of these interviews):
every step is a `make` target in the content repo taking `I=<interview>`,
and anything learned on one interview goes into the shared glossary, the
scripts or this section, not only into that interview's folder.

Steps 1–4 were first run on Sprint Bike on 2026-09-27; 5–9 are the plan.
Correct this section as they are carried out.

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
- **Phone variants.** A 1200 px card shown at 360–390 px shrinks its text to
  ~30 %, unreadable. Ship a phone variant (600–720 px wide, via `<picture>`
  or `srcset`) with one alt text true for both; if one card is shown
  full-width on phones instead, design its text at ~34–40 px at 1x.
- **Take labels from the screen the flow really opens**: the page a
  WhatsApp or email link lands on, not a related app screen (FichaChat drew
  the portal first and had to redo it).
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
  node_modules has playwright or playwright-core>`, `--fonts "Lexend,Roboto,Material Icons"`,
  `--icon-font "Material Icons"`, `--query lang=ca` or `--lang ca`, `--min-text 20`). It writes each WebP at its exact size, a 2x PNG, and one
  `contact-sheet.png` of every scene over white, and it checks automatically:
  every listed font family has a loaded face (a missing one means a fallback
  font, the Times trap), no text overflows its box, and which text is smaller
  than the minimum (a decision, not always an error: a phone's clock is small
  on purpose). It fails the run when the icon font is missing (icons would
  render as ligature text like "CHEVRON_RIGHT") and warns when a card's box
  shadow reaches the stage edge (a clipped shadow shows as a hard
  rectangle: keep cards and shadows inside the stage). The HTML contract:
  one scene per `?s=<name>` inside `#stage`, and a `window.ready` promise
  that resolves after fonts and images load. It loads the page with `goto`
  on `file://`: `setContent` cannot load `file://` fonts. Subset icon fonts
  to the glyphs used (Material Symbols 3.9 MB → 18 KB).
- **Look at the contact sheet** before shipping: wrapped labels, empty card
  bottoms and collisions only show up there. Then check the images in the real
  page at desktop and phone width: an image displayed at 60 % of its size
  shrinks its text too (20 px becomes 12 px), so the phone view decides whether
  the text is still readable.
- **Report honestly:** say what the script checked, what you looked at, and
  what nobody has checked yet.
- **Per language:** the labels are text, so each language gets its own
  render, and every label is localised (reason texts and score captions
  too). Keep the original language as the markup and apply a strings table
  only for the others, so the original render stays byte-identical; select
  with `?s=<scene>-<lang>` or `--query lang=<l>`. Re-measure pointer click
  positions per language (text widths change) and set caption line breaks
  per format per language. **Before publishing, check each language's
  output differs from the others**: a shell `echo "-$L"` bug once
  re-encoded the Spanish video as English with no error.

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

- **BikeCRM content repo** (`~/git/BikeCRM/bikecrm-content-creation`): everything outside
  the site — customer interviews (`docs/interview-workflow.md`), feature videos, compilations,
  channel messages and scheduling (`docs/feature-video-workflow.md`), the publication register
  `publications.tsv`, the pacing monitor (`monitors/postiz-queue/`), the shared kit (`shared/`:
  feature-video renderer and build, brand outro/question card/thumbnail scenes, episode stings,
  Lexend). September 2026: Sprint Bike interview (episode + 10 shorts) and V1–V5 + compilation,
  all scheduled in Postiz (BikeCRM's account; hq `shared/docs/postiz-cloud.md`).
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
  `ramen.localhost:3203`, which **talks to production** (`make start`; for
  recordings that write, use the LOCAL stack instead: ramen with
  `ENACAST_API_URL=http://enacast.localhost:8201` and astro dev with its
  `.env.local`, test radio `radiotest.localhost`): capture as the
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
  **Feature video "Seccions habituals" (ca, 2026-09-27)**, made before the
  feature was deployed: **concept cards in HTML** (no captures), every label
  copied from the catalogs (ramen `messages/ca.json` `regularSections.*`,
  astro `translations.ts` `regularSections.*`) with invented data (program
  "Els matins", Albert Puig), so it could be shot from uncommitted code. It
  first reused the Insights video's cut points (22.5 s) and soundtrack
  generator, since moved into the repo's shared engine (below), so a new
  feature video is one scene file plus an events block. Cursor targets are
  measured from the untransformed layout at `window.ready`
  (`getBoundingClientRect` of the real buttons); hardcoded guesses missed the
  buttons by 100+ px. Delivered to Oriol on WhatsApp (whatsapp-waha skill:
  an mp4 goes as a document, `sendVideo` needs the chrome image).
  v1 (22.5 s) was judged too fast; **v2 (39.5 s, sent 2026-09-27, not
  published) was re-cut with a time map, not re-animated**: the scene stays
  authored in v1 time and the video's `timing.js` defines each cut as
  `holds` (`[v1 time, seconds frozen]`) and `slows` (`[v1 from, v1 to,
  factor]`); the page reads it (`?cut=v2`) and `soundtrack.py` reads the SAME
  file to move its events and cut points, so picture and sound stay in sync.
  Keep holds in multiples of the beat (0.5 s there) so every cut stays on the
  beat. `video.conf` lists `CUTS="v2 v1"` (first = default) with per-cut
  `DUR_<cut>`, `POSTER_T_<cut>`, `STILLS_<cut>`; build one with
  `make video V=… L=ca C=v2`, renders named `<slug>-<lang>-<cut>-WxH.mp4`.
  **EnaCast feature videos live in `~/git/EnaCast/enacast-content-creation`**
  (Oriol, 2026-09-27), not in the site repo: one `videos/YYYY-MM-DD-<name>/`
  per video (`scene-<lang>.html`, `soundtrack.py`, `video.conf`, `copy/`,
  README with story + status), a shared renderer/build script and the
  soundtrack engine `shared/audio/synth.py` (`Track(dur, cuts).bed()` + the
  video's events + `.transitions().write()`); `make check V=…` renders the
  stills and a contact sheet, `make video V=… L=ca [C=<cut>]` the mp4. Renders stay in
  the video's git-ignored `renders/` (mp4s move to a NAS later). Only videos
  embedded on the commercial site keep their sources in its `content-sources/`.
