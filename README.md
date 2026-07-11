# LLM_SKILLS

Personal collection of Claude Code skills and slash commands.

## Layout

```
skills/      # Skills — auto-loaded when their description matches the user's request
commands/    # Slash commands — invoked explicitly with /<name>
```

## Contents

### Skills

- **[seo](skills/seo/SKILL.md)** — Ship and audit SEO on any kind of site (SaaS landing pages, e-commerce, news, podcasts, blogs, docs). Covers classic SEO (canonical URLs, robots.txt, sitemap.xml, Open Graph, JSON-LD), AI search / GEO (AI crawler policy, llms.txt), RSS / Podcasting 2.0, Core Web Vitals, hreflang, and multitenant canonical-host redirects. Reference docs live in [`skills/seo/references/`](skills/seo/references/).
- **[growth-research](skills/growth-research/SKILL.md)** — Build a complete go-to-market research deck for any product (SaaS, indie tool, media business, agency). Spawns up to **eight parallel research agents** covering the four base slices (subreddits, magazines / newsletters / PR, conferences and trade shows, partner / channel / competitor ecosystem) and four situational ones (influencers / KOLs, deep competitor intelligence tear-downs, regulatory tailwinds and deadlines, and a pricing & packaging strategy report). Produces a standardised repo: markdown source-of-truth, JSON sidecars, sortable xlsx mirrors, an **interactive HTML explorer** with filters and Chart.js graphs, and a top-level prioritised playbook (`GROWTH_RESEARCH.md`). Reference docs and templates live in [`skills/growth-research/references/`](skills/growth-research/references/).
- **[find-leads](skills/find-leads/SKILL.md)** — Find business leads for any market/industry and export to XLSX. Use when the user wants to build a database of businesses, find leads, or scrape directories for a specific market. Ships with `scraper_template.py` and `xlsx_template.py` for the agent to adapt.
- **[core-web-vitals](skills/core-web-vitals/SKILL.md)** — Measure and fix Core Web Vitals (LCP, CLS, INP/TBT) on any web project: headless Lighthouse CLI recipes (desktop + throttled mobile), CrUX field data via the PSI API, how to read the report JSON (LCP breakdown/discovery insights, layout-shift culprits, heavy resources), per-metric fix playbooks (hero image priority, CMS-image CDN rewriting + lazy-loading, reserved space for CLS, lazy-importing libraries for TBT), and field-tested gotchas (lab numbers are Lantern-simulated, LCP can't beat FCP, verify deploys before re-measuring, stale service workers).
- **[pwa](skills/pwa/SKILL.md)** — Ship and audit Progressive Web Apps: installability, manifest, service worker, offline support, push notifications, update flow. Covers Vite + React, Next.js, Astro, SvelteKit, Remix, plain HTML; cache strategies, install prompt UX, iOS Safari quirks, hosting headers, Lighthouse PWA audit.
- **[pydantic-ai-langfuse](skills/pydantic-ai-langfuse/SKILL.md)** — Implement LLM features in Python with PydanticAI + Langfuse observability: agent/prompt builder patterns, PydanticAI 2.x breaking changes (`google:` provider rename, `Agent.instrument_all()`), OTel→Langfuse init that no-ops without keys, `@observe` capture rules (Django ORM OOM trap), TestModel/FunctionModel testing with `ALLOW_MODEL_REQUESTS=False`, rate-limit-safe batch scoring, user-steerable judge prompts, and SPA-aware website fetching for LLM input.
- **[celery-deploy-safety](skills/celery-deploy-safety/SKILL.md)** — Audit and fix a Django + Celery + Redis project so deploys, restarts, and crashes never silently lose background work: acks_late at-least-once delivery, Redis AOF persistence, orphan-resume sweeps, dispatch dedupe locks, worker memory bounds, stop_grace_period, and how to verify the whole chain.

### Commands

- **[/qa-report](commands/qa-report.md)** — Generate a QA testing report from recent git changes on the current branch. Categorizes new features, breaking changes, and produces a prioritized testing checklist written to `qa/YYYY-MM-DD-<short_description>.md`.

## Installing

These files live in this repo as the source of truth. To make them available to Claude Code, symlink them into `~/.claude/`:

```fish
ln -s (pwd)/skills/seo               ~/.claude/skills/seo
ln -s (pwd)/skills/growth-research   ~/.claude/skills/growth-research
ln -s (pwd)/skills/find-leads        ~/.claude/skills/find-leads
ln -s (pwd)/skills/core-web-vitals   ~/.claude/skills/core-web-vitals
ln -s (pwd)/skills/pwa               ~/.claude/skills/pwa
ln -s (pwd)/skills/celery-deploy-safety ~/.claude/skills/celery-deploy-safety
ln -s (pwd)/commands/qa-report.md    ~/.claude/commands/qa-report.md
```

(Or copy them if you'd rather not symlink.)
