# Subreddit research — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need an **extensive, structured list of subreddits** where this product could (a) advertise via Reddit Ads, (b) participate organically without being spammy, or (c) launch via founder posts. For each subreddit I want:

- `/r/name` (clickable URL)
- approximate subscriber count (verify via web search — Reddit hid public sub counts in 2026, use third-party trackers like subredditstats / GummySearch and mark estimates with "verify")
- which product surface fits — use exactly the surface names from the product context above
- the kind of post or ad angle that would land
- self-promo rules / red flags (e.g. "no self promo" in sidebar, AutoMod karma gates, "one promo per 60 days")

**Group by category**, choose categories that fit the product (typical categories below — drop any that don't apply, add ones that do):

- Direct creator / professional communities (where the ICP lives)
- Listener / consumer fan communities (for case-study amplification, not direct B2B ads)
- Adjacent vertical communities (one step away from the ICP)
- Audio / engineering / technical communities
- Indie SaaS / founder / startup marketing communities (for thought leadership)
- Hyperlocal / municipal / regional communities (for local-buyer products)
- Language-specific communities ({{LANGUAGES}})
- Marquee-customer fan subreddits (testimonials, not ads) — if the product has well-known customers

Target **50+ subreddits total** across categories. Be specific. For each entry, where you can find the actual subscriber count and whether the sub allows ads, do so. Where you can't, mark as "verify before posting."

**Output format — return both of these together in your final message, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Sections per category, each with a table:

```
| Subreddit | Approx. subs | Fit | Angle | Self-promo / red flags |
```

End with a "Cross-cutting notes" section (e.g. Reddit Ads targeting tips, posting-runway recommendations, karma gates) and a "Sources" section with the URLs you actually relied on.

### 2. A JSON array matching this schema

```json
[
  {
    "category": "A. <category name>",
    "subreddit": "r/<name>",
    "url": "https://reddit.com/r/<name>",
    "approx_subs": "<e.g. ~200K or 'verify'>",
    "fit": "<one of the product surfaces, or 'Both', or 'Adjacent'>",
    "geography": "<US|UK|EU|ES|FR|DE|Global|...>",
    "angle": "<one-line angle for posts/ads>",
    "self_promo_flags": "<red flags / sidebar rules / karma gates>"
  }
]
```

The JSON must include **every row from the markdown tables**, with matching values. Don't skip any.

**JSON formatting**: Use literal `&`, `<`, `>` characters inside JSON string values. Do NOT use HTML entities like `&amp;`, `&lt;`, `&gt;` — JSON has no HTML escapes, so those would appear verbatim in downstream spreadsheets. The JSON block must be valid `json.loads()`-parsable, with the intended characters appearing as-is.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. No filler. Roughly 1500–2500 words of markdown is fine; the JSON should be as long as it needs to be to cover every entry.
