# AI crawler policy

The trickiest decision in robots.txt is what to do with AI-adjacent bots.
Load this file when the user asks about GPTBot / ClaudeBot / PerplexityBot
policy, wants to block training vs retrieval, or is auditing the AI side
of their robots.txt.

## Three roles a bot can play

- **Training** — bulk-downloads content to build model weights. Content
  gets baked in but you never see a referral. Examples: `GPTBot`
  (OpenAI), `ClaudeBot` (Anthropic), `Google-Extended` (Google), `CCBot`
  (Common Crawl feeds many training pipelines).
- **Retrieval** — fetches a page in real time to answer a live user
  question, with a citation that links back. Drives traffic. Examples:
  `OAI-SearchBot`, `ChatGPT-User`, `Claude-SearchBot`, `Claude-User`,
  `PerplexityBot`, `Perplexity-User`.
- **Classic search** — the original crawler that feeds traditional
  search results. Always allow unless the site is truly private.
  Examples: `Googlebot`, `Bingbot`.

## User-agent reference (current as of early 2026)

| User-Agent | Operator | Role | Notes |
|------------|----------|------|-------|
| `GPTBot` | OpenAI | Training | Used to collect content for GPT model training |
| `OAI-SearchBot` | OpenAI | Retrieval | Used by ChatGPT search features (citation layer) |
| `ChatGPT-User` | OpenAI | Retrieval | Fires when a user clicks "browse" in a chat |
| `ClaudeBot` | Anthropic | Training | Used for Claude model training |
| `Claude-SearchBot` | Anthropic | Retrieval | Used by Claude search/web features |
| `Claude-User` | Anthropic | Retrieval | Fires on user-invoked browsing |
| `Google-Extended` | Google | Training | Gemini/Vertex training opt-out only; does NOT affect indexing or AI Overviews |
| `Googlebot` | Google | Classic search | Always allow. Also feeds AI Overviews; blocking it blocks AI Overview citations too |
| `Googlebot-Image`, `Googlebot-Video` | Google | Classic search | Image/video verticals |
| `Bingbot` | Microsoft | Classic search | Always allow; also feeds Copilot |
| `PerplexityBot` | Perplexity | Retrieval | Indexes sources for Perplexity answers |
| `Perplexity-User` | Perplexity | Retrieval | Fires on user-invoked search |
| `Meta-ExternalAgent` | Meta | Training | Trains Meta AI / Llama |
| `Meta-ExternalFetcher` | Meta | Retrieval | User-invoked (Meta AI assistant) |
| `Amazonbot` | Amazon | Retrieval / Alexa | Powers Alexa answers + product research |
| `Applebot` | Apple | Classic search | Siri, Spotlight, Safari suggestions — always allow |
| `Applebot-Extended` | Apple | Training | Apple Intelligence model-training opt-out |
| `CCBot` | Common Crawl | Training-ish | Public dataset used by many model trainers |
| `Bytespider` | ByteDance | Aggressive scraper | Block |
| `Diffbot` | Diffbot | Scraping-as-a-service | Block unless paying |
| `DataForSeoBot` | DataForSEO | SEO analytics scraper | Block |
| `PetalBot` | Huawei | Classic + AI | Low Western referral volume; usually block |

### Crawl volume

Per early-2026 Cloudflare data: Googlebot still leads, but
ClaudeBot ≈ GPTBot are in the same order of magnitude, followed by
Meta-ExternalAgent > Bingbot > PerplexityBot. Before picking a tier,
grep your own access logs — real volume varies wildly by vertical.

### JS rendering: most AI crawlers don't

Unlike Googlebot (which runs a headless Chromium over two passes),
GPTBot, ClaudeBot, PerplexityBot, and Meta-ExternalAgent generally
fetch raw HTML and extract the text they find. If primary content is
client-side-rendered, you are invisible to AI search regardless of
robots.txt policy. Server-rendering (or SSG) is the prerequisite.

## Three typical policies — pick one

### Publisher (want AI citations) — default for content sites

```
User-agent: *
Allow: /
```

That's it. Training crawlers, retrieval crawlers, and classic search
all fall under the default allow. You appear in AI answers AND in model
weights. Best for: news sites, podcasts, blogs, public documentation,
marketing sites.

### Content-protective (appear in AI answers but not in training)

```
User-agent: GPTBot
Disallow: /
User-agent: ClaudeBot
Disallow: /
User-agent: Google-Extended
Disallow: /
User-agent: Meta-ExternalAgent
Disallow: /
User-agent: Applebot-Extended
Disallow: /
User-agent: CCBot
Disallow: /

User-agent: *
Allow: /
```

Retrieval bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot,
Meta-ExternalFetcher, Amazonbot, Applebot) aren't listed, so they fall
under `User-agent: *` and continue to crawl. Classic search
(Googlebot, Bingbot) is unaffected. Best for: original reporting, paid
research, creative work where you want citation traffic but not
uncompensated training exposure.

**Not foolproof.** robots.txt is an honor system; training crawlers
operated by third parties (web-scraping-as-a-service companies, open
Common Crawl rehosters) ignore it. If training exposure is a legal or
commercial risk (paywalled research, editorial IP), layer the policy
with UA-based WAF blocks at the CDN — Cloudflare AI Scrapers ruleset,
Fastly, or the equivalent.

### Closed (index in classic search only)

```
User-agent: Googlebot
Allow: /
User-agent: Bingbot
Allow: /

User-agent: *
Disallow: /
```

Nothing gets AI treatment. Classic search still works. Best for:
private SaaS dashboards, staging environments, anything that shouldn't
show up in AI answers or model training.

## Decision questions

1. **Does your site benefit from being quoted in AI summaries with a
   link back?** Yes → at least Publisher or Content-protective.
2. **Is the content expensive to produce and uncompensated training
   meaningfully hurts you?** Yes → Content-protective.
3. **Do the search-engine traffic benefits matter at all?** No → Closed.

## Always block (regardless of policy)

Low-signal scrapers that consume bandwidth without driving traffic
back. Include these in every policy:

```
User-agent: Bytespider
Disallow: /
User-agent: Diffbot
Disallow: /
User-agent: DataForSeoBot
Disallow: /
User-agent: PetalBot
Disallow: /
```

`CCBot` belongs in this list under Publisher tier too if you don't want
the content in public datasets — judgment call.

## Per-tenant policy

If one tenant of a multitenant SaaS needs stricter rules (e.g. a
research-report product), branch the SSR robots route on a
`robots_policy` field of the tenant model:

```ts
const policy = tenant.robots_policy ?? 'publisher';
if (policy === 'content-protective') { emitTrainingBlocks(lines); }
if (policy === 'closed') { emitClosedPolicy(lines); return; }
emitDefaultAllow(lines);
```
