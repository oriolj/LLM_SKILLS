# Magazines / trade press / newsletters — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need an **extensive list of magazines, online trade publications, newsletters, and PR outlets** where this product can either:

- buy display / sponsorship ads,
- pitch a press release / product launch story,
- pitch a guest op-ed (founder thought leadership),
- sponsor a newsletter.

Markets to prioritise: {{MARKETS}}. Language coverage to consider: {{LANGUAGES}}.

For each outlet I want: **name, URL, country, audience description, approximate audience size (if findable), product-surface fit, and contact / ad-page link if you can find it.**

**Group by category — choose categories that fit the product. Typical groupings:**

- Industry trade press in the product's primary vertical, split by US / UK / EU / regional language
- Adjacent-vertical trade press (one step removed but still relevant readership)
- Per-language press for each non-English language the product supports
- Indie / startup / SaaS outlets (TechCrunch, Sifted, Tech.eu, EU-Startups, Product Hunt, Indie Hackers, The Information, Nieman Lab) — for product launches and thought leadership
- Newsletters worth sponsoring (with reach + open-rate where findable)
- Editorial-only outlets to pitch but not ad on (and a brief "why no ads here")

Target **40+ outlets total**. Where you can find a rate-card / "advertise with us" / "sponsor" page, link it. Skip filler — useful entries only.

End with a **Summary Picks** section: ranked list of 10–15 newsletters / outlets by signal-to-cost for this product. This is the part the user reads first.

**Output format — return both of these together in your final message, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Per outlet, a 2–4 sentence block with: what it is, audience profile, reach numbers, why it's relevant, advertise URL / contact. Group under category headings.

End with:
- A **Summary Picks** section (ranked top 10–15).
- An **Outlets to monitor / pitch but not buy ads on** section.
- A **Sources** section with the URLs you actually relied on.

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<group name>",
    "outlet": "<name>",
    "url": "<homepage URL>",
    "country": "<US|UK|EU|ES|FR|DE|IT|NL|Global|...>",
    "fit": "<product surface or 'Both'>",
    "audience": "<who reads it>",
    "reach": "<subs / page views / circulation>",
    "notes": "<contact email, advertise URL, special notes>"
  }
]
```

The JSON must include **every outlet from the markdown**, with matching values. Don't skip any.

**JSON formatting**: Use literal `&`, `<`, `>` characters inside JSON string values. Do NOT use HTML entities like `&amp;`, `&lt;`, `&gt;` — JSON has no HTML escapes, so those would appear verbatim in downstream spreadsheets. The JSON block must be valid `json.loads()`-parsable, with the intended characters appearing as-is.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. ~1500–2500 words of markdown is fine.
