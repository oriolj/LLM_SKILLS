# JSON row schemas

Every research agent must return both a markdown document (source of truth, with prose + categories + sources) **and** a JSON array of rows matching the schema below. The parent caller persists the JSON to `research/<topic>/<topic>.json`; `scripts/build_xlsx.py` reads it and writes the matching `.xlsx`.

All fields are strings. Use `""` for unknown values, never `null`. Wrap multi-line text into a single line. Don't embed markdown formatting inside cells — they render as plain text.

## subreddits.json

```json
[
  {
    "category": "A. Podcaster communities",
    "subreddit": "r/podcasting",
    "url": "https://reddit.com/r/podcasting",
    "approx_subs": "~165–200K",
    "fit": "Insights",
    "geography": "Global",
    "angle": "Workflow/editing posts; weekly feedback thread tolerated",
    "self_promo_flags": "Strict self-promo rule; karma gate via AutoMod"
  }
]
```

Columns in xlsx: `Category, Subreddit, URL, Approx. subs, Fit, Geography, Angle / use, Self-promo / red flags`.

## magazines.json

```json
[
  {
    "category": "US podcast trade",
    "outlet": "Podnews",
    "url": "https://podnews.net",
    "country": "US/Global",
    "fit": "Both",
    "audience": "Senior podcast/audio decision-makers worldwide",
    "reach": "33K subs, ~26.8M page views/30d",
    "notes": "Daily briefing by James Cridland. sales@podnews.net"
  }
]
```

Columns in xlsx: `Category, Outlet, URL, Country, Fit, Audience, Reach / size, Notes / contact`.

## conferences.json

```json
[
  {
    "category": "US podcast",
    "event": "PodFest Multimedia Expo",
    "url": "https://podfestexpo.com/",
    "dates": "Jan 15-18",
    "city": "Orlando",
    "country": "US",
    "fit": "Insights",
    "attendees": "~2-2.5K",
    "sponsorship_range": "$3-7K booths",
    "why_it_matters": "Indie hosts dense; lower-cost than Podcast Movement"
  }
]
```

Columns in xlsx: `Category, Event, URL, Dates, City, Country, Fit, Attendees, Sponsorship range, Why it matters`.

## partners.json

```json
[
  {
    "category": "Hosting platforms",
    "company": "Buzzsprout",
    "url": "https://buzzsprout.com",
    "what_they_do": "Largest indie host (~100K shows); Cohost AI add-on",
    "role": "COMPETITOR + CHANNEL",
    "surface": "Insights",
    "geography": "Global",
    "pitch": "Position Insights as the deeper analytics layer their Cohost AI feeds into",
    "partner_program_or_contact": "—"
  }
]
```

Columns in xlsx: `Category, Company, URL, What they do, Role, Surface, Geography, Pitch angle, Partner program / contact`.

## influencers.json (extended slice 5)

```json
[
  {
    "category": "Trade-press journalists",
    "name": "James Cridland",
    "handle": "@jamescridland",
    "url": "https://podnews.net",
    "audience_size": "33K newsletter subs",
    "audience_description": "Senior podcast / audio decision-makers worldwide",
    "fit": "Insights",
    "geography": "Global (US-anchored)",
    "engagement_angle": "Pitch Insights as a guest topic on Podnews Weekly Review",
    "contact_path": "james@podnews.net"
  }
]
```

Columns in xlsx: `Category, Name, Handle, URL, Audience size, Audience, Fit, Geography, Engagement angle, Contact path`.

## competitor_intel.json (extended slice 6)

```json
[
  {
    "category": "A. Tier-A direct competitors",
    "name": "Bikedesk",
    "url": "https://bikedesk.com",
    "founded_year": "2018",
    "hq_country": "DK",
    "employees_approx": "11-50",
    "revenue_or_funding": "Bootstrapped, undisclosed",
    "pricing_snapshot": "From €79/mo per shop",
    "key_features": "POS, workshop tickets, SMS, calendar, multilingual",
    "notable_customers": "Verify — list 2-4 from public site",
    "strengths": "Mature EU/UK product with deep IBD focus",
    "weaknesses_to_exploit": "Heavy POS-led UX; workshop-first competitors win on mechanic ergonomics",
    "threat_level": "High"
  }
]
```

Columns in xlsx: `Category, Name, URL, Founded, HQ country, Employees, Revenue / funding, Pricing snapshot, Key features, Notable customers, Strengths, Weaknesses to exploit, Threat level`.

## regulatory.json (extended slice 7)

```json
[
  {
    "category": "A. EU directives + regulations",
    "jurisdiction": "EU",
    "regulation_name": "EU Right-to-Repair Directive",
    "effective_date": "2027-07-31 (transposition deadline)",
    "status": "In force",
    "url": "https://eur-lex.europa.eu/eli/dir/2024/1799/oj",
    "summary": "Mandates repair-friendly product design, spare-parts availability, repair information disclosure",
    "relevance_to_product": "BikeCRM shops are the workshops that perform the repairs; rule unlocks shop demand",
    "compliance_burden_on": "Buyer",
    "sales_angle": "Pitch BikeCRM as the compliance-ready software 6 months before the 2027 transposition deadline",
    "risk_to_us": "—",
    "notes": "Member-state implementation varies; watch ES / FR transposition timing"
  }
]
```

Columns in xlsx: `Category, Jurisdiction, Regulation, Effective date, Status, URL, Summary, Relevance, Burden on, Sales angle, Risk to us, Notes`.

## Conventions

- **`fit` / `surface`** values must match the product surfaces from Step 1 (e.g. `Radio SaaS`, `Insights`, `Both`). For single-surface products use that surface name everywhere.
- **`role`** in partners is one of: `PARTNER`, `CHANNEL`, `COMPETITOR`, `CUSTOMER`, `VENDOR`, `RED FLAG` — or combinations (`PARTNER + CHANNEL`).
- **`threat_level`** in competitor_intel is one of: `High`, `Medium`, `Low`.
- **`status`** in regulatory is one of: `In force`, `Phased rollout`, `Pending entry into force`, `Proposal / draft`, `Repealed`.
- **`compliance_burden_on`** in regulatory is one of: `Buyer`, `Us as SaaS`, `Both`, `Ecosystem partner`.
- **`geography`** uses ISO-style codes when possible (`US`, `UK`, `EU`, `ES`, `FR`, `DE`, `LATAM`, `Global`). Multi-region OK (`EU/UK`).
- **`category`** groups related rows together for filtering — give them a stable prefix so they sort sensibly (e.g. `A. Podcaster communities`, `B. Listener communities`).
- If a row has no URL (e.g. a defunct competitor referenced for context), use `"—"` not `""`.
