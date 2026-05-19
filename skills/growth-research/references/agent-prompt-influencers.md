# Influencers / KOL map — agent prompt template

Use this as the prompt for the parallel `Agent` call. Replace the `{{...}}` placeholders before sending.

---

{{PRODUCT_CONTEXT}}

I need a **named-human map** of the influencers / KOLs (Key Opinion Leaders) who shift buyer opinion in this vertical. Our other research covers *channels* (subreddits, magazines, conferences, partner orgs). This slice covers *people* — the specific individuals a founder can DM, pitch as a guest, send a free trial to, or sponsor.

A "KOL" here means: someone with a personal audience (their name on the byline, the show, the channel — not just an org account), whose endorsement or coverage of this product would move buyers.

For each KOL, capture:

- **name** — real name.
- **handle** — primary platform handle (e.g. `@jamescridland`).
- **url** — primary platform link (their newsletter, channel, podcast, profile).
- **audience_size** — best available number (subscribers / followers / monthly listeners). Mark "verify" if uncertain.
- **audience_description** — who their audience is (one line).
- **fit** — which product surface they best serve. Use the surface name(s) from the product context.
- **geography** — where their audience concentrates.
- **engagement_angle** — one-line "how to land": guest pitch / send product / sponsor episode / hire to consult / partner on co-branded content.
- **contact_path** — DM / email / agent / publisher. Be specific where you can find it (e.g. "DM via X, replies to founders").

**Group by category. Typical groupings:**

A) **Industry analysts / consultants** — paid-by-vendors strategy voices.
B) **Trade-press journalists** — people who *write the trade press* (use the magazine slice's outlets as the seed list and find the bylines).
C) **Podcast hosts** — running shows in or adjacent to the vertical.
D) **YouTubers** — running channels in or adjacent to the vertical.
E) **Newsletter authors** — independent newsletters with named editors.
F) **X / Twitter voices** — prolific accounts whose tweets move opinion.
G) **LinkedIn voices** — thought-leaders posting in the vertical.
H) **Conference circuit speakers** — recurring keynote / panel names from the conferences slice.
I) **Customer-evangelist KOLs** — practitioners (a notable user / operator from a marquee customer) who'd evangelise the product if onboarded.

Target **40+ named individuals** across categories. Skip obvious filler. If a name has a real org behind them (e.g. James Cridland → Podnews), still list the person — the org is in the magazines slice.

**Where you can't find a name, don't invent one.** Use "verify" or skip rather than fabricate.

End with:

- A **Top 10 KOLs to DM this quarter** section — ranked by leverage × landability.
- A **People-to-watch but not pitch yet** section — names worth tracking but not warm enough.
- A **Don't bother** section — high-profile names whose endorsement won't actually move buyers in this niche (e.g. household-name tech podcasters whose audience is too broad).

**Output format — return both of these together, clearly separated by fenced code blocks:**

### 1. A complete markdown document

Sections per category, each with a table or block per KOL: name, handle, URL, audience, fit, angle, contact path. End with the three closing sections. **Sources** section at the end with the URLs you actually relied on.

### 2. A JSON array matching this schema

```json
[
  {
    "category": "<group name>",
    "name": "<real name>",
    "handle": "<@handle on primary platform>",
    "url": "<primary platform link>",
    "audience_size": "<e.g. '33K subs' or 'verify'>",
    "audience_description": "<one line — who they reach>",
    "fit": "<product surface name(s) — 'Both' if both>",
    "geography": "<US|UK|EU|ES|FR|DE|Global|...>",
    "engagement_angle": "<one-line: how to land them>",
    "contact_path": "<DM / email / agent / publisher — be specific>"
  }
]
```

The JSON must include **every named person from the markdown**. Don't skip any.

**Do not write files.** Return both artefacts in your final message — the caller will persist them.

Be specific. ~1500–2500 words of markdown is fine.
