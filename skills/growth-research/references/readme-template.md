# {{PRODUCT_NAME}} — Partners & Ads Research

A working repository for go-to-market research for [**{{PRODUCT_NAME}}**]({{PRODUCT_URL}}):

- **Where to advertise** — subreddits, magazines, newsletters, trade press.
- **Where to show up in person** — trade shows, conferences, festivals (EU + US).
- **Who to talk to as a partner** — platforms, networks, federations, ad-tech, AI vendors.
- **Who the competitors are** — for positioning and benchmarking.

## What {{PRODUCT_NAME}} is

{{PRODUCT_SUMMARY}}

## Markets

{{MARKETS_PARAGRAPH}}

## Repo layout

```
{{WORKDIR_NAME}}/
├── README.md                   ← this file
├── CLAUDE.md                   ← session instructions for Claude
├── GROWTH_RESEARCH.md          ← consolidated executive summary + top-12 actions
├── scripts/
│   └── build_xlsx.py           ← regenerates xlsx from the JSON sidecars
└── research/
    ├── subreddits/             subreddits.md + subreddits.json + subreddits.xlsx
    ├── magazines/              magazines.md + magazines.json + magazines.xlsx
    ├── conferences/            conferences.md + conferences.json + conferences.xlsx
    └── partners/               partners.md + partners.json + partners.xlsx
```

Each topic folder has:

- `<topic>.md` — full notes + rationale. **Source of truth.**
- `<topic>.json` — same data, structured rows.
- `<topic>.xlsx` — sortable spreadsheet generated from the JSON.

## How this repo is used

This is a **research repo**, not a code repo. No build, no tests, no Makefile. Update the markdown files as new findings come in. Mirror the change into the matching `.json` and rerun `python3 scripts/build_xlsx.py` to regenerate the spreadsheets. Commit progress so the history is a paper trail of what we considered.
