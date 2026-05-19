# Partner ecosystem — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need a **comprehensive map of the partner ecosystem** around this product. For every entry describe:

- Company name + URL
- What they do (1 line)
- Whether they're a likely **PARTNER** (complementary), a **CHANNEL** (could resell / refer), a **COMPETITOR** (overlapping product — red flag), a **CUSTOMER** (could buy at scale), or a **VENDOR** (the product likely pays them). Combinations OK (`PARTNER + CHANNEL`, `COMPETITOR + PARTNER`).
- Which product surface this partner serves (use the surface names from the product context).
- Geography.
- The concrete partnership angle / pitch in one line.
- Any known partner program URL or BD contact path.

**Group by category — pick what fits the product. Typical groupings for a SaaS / media product:**

1. **Direct ecosystem peers** — platforms / tools the ICP already pays for (hosting, distribution, the surface the product plugs into)
2. **Aggregators / networks / federations** — bodies that represent many of the product's target customers (industry associations, trade bodies, university networks)
3. **Measurement / analytics adjacent** — data players the product can exchange signals with
4. **Monetisation / ad-tech adjacent** — if the product's data has ad-targeting value
5. **Direct competitors** — must benchmark; mark as RED FLAG and note the moat angle
6. **Adjacent vendors / channels** — tools the ICP also uses that aren't competing but could co-market
7. **AI / API / infrastructure vendors** — the product probably pays them; some are co-marketing opportunities
8. **Open-source / community alignment** — projects to align with for goodwill (sponsor, contribute, integrate)

Target **70+ entities**. Be specific. Mark obvious competitors as red flags rather than partners. Mark companies owned by hostile parents (e.g. closed-ecosystem big platforms) as red flags too.

End with:

- A **Priority shortlist (BD sequencing)** — top 10 first meetings to book, ranked.
- A **Hard red flags** section — who not to spend BD cycles on, and why (defunct, closed ecosystem, structurally adversarial).

**Output format — return both of these together in your final message, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Per company, a bullet with: name + URL, what they do, role tag, pitch angle, partner program URL if any. Group under category headings.

End with:
- A **Priority shortlist** section (top 10 ranked).
- A **Hard red flags** section.
- A **Sources** section.

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<group name>",
    "company": "<name>",
    "url": "<homepage URL or '—' if defunct>",
    "what_they_do": "<one-line description>",
    "role": "<PARTNER | CHANNEL | COMPETITOR | CUSTOMER | VENDOR | RED FLAG, or combinations>",
    "surface": "<product surface this serves>",
    "geography": "<US|UK|EU|ES|FR|DE|Global|...>",
    "pitch": "<one-line BD pitch angle, or '—' if competitor/red flag>",
    "partner_program_or_contact": "<URL or contact path, or '—'>"
  }
]
```

The JSON must include **every company from the markdown**, with matching values. Don't skip any.

**JSON formatting**: Use literal `&`, `<`, `>` characters inside JSON string values. Do NOT use HTML entities like `&amp;`, `&lt;`, `&gt;` — JSON has no HTML escapes, so those would appear verbatim in downstream spreadsheets. The JSON block must be valid `json.loads()`-parsable, with the intended characters appearing as-is.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. ~2000–3500 words of markdown is fine.
