# GEO / AEO — getting cited by AI search engines

Load this when the user mentions AI Overviews, GEO (Generative Engine
Optimization), AEO (Answer Engine Optimization), "getting cited by
ChatGPT / Claude / Perplexity", or wants to evaluate why their content
isn't showing up in AI answers.

GEO = classic SEO with sharper focus on content structure and factual
verifiability. A page that wins AI citations had to be indexable,
E-E-A-T-strong, and semantically clean first. It's a layer on top of
SEO, not a replacement.

## Prerequisites (confirm these before GEO-specific moves)

1. **Server-rendered content.** Most AI crawlers don't run JS; CSR is
   invisible to them. See `ai-crawler-policy.md`.
2. **AI crawlers aren't blocked.** Check `robots.txt` and CDN rules —
   Cloudflare's "Block AI bots" toggle blocks retrieval bots too,
   which removes you from citation pools. Default = publisher tier.
3. **No paywalls / login walls** on content you want cited.
4. **Strong E-E-A-T.** Named `Person` authors with `sameAs`,
   `NewsMediaOrganization` on news sites, real policy pages,
   verifiable company info. E-E-A-T is the heaviest single lever in
   current AI Overview citation patterns.

## Content structure that gets cited

### Direct answers up front

Put the direct answer in the first paragraph after the `<h1>`.
Elaborate below. AI engines excerpt short passages (typically a few
paragraphs); if the answer isn't near the top, they skip you for a
competitor that leads with it.

### Question-shaped subheads

`<h2>` and `<h3>` phrased as the natural question form get matched
when users ask the same thing. "How do I reset my password?" beats
"Password Reset Process".

### Structured facts, not prose blobs

Claims with specific numbers, dates, or named sources are far more
citation-eligible than vague paragraphs. "Response time improved 42%"
> "response time improved significantly". Original data + named
customers / subjects is the highest-correlation signal.

### Semantic density

Name the relevant entities explicitly — products, concepts,
regulations, people. For a post about payroll software: "ACA", "W-2",
"Gusto", "Section 125 plan". Breadth of named entities matters more
than keyword repetition.

### Freshness

AI engines weight recency. A 2024-stamped guide loses to a 2026 guide
on the same topic. Practical rules:

- Put the year in titles where it's honest ("2026 guide to…") when
  the content is genuinely updated annually.
- Visible "Last updated: <date>" line near the top of evergreen posts.
- `dateModified` on the `Article` schema — but only when content
  actually changed. Faking it (bumping date without changes) gets
  detected.

### Semantic completeness

Fully answer the question in one page. Splitting "what is X" across
five posts that each tease the next isn't GEO-friendly — AI engines
prefer a single source that covers the entire answer, with
well-organized subsections.

### Citation-friendly formatting

- Tables for comparative data (AI extracts these cleanly)
- Ordered lists for step-by-step
- Bulleted lists for criteria / features
- Short paragraphs (2-4 sentences)
- No image-of-text (AI OCR is unreliable and slow)

## Schema signals that matter for AI citation

Beyond ranking, these contribute to whether AI engines trust and cite:

- `Article.author` as a `Person` with `sameAs` linking to verifiable
  identities (LinkedIn, Google Scholar, Mastodon, X). AI engines
  cross-reference author credentials when deciding to cite.
- `Organization.sameAs` — official social / Crunchbase / Wikipedia.
- `Article.citation` — link to primary sources you reference. Models
  learn to prefer pages that themselves cite.
- `FAQPage` still works for ChatGPT/Perplexity ingestion even though
  Google deprecated the rich result. Cheap to emit on genuine Q&A
  content.
- Clean `BreadcrumbList` — helps the crawler understand where the
  page sits in site structure.

## Measuring AI citation (there's no GSC equivalent yet)

- **Brand-query tracking** — run your target queries in ChatGPT,
  Perplexity, Claude, and Gemini periodically. Note which sources
  they cite. Tools: AI Overview tracking in Ahrefs / Semrush, or
  manual spot-checks.
- **Server logs** — filter access logs for AI user-agents
  (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.). Rising crawl
  frequency is a leading indicator of citation volume.
- **Direct referrer traffic** from ChatGPT / Perplexity / Claude —
  these appear in analytics as referrals when users click citation
  links. Not large volume, but a quality-signal check.
- **Bing Webmaster Tools** exposes some AI-surface data (Copilot
  impressions) — set this up if you haven't.

## Anti-patterns

- **Over-optimized answer-box bait** — writing every page in TL;DR +
  bullet format strips the depth AI engines also reward. Lead with the
  answer, but keep the full coverage underneath.
- **AI-generated content without disclosure or editorial oversight.**
  Tagged AI-assisted content with visible review is fine; detected-
  at-scale AI spam gets demoted.
- **Buying mentions on low-quality listicle / review farms** — AI
  engines weigh source authority; spam-farm citations are net-neutral.

## Reality check

Classic SEO still drives most traffic — AI search is rising but Google
organic dwarfs it for most verticals. Being cited in AI answers is
brand exposure but the click-through can be lower (user got the answer
inline). The highest-ROI lever is almost always **original data**: one
experiment / dataset / interview per quarter that no competitor has
tends to drive more AI citations than a year of rewriting existing
posts.

## Quick playbook

When the user asks "help me rank in AI Overviews":

1. Confirm server rendering + AI crawler access (prerequisites).
2. Audit E-E-A-T: does every article have a named `Person` author
   with `sameAs`? Does the site have `NewsMediaOrganization` or
   equivalent?
3. Pick 5-10 target queries. For each, check what Perplexity and
   ChatGPT currently cite. Identify gaps where the user's content
   should compete.
4. For the top 2-3 pages competing on those queries, rewrite the
   lead to answer the question directly in the first 150 words.
   Add one piece of original / verifiable data per page.
5. Confirm `dateModified` is genuine and recent where applicable.
6. Ship. Re-check AI citations after 4-8 weeks; expect slow rollout.
