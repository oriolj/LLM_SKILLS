# Conferences / trade shows — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need a **comprehensive list of trade shows, conferences, festivals, and industry events** in {{TARGET_YEAR}} (and early {{NEXT_YEAR}} if known) where this product could exhibit, sponsor, speak, or do partner BD. Markets to prioritise: {{MARKETS}}.

For each event include:

- Event name + URL
- Dates ({{TARGET_YEAR}}) — search for actual dates, not last year's
- City / country
- Audience profile (who's actually in the room)
- Approximate attendee count
- Product-surface fit and why it matters
- Sponsorship / booth opportunities and rough cost tier if findable (booths €X-Y / sponsorships $X-Y / "tiered partnerships")

**Group by category — choose what fits the product. Typical groupings:**

- Events in the product's primary vertical, split by US / EU
- Adjacent-vertical events (one step removed)
- Broadcasting / media / production tech (if applicable)
- Ad-tech / media buying (if monetisation matters)
- Creator economy / tech startup events
- Academic / community events
- Language- or region-specific events for each non-English market the product targets

Target **40+ events**. Mark events whose {{TARGET_YEAR}} edition has already passed as "(passed) — note for {{NEXT_YEAR}} planning" so they still appear in the calendar.

End with a **Top-12 to prioritise** section: ranked list optimised for the product's specific surfaces and markets. Mix venues, geographies, and surface fits.

**Output format — return both of these together in your final message, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Per event, a block with: URL, dates, venue, audience, attendee count, relevance, sponsorship range. Group under category headings.

End with:
- A **Top-12 to prioritise** section.
- A **Wildcards** section (prestige or speculative events).

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<group name>",
    "event": "<name>",
    "url": "<event homepage URL>",
    "dates": "<e.g. 'Mar 22-24' or 'Q3 (TBC)'>",
    "city": "<city name>",
    "country": "<US|UK|FR|DE|ES|NL|...>",
    "fit": "<product surface(s) — 'Both' if both>",
    "attendees": "<e.g. '1.5K+' or '~10K'>",
    "sponsorship_range": "<e.g. '$10-50K booths' or '€5-15K + sponsorships €15-60K'>",
    "why_it_matters": "<one-line — why for this product>"
  }
]
```

The JSON must include **every event from the markdown**, with matching values. Don't skip any.

**JSON formatting**: Use literal `&`, `<`, `>` characters inside JSON string values. Do NOT use HTML entities like `&amp;`, `&lt;`, `&gt;` — JSON has no HTML escapes, so those would appear verbatim in downstream spreadsheets. The JSON block must be valid `json.loads()`-parsable, with the intended characters appearing as-is.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. ~1500–2500 words of markdown is fine.
