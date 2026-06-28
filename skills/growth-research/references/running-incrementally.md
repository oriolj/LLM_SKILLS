# Running the skill on an existing workdir

The default procedure in `SKILL.md` assumes a greenfield workdir — empty directory, scaffold everything from scratch. This document covers the common alternative: **adding a new slice (or refreshing an existing one) on a growth-research repo that already exists**.

Load this reference when the user says things like:

- "Add competitor intel to my existing Enacast research repo."
- "Refresh the regulatory slice — it's six months old."
- "Run the influencers agent on bikecrm again, then merge."
- "I already have the base 4 slices, now do the extended ones."

## When does this apply

Three flavours of incremental work share most of the procedure:

| Flavour | Example | Difference |
|---|---|---|
| **Add new slice(s)** | Base 4 exist; add `influencers` | Only spawn the new agents; leave existing folders untouched. |
| **Refresh one slice** | `competitor_intel` exists but is stale | Spawn one agent; overwrite that topic's `.md` + `.json`; regenerate xlsx. |
| **Migrate from old format** | Old run used inline-Python data in `build_xlsx.py` | One-shot extract to JSON sidecars, then overwrite the script. |

## Procedure

### 1. Confirm the workdir

```bash
cd <workdir>
git status
find research -name '*.md' -type f | sort
cat README.md | head -30
```

Confirm: right repo, expected slices present, product summary still accurate. **Don't re-derive the product from a fresh `WebFetch`** — the existing `README.md` is the source of truth for what the product is. Only re-fetch if the user says the product has changed.

### 2. Read CLAUDE.md before touching anything

The workdir's `CLAUDE.md` may have project-specific conventions (language tags, surface names, capitalisation rules) that earlier runs locked in. Follow those.

### 3. Check the build_xlsx.py shape

Open `scripts/build_xlsx.py`. Two possibilities:

- **New shape (JSON-driven)**: a `TOPICS = {...}` dict mapping topic names to field lists; `build()` reads `research/<topic>/<topic>.json`. This is the current canonical shape. Proceed to step 5.
- **Old shape (inline Python)**: module-level `SUBREDDITS = [...]`, `MAGAZINES = [...]` etc., with tuple rows passed to `write_sheet`. **Migrate first** — see step 4.

### 4. Migrate inline-Python data to JSON sidecars (only if needed)

One-shot script — adapt to whatever constant names the old script used:

```python
# /tmp/migrate.py
import json, sys
from pathlib import Path
WORKDIR = Path("<workdir>")
sys.path.insert(0, str(WORKDIR / "scripts"))
from build_xlsx import SUBREDDIT_COLS, SUBREDDITS, MAGAZINE_COLS, MAGAZINES, CONF_COLS, CONFERENCES, PARTNER_COLS, PARTNERS

# Map old column-header strings to new JSON keys.
HEADER_TO_KEY = {
    "Category": "category", "Subreddit": "subreddit", "URL": "url",
    "Approx. subs": "approx_subs", "Fit": "fit", "Geography": "geography",
    "Angle / use": "angle", "Self-promo / red flags": "self_promo_flags",
    "Outlet": "outlet", "Country": "country", "Audience": "audience",
    "Reach / size": "reach", "Notes / contact": "notes",
    "Event": "event", "Dates (2026)": "dates", "City": "city",
    "Attendees": "attendees", "Sponsorship range": "sponsorship_range",
    "Why it matters": "why_it_matters",
    "Company": "company", "What they do": "what_they_do", "Role": "role",
    "Surface": "surface", "Pitch angle": "pitch",
    "Partner program / contact": "partner_program_or_contact",
}

for topic, cols, rows in [
    ("subreddits", SUBREDDIT_COLS, SUBREDDITS),
    ("magazines",  MAGAZINE_COLS,  MAGAZINES),
    ("conferences", CONF_COLS,     CONFERENCES),
    ("partners",   PARTNER_COLS,   PARTNERS),
]:
    keys = [HEADER_TO_KEY[c] for c in cols]
    dicts = [dict(zip(keys, row)) for row in rows]
    out = WORKDIR / "research" / topic / f"{topic}.json"
    out.write_text(json.dumps(dicts, ensure_ascii=False, indent=2) + "\n")
    print(f"{topic}: {len(dicts)} rows -> {out.relative_to(WORKDIR)}")
```

Run it once. Then overwrite `scripts/build_xlsx.py` with the JSON-driven version from `references/build_xlsx.py`. Confirm `python3 scripts/build_xlsx.py` reproduces the existing xlsx files byte-for-byte (or close enough — minor styling diffs are OK).

### 5. Copy the latest build_xlsx.py if your run needs newer topics

If the existing script doesn't know about the topic you're adding (e.g. you're adding `influencers` but the script only handles the base 4), overwrite it with `references/build_xlsx.py`. The newer script supports all 8 topics and **skips any topic that has no JSON file** — so older topics keep working untouched.

### 6. Scaffold only the new topic folders

```bash
mkdir -p research/<new_topic>/
# (don't touch existing research/<existing_topic>/ folders)
```

### 7. Spawn agents for the new (or to-be-refreshed) slices only

Use the parallel-agent procedure from `SKILL.md` Step 4, but limit it to the slices in scope. Re-use the product context from the workdir's `README.md` — don't re-derive it.

### 8. Persist outputs with `persist_agent_output.py`

For each completed agent:

```bash
python3 scripts/persist_agent_output.py <topic> --from /tmp/agent_output.txt
```

This cleans HTML entities, validates the JSON, and writes both `<topic>.md` and `<topic>.json` into the right folder. Copy `references/persist_agent_output.py` into the workdir's `scripts/` if it isn't there yet.

When you're refreshing a slice rather than adding one, the helper overwrites the existing files — confirm with the user before doing this on a slice with hand-edits.

### 9. Run `python3 scripts/build_xlsx.py`

Regenerates xlsx for every topic that has a JSON file. Existing topics are unchanged (same JSON in → same xlsx out). New topics get their first xlsx.

### 10. Update `GROWTH_RESEARCH.md`

Don't rewrite. **Add a new section** referencing the new slices, with a short top-N callout (e.g. "Top 10 KOLs to DM this quarter" / "Top 5 competitive plays" / "Top 5 regulatory windows by date"). The existing Top-12 actions section stays. The "Repo layout" tree at the bottom needs to mention the new folder(s).

### 11. Commit with a descriptive message

The git log should make it obvious which slices were added when. Examples:

- `research: add 3 extended slices (influencers, competitor intel, regulatory)`
- `research: refresh competitor_intel (Q2 2026)`
- `research: migrate to JSON sidecars + add influencers`

## Anti-patterns specific to incremental runs

- **Don't re-fetch the product page** unless the product has materially changed. The README and CLAUDE.md are the source of truth — using them keeps surface tags, language conventions, and pricing details consistent across slices.
- **Don't reorder existing categories** in a refreshed slice's markdown without explicit reason. Diffs in xlsx are fine; diffs in markdown are reviewed by the user, and gratuitous reordering hides the actual content change.
- **Don't run all 8 agents again to refresh one slice.** Spawn just the agent(s) that need refreshing.
- **Don't bump the JSON schema for an existing topic without migrating the existing data.** If you need a new column on a slice that already has rows, write a migration script that backfills the new field on every existing row (use `""` or `"verify"` as default) and add it to `build_xlsx.py` and the agent prompt in one commit.
- **Don't commit the migration script into the workdir.** It's a one-shot — keep it in `/tmp` and discard once the migration is verified.
