# LLM_SKILLS

Personal collection of Claude Code skills and slash commands.

## Layout

```
skills/      # Skills — auto-loaded when their description matches the user's request
commands/    # Slash commands — invoked explicitly with /<name>
```

## Contents

### Skills

- **[android](skills/android/SKILL.md)** — Build, test and verify native Android apps entirely from the CLI, no Android Studio: SDK/toolchain bootstrap (sdkmanager, Gradle wrapper without gradle installed), known-good AGP/Kotlin/Compose version sets, pure-Kotlin core modules for fast JVM tests, and the headless-emulator self-verification loop (KVM AVD + swiftshader, adb install/launch, logcat crash triage, screencap + input tap/swipe driving). Includes Compose gotchas and Maven Central artifact probing.
- **[seo](skills/seo/SKILL.md)** — Ship and audit SEO on any kind of site (SaaS landing pages, e-commerce, news, podcasts, blogs, docs). Covers classic SEO (canonical URLs, robots.txt, sitemap.xml, Open Graph, JSON-LD), AI search / GEO (AI crawler policy, llms.txt), RSS / Podcasting 2.0, Core Web Vitals, hreflang, and multitenant canonical-host redirects. Reference docs live in [`skills/seo/references/`](skills/seo/references/).
- **[growth-research](skills/growth-research/SKILL.md)** — Build a complete go-to-market research deck for any product (SaaS, indie tool, media business, agency). Spawns up to **eight parallel research agents** covering the four base slices (subreddits, magazines / newsletters / PR, conferences and trade shows, partner / channel / competitor ecosystem) and four situational ones (influencers / KOLs, deep competitor intelligence tear-downs, regulatory tailwinds and deadlines, and a pricing & packaging strategy report). Produces a standardised repo: markdown source-of-truth, JSON sidecars, sortable xlsx mirrors, an **interactive HTML explorer** with filters and Chart.js graphs, and a top-level prioritised playbook (`GROWTH_RESEARCH.md`). Reference docs and templates live in [`skills/growth-research/references/`](skills/growth-research/references/).
- **[find-leads](skills/find-leads/SKILL.md)** — Find business leads for any market/industry and export to XLSX. Use when the user wants to build a database of businesses, find leads, or scrape directories for a specific market. Ships with `scraper_template.py` and `xlsx_template.py` for the agent to adapt.
- **[core-web-vitals](skills/core-web-vitals/SKILL.md)** — Measure and fix Core Web Vitals (LCP, CLS, INP/TBT) on any web project: headless Lighthouse CLI recipes (desktop + throttled mobile), CrUX field data via the PSI API, how to read the report JSON (LCP breakdown/discovery insights, layout-shift culprits, heavy resources), per-metric fix playbooks (hero image priority, CMS-image CDN rewriting + lazy-loading, reserved space for CLS, lazy-importing libraries for TBT), and field-tested gotchas (lab numbers are Lantern-simulated, LCP can't beat FCP, verify deploys before re-measuring, stale service workers).
- **[pwa](skills/pwa/SKILL.md)** — Ship and audit Progressive Web Apps: installability, manifest, service worker, offline support, push notifications, update flow. Covers Vite + React, Next.js, Astro, SvelteKit, Remix, plain HTML; cache strategies, install prompt UX, iOS Safari quirks, hosting headers, Lighthouse PWA audit.
- **[pydantic-ai-langfuse](skills/pydantic-ai-langfuse/SKILL.md)** — Implement LLM features in Python with PydanticAI + Langfuse observability: agent/prompt builder patterns, PydanticAI 2.x breaking changes (`google:` provider rename, `Agent.instrument_all()`), OTel→Langfuse init that no-ops without keys, `@observe` capture rules (Django ORM OOM trap), TestModel/FunctionModel testing with `ALLOW_MODEL_REQUESTS=False`, rate-limit-safe batch scoring, user-steerable judge prompts, and SPA-aware website fetching for LLM input.
- **[eu-law](skills/eu-law/SKILL.md)** — EU + Spanish web-law compliance checklist for websites and SaaS: the four legal pages and when each is required (aviso legal LSSI-CE, privacidad GDPR/LOPDGDD, cookies ePrivacy, términos), cookie-banner decision tree (engineer for zero cookies and skip the banner), GDPR engineering checklist (deletion, portability, DPAs, international transfers), SaaS terms structure (B2B vs B2C, 14-day withdrawal), LSSI email-marketing rules, and AI Act transparency touchpoints. Not legal advice — launch-ready groundwork.
- **[sqlite-production](skills/sqlite-production/SKILL.md)** — Run SQLite safely in production: required pragmas (WAL, busy_timeout, synchronous=NORMAL), the db/-wal/-shm file trio, single-writer discipline with BEGIN IMMEDIATE, same-host multi-container sharing on Docker volumes, blue-green/rolling deploys on Coolify (additive-only migrations, health checks), Litestream/VACUUM INTO backups, and Go (modernc.org/sqlite) + Django 5.1+ connection setup.
- **[multitenancy-guardrails](skills/multitenancy-guardrails/SKILL.md)** — Design, review and test tenant isolation in row-level multi-tenant SaaS: core scoping rules (tenant from the server never the client, scope at the data-access layer, 404 not 403, UUIDs are not authorization), the leak-vector checklist (exports, files, stats, HTMX fragments, background jobs, emails, RAG retrieval, cache/rate-limit keys, storage paths, magic links, merge ops, widgets), enforcement patterns for Django, DRF (get_queryset + the related-field write leak), Go (pgx/sqlc guards, optional-scope param), and Postgres (per-tenant uniques, composite-FK integrity trick, tenant-leading indexes, RLS with FORCE), plus the mandatory two-tenant isolation test suite.
- **[celery-deploy-safety](skills/celery-deploy-safety/SKILL.md)** — Audit and fix a Django + Celery + Redis project so deploys, restarts, and crashes never silently lose background work: acks_late at-least-once delivery, Redis AOF persistence, orphan-resume sweeps, dispatch dedupe locks, worker memory bounds, stop_grace_period, and how to verify the whole chain.
- **[capacitor-ios](skills/capacitor-ios/SKILL.md)** — Compile, run, and distribute a Capacitor iOS app from the CLI: simulator builds, direct-to-device installs via devicectl, the TestFlight archive→upload lane (`xcodebuild` + `-allowProvisioningUpdates`, monotonic build numbers from `git rev-list --count`), App Store submission traps, and the field-tested signing failure playbook (WWDR intermediate, `errSecInternalComponent` keychain unlocks, device-registration for fresh teams). Encodes the disposable-`ios/` convention: durable config in idempotent scripts, signing passed at build time, never stored in the generated project.
- **[capacitor-android](skills/capacitor-android/SKILL.md)** — Compile and distribute a Capacitor Android app: debug-APK device-testing lane (JDK 21 / android-36 pins, dev-URL bundle sanity check, one-current-APK share convention), and the signed-release/Play lane (upload keystore + Play App Signing, `signingConfigs`/`versionCode` injected by script into the disposable `android/`, AAB uploads, SHA-1s for Google sign-in). Companion to the native-Android **android** skill above.
- **[api-idempotency](skills/api-idempotency/SKILL.md)** — Make unsafe API writes idempotent so retries, flaky connections, and offline-queue replays can't create duplicate rows: the client-generated idempotency-key pattern (Stripe-style), the mint-once-per-intent rule, DB unique constraints + IntegrityError race handling, transient-vs-permanent retry classification, and how to audit a codebase for the "infra exists but a path skips it" gap.

### Commands

- **[/qa-report](commands/qa-report.md)** — Generate a QA testing report from recent git changes on the current branch. Categorizes new features, breaking changes, and produces a prioritized testing checklist written to `qa/YYYY-MM-DD-<short_description>.md`.

## Installing

These files live in this repo as the source of truth. To make them available to Claude Code, symlink them into `~/.claude/`:

```fish
ln -s (pwd)/skills/android           ~/.claude/skills/android
ln -s (pwd)/skills/seo               ~/.claude/skills/seo
ln -s (pwd)/skills/growth-research   ~/.claude/skills/growth-research
ln -s (pwd)/skills/find-leads        ~/.claude/skills/find-leads
ln -s (pwd)/skills/core-web-vitals   ~/.claude/skills/core-web-vitals
ln -s (pwd)/skills/pwa               ~/.claude/skills/pwa
ln -s (pwd)/skills/celery-deploy-safety ~/.claude/skills/celery-deploy-safety
ln -s (pwd)/skills/api-idempotency      ~/.claude/skills/api-idempotency
ln -s (pwd)/skills/capacitor-ios        ~/.claude/skills/capacitor-ios
ln -s (pwd)/skills/capacitor-android    ~/.claude/skills/capacitor-android
ln -s (pwd)/skills/sqlite-production    ~/.claude/skills/sqlite-production
ln -s (pwd)/skills/pydantic-ai-langfuse ~/.claude/skills/pydantic-ai-langfuse
ln -s (pwd)/skills/eu-law               ~/.claude/skills/eu-law
ln -s (pwd)/commands/qa-report.md    ~/.claude/commands/qa-report.md
```

(Or copy them if you'd rather not symlink.)
