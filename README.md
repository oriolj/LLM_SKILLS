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
- **[growth-research](skills/growth-research/SKILL.md)** — Build a complete go-to-market research deck for any product (SaaS, indie tool, media business, agency). Spawns four parallel research agents covering subreddits, magazines / newsletters / PR, conferences and trade shows, and partner / channel / competitor ecosystem. Produces a standardised repo with markdown source-of-truth, JSON sidecars, sortable xlsx mirrors, and a top-level prioritised playbook. Reference docs and templates live in [`skills/growth-research/references/`](skills/growth-research/references/).
- **[find-leads](skills/find-leads/SKILL.md)** — Find business leads for any market/industry and export to XLSX. Use when the user wants to build a database of businesses, find leads, or scrape directories for a specific market. Ships with `scraper_template.py` and `xlsx_template.py` for the agent to adapt.

### Commands

- **[/qa-report](commands/qa-report.md)** — Generate a QA testing report from recent git changes on the current branch. Categorizes new features, breaking changes, and produces a prioritized testing checklist written to `qa/YYYY-MM-DD-<short_description>.md`.

## Installing

These files live in this repo as the source of truth. To make them available to Claude Code, symlink them into `~/.claude/`:

```fish
ln -s (pwd)/skills/seo               ~/.claude/skills/seo
ln -s (pwd)/skills/growth-research   ~/.claude/skills/growth-research
ln -s (pwd)/skills/find-leads        ~/.claude/skills/find-leads
ln -s (pwd)/commands/qa-report.md    ~/.claude/commands/qa-report.md
```

(Or copy them if you'd rather not symlink.)
