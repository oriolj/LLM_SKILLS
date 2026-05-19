# Regulatory tailwinds — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need a **regulatory tailwind tracker**: laws, directives, standards and deadlines that create timing windows for this product. Two kinds of entries matter:

- **Opportunities** — a regulation that creates demand for what this product already does. Compliance buyers, public-sector budget, mandatory features that make our pitch easier. *These are sales-enablement gold.*
- **Risks / burdens** — a regulation that places a new compliance load on the SaaS itself (us), our customers, or the ecosystem. Worth knowing so we don't get blindsided and can position ourselves ahead.

Coverage should span every jurisdiction the product sells into. Markets: {{MARKETS}}.

For each regulation, capture:

- **jurisdiction** — `EU` (whole bloc) or per-country (`US`, `UK`, `ES`, `FR`, `DE`, `IT`, etc.).
- **regulation_name** — official short name (e.g. "EU Right-to-Repair Directive", "AI Act", "DAC7", "DSA").
- **effective_date** — when it takes / took effect, or staged dates if phased.
- **status** — `In force` / `Phased rollout` / `Pending entry into force` / `Proposal / draft` / `Repealed`.
- **url** — official text or authoritative summary (EUR-Lex, gov.uk, federal register, national official journal). Avoid blog-post summaries when official text exists.
- **summary** — one line: what the rule actually requires.
- **relevance_to_product** — one line: why this matters for THIS product specifically (not generic).
- **compliance_burden_on** — `Buyer` / `Us as SaaS` / `Both` / `Ecosystem partner`. Who has to comply, who pays the bill.
- **sales_angle** — concrete one-line play to monetise the deadline (e.g. "Pitch as the compliance-ready software 6 months before the May 2027 deadline").
- **risk_to_us** — if any new burden falls on the SaaS, one line on what we'd need to add. Empty string if pure opportunity.
- **notes** — open field for nuance (enforcement intensity, member-state divergence, lobbying status, etc.).

**Categories to group by (pick what applies):**

A) **EU directives + regulations** — Right-to-Repair, AI Act, DSA, DMA, accessibility, ePrivacy, GDPR enforcement updates, sectoral (e.g. broadcasting, mobility, payments).
B) **US federal** — FCC, FTC, CPSC, sector-specific.
C) **US state-level** — California, Colorado, Texas, New York where applicable.
D) **UK post-Brexit divergences** — UKCA, ICO updates, OFCOM.
E) **Per-country EU member state implementations** — DE Bundesnetzagentur, FR ARCEP / DGCCRF, ES CNMC, IT AGCOM — where the directive's implementation has bite.
F) **Industry standards / certifications** — ISO, IEEE, IEC, vertical-specific (e.g. ISO 11088 for ski bindings, EN 365 for PPE).
G) **Public-sector funding programmes** — grants and procurement frameworks that compliance status unlocks.
H) **Tax / VAT / payments rules** — DAC7, OSS / IOSS, e-invoicing mandates (e.g. France's electronic invoicing 2026–2027 rollout).
I) **Sector-specific enforcement deadlines** — anything date-specific that creates pre-deadline sales urgency.

Target **20–40 regulations**. Skip generic ones that apply to all SaaS (just GDPR or just PCI-DSS at the boilerplate level) unless the product has a specific angle on them.

**Where a date is uncertain, mark "verify".** Don't invent dates.

End with:

- A **Top 5 windows that unlock budget by date** section — ranked by sales-enablement leverage × deadline urgency. This is the most actionable section.
- A **Risks falling on us as SaaS** section — what we'd need to add or change about our own product, ranked.
- A **Watch list** — proposals not yet in force but heading that way over the next 12–24 months.

**Output format — return both of these together, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Per regulation, a structured block with all the captured fields. Group under category headings. End with the three closing sections and a **Sources** section listing official URLs.

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<A|B|C|D|... group name>",
    "jurisdiction": "EU|US|UK|ES|FR|DE|...",
    "regulation_name": "<official short name>",
    "effective_date": "<YYYY-MM or 'phased: Y1, Y2' or 'verify'>",
    "status": "In force | Phased rollout | Pending entry into force | Proposal / draft | Repealed",
    "url": "<official source URL>",
    "summary": "<one line — what it requires>",
    "relevance_to_product": "<one line — why for THIS product>",
    "compliance_burden_on": "Buyer | Us as SaaS | Both | Ecosystem partner",
    "sales_angle": "<one-line concrete play>",
    "risk_to_us": "<one line, or '—' if pure opportunity>",
    "notes": "<nuance, enforcement intensity, etc.>"
  }
]
```

The JSON must include **every regulation from the markdown**. Don't skip any.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. Cite the official text where you can. ~1500–2500 words of markdown is fine.
