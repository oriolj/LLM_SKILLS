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

## Conventions

- **`fit` / `surface`** values must match the product surfaces from Step 1 (e.g. `Radio SaaS`, `Insights`, `Both`). For single-surface products use that surface name everywhere.
- **`role`** in partners is one of: `PARTNER`, `CHANNEL`, `COMPETITOR`, `CUSTOMER`, `VENDOR`, `RED FLAG` — or combinations (`PARTNER + CHANNEL`).
- **`geography`** uses ISO-style codes when possible (`US`, `UK`, `EU`, `ES`, `FR`, `DE`, `LATAM`, `Global`). Multi-region OK (`EU/UK`).
- **`category`** groups related rows together for filtering — give them a stable prefix so they sort sensibly (e.g. `A. Podcaster communities`, `B. Listener communities`).
- If a row has no URL (e.g. a defunct competitor referenced for context), use `"—"` not `""`.
