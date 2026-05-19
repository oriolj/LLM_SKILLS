# Competitor intelligence tear-down — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need a **competitor intelligence tear-down** for every direct and meaningful adjacent competitor in this vertical. Our other research lists competitors as part of the partner map; this slice goes *deep* on each one for use in positioning decks, competitive sales situations, and product roadmap calls.

Source priority for each competitor (use what's findable):

- Their **homepage + pricing page** (snapshot the public price model).
- Their **LinkedIn company page** (employee count, founding year, HQ).
- **Crunchbase / Pitchbook public data** (last funding round, total raised).
- Public **case studies** (notable named customers).
- **Press coverage** (last 12 months — wins, losses, layoffs, leadership changes).
- Their **changelog / release notes** if public.

For each competitor, capture:

- **name**
- **url**
- **founded_year** (or "verify" if uncertain)
- **hq_country**
- **employees_approx** — LinkedIn estimate; mark range (e.g. "11–50") or exact if findable.
- **revenue_or_funding** — best public estimate (e.g. "$5M ARR (estimated)", "Series A $12M Mar 2024", "Bootstrapped, undisclosed"). Be honest about uncertainty.
- **pricing_snapshot** — starting price + pricing model in one line (e.g. "From $99/mo, per-seat", "Custom, contact sales only").
- **key_features** — 3–5 most-emphasised product capabilities, comma-separated.
- **notable_customers** — 2–4 named customers from public sources.
- **strengths** — what they genuinely do well (be honest — competitive intel is worthless if it's biased).
- **weaknesses_to_exploit** — concrete gaps in their product, market position, pricing, support, or strategy that this product can attack.
- **threat_level** — `High` / `Medium` / `Low`. High = directly competing for same deals today. Medium = adjacent overlap. Low = different segment but worth tracking.

**Categories to group by:**

A) **Tier-A direct competitors** — feature-set overlap >70%, same ICP.
B) **Tier-B adjacent / partial competitors** — overlap on some surfaces but not the core wedge.
C) **Horizontal incumbents** — generalists who occasionally win in this vertical (e.g. Shopify, RepairShopr, ServiceTitan).
D) **OEM / closed-ecosystem competitors** — locked into a single brand's dealer network, can't be displaced inside that ecosystem.
E) **Dead / defunct / pivot-away** — names that come up in conversation but aren't really competing anymore. Document so the sales team doesn't waste cycles.

Target **15–30 competitors total** across categories. Quality > quantity — a thorough tear-down on 15 beats a shallow list of 50.

**Where you can't find a number, don't fabricate it.** Use "verify" or "unknown public estimate".

End with:

- A **Top 5 competitive weaknesses to attack today** section — concrete plays the founder can run this quarter.
- A **Threat-level summary table** — competitors grouped by threat_level for at-a-glance reading.
- A **Don't burn cycles on these** section — competitors not worth deep response (defunct, structurally locked away, segment mismatch).
- A **Watch list** — competitors to re-check in 6 months because of recent funding / pivot / product launch.

**Output format — return both of these together, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Per competitor, a structured block with all the captured fields. Group under category headings. End with the four closing sections and a **Sources** section listing the URLs you actually relied on (pricing pages, LinkedIn pages, Crunchbase profiles, news articles).

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<A|B|C|D|E group name>",
    "name": "<competitor name>",
    "url": "<homepage URL>",
    "founded_year": "<YYYY or 'verify'>",
    "hq_country": "<US|UK|EU|ES|FR|DE|...>",
    "employees_approx": "<e.g. '11-50' or '~250'>",
    "revenue_or_funding": "<one line — public estimate>",
    "pricing_snapshot": "<one line — starting price + model>",
    "key_features": "<3-5 features, comma-separated>",
    "notable_customers": "<2-4 named customers>",
    "strengths": "<honest one-line>",
    "weaknesses_to_exploit": "<concrete gap to attack>",
    "threat_level": "High | Medium | Low"
  }
]
```

The JSON must include **every competitor from the markdown**. Don't skip any.

**JSON formatting**: Use literal `&`, `<`, `>` characters inside JSON string values. Do NOT use HTML entities like `&amp;`, `&lt;`, `&gt;` — JSON has no HTML escapes, so those would appear verbatim in downstream spreadsheets. The JSON block must be valid `json.loads()`-parsable, with the intended characters appearing as-is.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. ~2000–3000 words of markdown is fine.
