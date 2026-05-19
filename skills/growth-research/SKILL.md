---
name: growth-research
description: Build a complete growth / go-to-market research deck for any product — subreddits to advertise on, magazines and newsletters to sponsor or pitch, conferences and trade shows to attend, and partner / channel / competitor map. Optionally extends to influencer / KOL mapping (named humans who shift buyer opinion), competitor intelligence tear-downs (pricing, employees, funding, weaknesses to exploit), and regulatory tailwind tracking (deadlines that unlock public-sector and compliance budgets). Produces a standardised repo (per-topic folders with markdown source-of-truth, JSON sidecars, and sortable xlsx mirrors, plus a top-level prioritised playbook). Use whenever the user asks to "research advertising/partner opportunities for X", "find growth channels for X", "where can we advertise X", "who could we partner with for X", "build a GTM research deck", "find subreddits / magazines / conferences / partners / influencers for X", "competitor tear-down for X", "what regulations unlock budget for X", "do an extensive partner & ads search for X", or hands over a product URL with a vague "review this and find places we can show up". Equally fits SaaS, consumer products, indie tools, agencies, podcast networks, media businesses. Not for one-off micro-questions ("what's a good subreddit for X") — for those, just answer directly without invoking this skill.
---

# Growth research playbook

Given a product (URL + maybe a short description), produce an extensive but opinionated **growth research deck**: where to advertise, where to show up in person, who to partner with, *who specifically* moves opinion in the vertical, what the competitive set looks like, and which regulations create timing windows. Output is a self-contained markdown + xlsx repo the user can hand to a BD/marketing lead.

## Base research slices (always include)

1. **Subreddits** — where to advertise / engage organically.
2. **Magazines & trade press** — newsletters, magazines, PR outlets to sponsor or pitch.
3. **Conferences & trade shows** — events to exhibit, sponsor, speak at, or attend.
4. **Partners & ecosystem** — partners, channels, competitors, potential customers.

## Extended research slices (situational — agent decides per-product)

5. **Influencers / KOLs** — named humans (industry analysts, prolific YouTubers, podcast hosts, newsletter authors, prolific X / LinkedIn voices, trade-press journalists) who shift buyer opinion. The other slices map channels; this one maps people you DM. **Include for**: any B2B product, any prosumer or creator product. **Skip for**: pure mass-consumer apps with no community of "experts" — those are influencer-marketing territory, not KOL outreach.
6. **Competitor intelligence** — depth on each direct competitor: pricing snapshot, employee count (LinkedIn), last funding round, key features, notable customers, strengths, weaknesses to exploit, threat level. The base partner slice gives you the *list*; this gives you the *intelligence* for positioning decks and competitive sales. **Include for**: any product with named direct competitors. **Skip for**: greenfield products with no real comparable.
7. **Regulatory tailwinds** — laws, directives and deadlines that create timing windows (compliance buyers, public-sector budget, mandatory features). Includes both opportunities (a directive your product happens to satisfy) and risks (a new burden falling on the SaaS itself). **Include for**: any product touching a regulated industry — finance, health, broadcasting, e-mobility, right-to-repair, accessibility, data residency. **Skip for**: purely creative / unregulated categories.

Each slice runs as a **parallel background agent** so the work finishes in roughly one agent's worth of wall clock. Each agent returns both a markdown file (rich notes, source of truth) and a JSON sidecar (rows for a sortable xlsx). A top-level `GROWTH_RESEARCH.md` consolidates the top actions.

---

## Procedure

### Step 1 — Ground the product

Before spawning any research agent, **establish what the product is**. Skipping this step is the most common failure — agents get sent off researching the wrong audience.

1. Ask the user for the product URL if not given.
2. `WebFetch` the homepage and (if findable) the pricing page. Extract:
   - **Product surfaces** — many products sell more than one thing. List each surface separately.
   - **Target customer** per surface — who pays, what role, what company size.
   - **Pricing tier(s)** — currency, billing cadence, free trial?
   - **Geography** — where the team is, where the customers are, what languages the UI supports.
   - **Marquee customers / case studies** — useful later for testimonial-amplification subreddits and PR.
3. If anything is ambiguous (e.g. the company sells to two very different ICPs), **tell the user what you found and confirm the surfaces before continuing.** Wrong ICP framing wastes the whole research run.

Output of this step: a 5–10 line product summary you'll paste into every agent prompt.

### Step 2 — Decide which slices to run

Always include slices 1–4. For 5–7, apply the inclusion criteria above. If you're including an extended slice, tell the user briefly *why* before spawning the agent — they may override.

If unsure between three close options (e.g. is this regulated enough to warrant the regulatory slice?), default to **include** — the slice will return "no major windows found" cheaply if it's a dud, and that itself is useful intelligence.

### Step 3 — Scaffold the repo

Working directory should be empty or near-empty. Create:

```
<workdir>/
├── README.md            ← product overview + repo layout
├── CLAUDE.md            ← session instructions for future Claude sessions
├── scripts/
│   └── build_xlsx.py    ← copy from this skill's references/
└── research/
    ├── subreddits/
    ├── magazines/
    ├── conferences/
    ├── partners/
    ├── influencers/             # only if including slice 5
    ├── competitor_intel/        # only if including slice 6
    └── regulatory/              # only if including slice 7
```

Templates for `README.md` and `CLAUDE.md` live in `references/readme-template.md` and `references/claude-md-template.md`. Load on demand. Fill in product-specific bits at the top.

Initialise git on `master`:

```bash
git init -b master
```

Copy `references/build_xlsx.py` into the workdir at `scripts/build_xlsx.py`. The script reads each `research/<topic>/<topic>.json` and writes the matching `.xlsx`. It already knows about all 7 topics — only the ones with JSON files generate xlsx.

### Step 4 — Spawn the research agents in parallel

Send a **single message with N `Agent` tool calls** (4–7 depending on slice choice) so they run concurrently. Use `subagent_type: general-purpose` and `run_in_background: true` for each.

Each agent prompt is a templated version of the corresponding file in `references/`:

- `references/agent-prompt-subreddits.md`
- `references/agent-prompt-magazines.md`
- `references/agent-prompt-conferences.md`
- `references/agent-prompt-partners.md`
- `references/agent-prompt-influencers.md`
- `references/agent-prompt-competitor-intel.md`
- `references/agent-prompt-regulatory.md`

**Critical substitution to do before sending the prompt:** every template has a `{{PRODUCT_CONTEXT}}` placeholder at the top — replace it with the 5–10 line product summary from Step 1 (surfaces, ICP per surface, pricing, geography, marquee customers, languages). Also adapt the `{{MARKETS}}` and `{{LANGUAGES}}` placeholders.

Every agent prompt instructs the agent to return **two artefacts together**:

1. A complete markdown document (this is the source of truth — categories, prose, source links).
2. A JSON array of rows matching a fixed schema (this drives the xlsx).

The agent's final message must contain both, clearly separated by fenced code blocks. Tell each agent NOT to write files itself — the parent caller persists them.

### Step 5 — Persist each agent's output

When an agent completes (you'll be notified via task-notification), extract:

- The markdown → write to `research/<topic>/<topic>.md`.
- The JSON → write to `research/<topic>/<topic>.json`.

Do this for each topic as it arrives. Don't wait for all of them; persist as they come in.

### Step 6 — Build the xlsx files

Once all `<topic>.json` files exist:

```bash
python3 scripts/build_xlsx.py
```

This reads each JSON, writes the matching `.xlsx` with header styling, freeze pane, autofilter, alternating-row shading, and reasonable column widths. The script is idempotent — re-run after any update. Topics without a JSON file are simply skipped.

If `openpyxl` is missing, install with `pip install openpyxl`.

### Step 7 — Write `GROWTH_RESEARCH.md`

The consolidated top-level deliverable. Load `references/growth-research-template.md` and fill in:

- One-liner per product surface (from Step 1).
- **Top-12 prioritised actions** — your pick across the slices. Mix at least one entry from each slice you ran; lead with the highest-leverage move.
- Quick-read summaries per slice with 5–10 stand-out items.
- For extended slices: a "Top 5 KOLs to DM this quarter" / "Top 3 competitive weaknesses we can attack today" / "Regulatory windows that unlock budget by date" block.
- "Don't burn cycles on these" red flags (especially from the partners and competitor-intel slices).
- Repo layout block (tree).

Don't repeat the full slice content here — link to `research/<topic>/<topic>.md` instead. This file is the executive summary; the slices are the appendices.

### Step 8 — Stop. Don't commit unless asked.

Show the user the final tree (`find . -type f -not -path './.git/*'`) and a 2–3 sentence summary of what was delivered. **Do not commit** unless the user explicitly asks.

---

## When the slices aren't the right slices

The default base 4 + situational 3 fits B2B SaaS, B2B services, mid-market consumer products, and media businesses. Two cases where you should renegotiate slices with the user before running:

- **Pure-consumer mobile app** (e.g. a meditation app, a habit tracker). Replace at least two base slices with: App-store ASO targets / Influencer tiers / Paid-social testbeds (TikTok, IG Reels, YouTube Shorts) / Subreddit testimonial seeds. Slice 5 (Influencers) gets replaced by a richer creator-tier breakdown.
- **Developer tool / open-source project**. Replace at least one base slice with: Newsletters & podcasts in the language ecosystem / Hacker News + Lobsters + DEV.to playbook / Conference CFPs / Sponsor-maintainer relationships in the OSS graph.

If the product is ambiguous, ask which slices the user wants before spawning agents. Don't silently customise — name the slices in the confirmation.

---

## Anti-patterns

- **Don't skip Step 1.** Sending agents off without a sharp product summary produces 60% generic results.
- **Don't run the agents sequentially.** They take 4–7 minutes each; parallel they take ~7 minutes total.
- **Don't have the agents write files directly.** Different agents may collide, write to the wrong path, or skip the JSON sidecar. Persist from the parent.
- **Don't conflate surfaces.** If the product has two ICPs, every research entry must be tagged with which surface it serves.
- **Don't run all 7 slices on autopilot.** The extended slices have real cost (~50K tokens each in agent compute). Apply the inclusion criteria.
- **Don't commit on the user's behalf.** This is a research repo, not a code repo — the user decides when it's ready to land.
- **Don't write a sales CRM or scraper in this repo.** Tooling lives elsewhere; this is a research deck.

---

## Reference files

Load on demand:

- `references/agent-prompt-subreddits.md` — base slice 1.
- `references/agent-prompt-magazines.md` — base slice 2.
- `references/agent-prompt-conferences.md` — base slice 3.
- `references/agent-prompt-partners.md` — base slice 4.
- `references/agent-prompt-influencers.md` — extended slice 5 (named humans / KOLs).
- `references/agent-prompt-competitor-intel.md` — extended slice 6 (tear-down per competitor).
- `references/agent-prompt-regulatory.md` — extended slice 7 (laws, directives, deadlines).
- `references/readme-template.md` — workdir `README.md` template.
- `references/claude-md-template.md` — workdir `CLAUDE.md` template.
- `references/growth-research-template.md` — top-level summary template with the top-12 frame.
- `references/build_xlsx.py` — copy this into `<workdir>/scripts/build_xlsx.py`. Knows about all 7 topics.
- `references/json-schemas.md` — the JSON row schema each agent must return.
