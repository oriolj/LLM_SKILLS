# Pricing & packaging strategy — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need a **pricing & packaging strategy report** for this product. The deliverable is a decision-ready recommendation: scan what the market charges today, analyse the product's value proposition and willingness-to-pay drivers, then **propose concrete pricing tiers and a go-to-market pricing strategy** the founder can act on this quarter.

This slice runs in parallel with the others, so do your **own** market price scan — don't assume a competitor list exists. Where you genuinely can't find a public price, say so ("Custom / contact-sales only", "verify") rather than inventing a number.

## What to research and produce

Work through these in order; each becomes a section of the markdown report.

### 1. Market price scan (benchmark anchors)
Find what comparable and adjacent products charge. For each anchor capture: who they are, their entry price, their billing model (per-seat / per-location / flat / usage / tiered / freemium), and what value metric they charge on. Note the **floor, median, and ceiling** of the market so we know the price corridor. Pull from public pricing pages; cite them.

### 2. Value proposition & willingness-to-pay
- What concrete value does the product deliver per surface (time saved, revenue gained, risk/compliance avoided, jobs replaced)? Translate to money where possible — this is the anchor for **value-based pricing**.
- Identify candidate **value metrics** (what to charge *per*): per seat, per location, per active child/customer, per transaction, per GB, flat. Recommend one and say why — the value metric is the single most important pricing decision.
- Note willingness-to-pay differences across the product surfaces / segments.

### 3. Recommended pricing & packaging
- Propose a concrete **tier ladder** (typically 3–4 tiers: a wedge/entry tier, a core tier, a power/expansion tier, plus Enterprise/custom if warranted). For each tier: name, price point (with currency + billing cadence, monthly and annual), the value metric, the target segment, and the 2–4 headline features that gate it.
- Decide **free trial vs freemium vs paid-only** and justify it.
- Propose **add-ons / packaging levers** (usage overages, premium support, onboarding fees) that drive expansion revenue.
- Apply sensible **price psychology** (anchor tier, charm pricing, annual discount, decoy if useful).

### 4. Pricing strategy & GTM
- Name the overall strategy: **penetration** (land cheap, expand), **value-based**, **skim** (premium-first), or **competitive** (anchor to a rival) — and justify against the market scan and stage.
- Discounting & sales motion: list price vs negotiated, annual prepay incentive, design-partner / founding-customer deals.
- **Regional / multi-market pricing** if the product spans markets ({{MARKETS}}, languages {{LANGUAGES}}) — currency, purchasing-power adjustment, tax/VAT framing.
- Expansion path (land-and-expand, seat growth, upsell triggers) and the metric that signals a customer is ready to move up a tier.

### 5. Monetization experiments / roadmap
Concrete tests to run in the next 1–2 quarters (e.g. Van Westendorp / price-sensitivity survey, A/B a higher anchor, gate one feature behind the core tier) with what each would tell us.

## Categories to group rows by

A) **Recommended tiers** — the proposed plan ladder.
B) **Market benchmark anchors** — competitor / adjacent price points that justify the corridor.
C) **Packaging & add-ons** — overages, premium support, onboarding, usage levers.
D) **Pricing levers / strategy** — discounting, annual incentive, regional pricing, value-metric choice (one row each).
E) **Monetization experiments** — tests to run, with the hypothesis.

## Closing sections of the markdown

- **Recommended price card** — the tier ladder laid out as a clean comparison the founder can paste into a deck.
- **The one decision that matters most** — call the single highest-leverage pricing move (usually the value metric or the entry price).
- **Risks & don't-do** — pricing mistakes to avoid (under-pricing the wedge, too many tiers, charging on a metric customers can't predict, leaving enterprise money on the table).
- **Sources** — the pricing pages and references you actually relied on.

**Output format — return both of these together, clearly separated by fenced code blocks:**

### 1. A complete markdown document

The full report with sections 1–5 above plus the closing sections. ~1500–2500 words is fine. Be specific and opinionated — a recommendation, not a survey.

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<A|B|C|D|E group name>",
    "item": "<tier name, competitor anchor, add-on, lever, or experiment>",
    "surface": "<which product surface / segment this applies to, or 'All'>",
    "price_point": "<currency + amount + cadence, e.g. '€29/mo (annual €290)' or 'Free' or 'Custom'>",
    "billing_model": "<Per-seat | Per-location | Flat | Usage | Tiered | Freemium | —>",
    "value_metric": "<what you charge per, e.g. 'per location', 'per active child'>",
    "target_segment": "<who this is for>",
    "positioning": "<one-line strategic role, e.g. 'entry wedge vs spreadsheets'>",
    "benchmark_anchor": "<competitor price this references, or '—' for benchmark rows>",
    "rationale": "<why this price / lever>",
    "risk_or_note": "<watch-out, dependency, or caveat>",
    "confidence": "High | Medium | Low"
  }
]
```

Every recommended tier, benchmark anchor, add-on, lever, and experiment in the markdown must appear as a row. Use `""` for genuinely unknown values and `"—"` where a field doesn't apply.

**JSON formatting**: Use literal `&`, `<`, `>` characters inside JSON string values. Do NOT use HTML entities like `&amp;`, `&lt;`, `&gt;` — JSON has no HTML escapes, so those would appear verbatim in downstream spreadsheets. The JSON block must be valid `json.loads()`-parsable.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.
