---
name: obsidian-vault
description: Turn a git repo (or any docs folder) into a navigable Obsidian vault, and build filterable Bases tables over structured notes. Use when the user asks to "make this navigable in Obsidian", "open the repo as a vault", "add a table/database of X we can filter", mentions Obsidian, Bases, .base files, wikilinks vs markdown links, .obsidianignore, or hiding folders from a vault; also when adding YAML frontmatter to docs so they can be queried. Covers Oriol's standing preferences (CORE PLUGINS ONLY — never community plugins; markdown links never [[wikilinks]]; full-width pages; hide CLAUDE.md/AGENTS.md and code dirs), the native userIgnoreFilters exclude mechanism (and why .obsidianignore is a trap without a plugin), the exact .base YAML schema with filters/views/groupBy/summaries, the frontmatter-drives-the-table rule, and the omit-don't-guess discipline that keeps a generated table trustworthy.
---

# Obsidian vaults over git repos

Field-tested 2026-08-10 on the `hq` monorepo — repo root opened as a vault
over a cross-linked server/domain/cost inventory, with a Bases table of ~24
servers filterable by company, provider, cost and status.

## Oriol's standing preferences — honor these without asking

1. **Core plugins only. Never community plugins.** A fresh clone must work
   with zero per-machine setup. If something appears to need a plugin, find
   the core equivalent first — CSS snippets cover a surprising amount of
   what plugins are sold for. Do not vendor plugin code into the repo
   either. If a plugin still looks unavoidable, Oriol's bar is
   **>1k GitHub stars**, which in this ecosystem excludes almost
   everything: check before proposing, and expect to fall back to CSS.
2. **Markdown links, never `[[wikilinks]]`.** Wikilinks render as broken
   text on GitHub and for every non-Obsidian reader, including other agents.
3. **Full-width pages** — readable line length off.
4. **Hide agent instructions and code from the vault.** `CLAUDE.md` /
   `AGENTS.md` are read from disk by agents, not browsed; one per directory
   just pollutes search. Codebases (ansible roles, config mirrors) are noise
   in a docs vault.
5. Sensible defaults he did not object to: attachments in a dedicated
   folder, system trash, spellcheck off, `alwaysUpdateLinks` on.

## The vault config (commit these, ignore the rest)

`.obsidian/app.json` — the whole preference set:

```json
{
  "useMarkdownLinks": true,
  "newLinkFormat": "relative",
  "alwaysUpdateLinks": true,
  "readableLineLength": false,
  "showUnsupportedFiles": false,
  "attachmentFolderPath": "docs/attachments",
  "trashOption": "system",
  "spellcheck": false,
  "userIgnoreFilters": ["homelab/ansible/", "CLAUDE.md", "AGENTS.md"]
}
```

`.gitignore` — commit the shared settings, ignore per-machine state:

```gitignore
.obsidian/*
!.obsidian/app.json
!.obsidian/appearance.json
!.obsidian/core-plugins.json
!.obsidian/snippets/
```

**`.obsidian/*`, not `.obsidian/`.** Git cannot re-include a file whose
parent directory is excluded, so `.obsidian/` would make every `!` negation
dead. Same rule bites in `.obsidianignore` and in Bases-adjacent tooling.

Deliberately NOT committed: `workspace.json` (pane layout, per-machine),
`plugins/`, caches. Obsidian rewrites `.base` files and `app.json` as the
user clicks around — expect churn, and re-read before editing rather than
clobbering.

## Hiding things properly takes TWO native mechanisms

This is the single easiest thing to get wrong, and the docs you write about
it will be confidently false if you don't test it.

**`userIgnoreFilters` alone does NOT hide anything from the file
explorer.** It is Obsidian's native "Excluded files" (Settings → Files and
links) and it removes entries from **Search, Quick Switcher, graph and link
suggestions** — but excluded folders remain listed in the explorer, merely
dimmed. That is by design. Claiming otherwise in a README wastes the user's
time when they restart and see no change.

**`.obsidianignore` is a trap.** It is not native — only the "Ignore"
community plugin (`devxoul/obsidian-ignore`) reads it. Without that plugin
the file sits there looking authoritative and doing nothing.

So use both of these, and update both when adding an exclusion:

1. **`userIgnoreFilters`** in `app.json` — search, switcher, graph. Takes
   plain paths and simple patterns, **not** gitignore globs; list each
   occurrence explicitly (every `CLAUDE.md` path, not `**/CLAUDE.md`).
2. **A CSS snippet** in `.obsidian/snippets/*.css`, enabled via
   `enabledCssSnippets` in `appearance.json` — this is what actually
   removes rows from the explorer. Snippets are a **core** feature and both
   files are committable, so it stays zero-setup.

**Ready-made snippet: [`assets/hide-non-docs.css`](assets/hide-non-docs.css)** —
copy it to `<vault>/.obsidian/snippets/`, swap the placeholder paths, add
the name to `enabledCssSnippets`. It already covers build noise and
`CLAUDE.md`/`AGENTS.md`, and documents the selector syntax inline.

```css
/* folder: hide the title AND the sibling children, or contents render */
.nav-folder-title[data-path="homelab/ansible"],
.nav-folder-title[data-path="homelab/ansible"] + .nav-folder-children {
  display: none;
}
/* files by suffix, anywhere in the vault */
.nav-file:has(> .nav-file-title[data-path$="CLAUDE.md"]) { display: none; }
```

`data-path` is the vault-relative path: `=` exact, `^=` prefix, `$=`
suffix, `*=` contains.

### Vetting plugins when one seems unavoidable

Obsidian's ecosystem is small — a "popular" plugin is often <100 stars, and
a >1k-star bar rules out every hide/ignore plugin that exists (checked
2026-08: Hide Folders 71, Advanced Exclude 66, Explorer Hider 16, Ignore
7 — the last also unreviewed by Obsidian staff). Check stars and review
status **before** proposing one, especially for a vault containing
sensitive inventory:

```bash
gh api repos/<owner>/<repo> --jq '"\(.stargazers_count) stars | pushed \(.pushed_at[0:10])"'
```

When the bar can't be met, say so and reach for CSS — Explorer Hider's own
description admits it is "a little bit of auto-managed CSS", which is the
tell that you can do it natively.

## Bases: filterable tables over notes

Bases is a **core** plugin (Obsidian 1.9+), so it satisfies the no-plugins
rule. It renders any set of notes as a filterable, groupable, summable
table driven entirely by **YAML frontmatter**.

### The rule that decides whether this works

**A note without frontmatter is invisible in every view.** So the moment
you build a Base, you have taken on a contract: every future note of that
kind must carry the frontmatter. Enforce it by:

- Putting a fully-commented `_template.md` next to the notes, with every
  field and its allowed values.
- Documenting the schema in the repo's `CLAUDE.md`, not just the template —
  agents read that first.

### Omit, never guess

Structured data reads as fact in a way prose does not. A guessed value in a
table becomes truth the next time anyone looks. So:

- **Leave a field out** when you don't know it. A blank cell is honest.
- Carry a `specs_confirmed: true|false` flag when values may come from a
  vendor spec sheet rather than the real thing. On `hq` this earned its
  keep immediately: the SX65 spec sheet says 4×22 TB, the actual disks are
  4×20 TB.
- Keep units out of numeric fields (`monthly_cost: 122.33`, not
  `"€122.33"`) or sorting and Sum summaries break.
- Carry `currency` separately and **never sum across currencies** — one
  provider billing USD among EUR ones silently corrupts every total.
- Multi-value fields (a machine serving several tenants) are YAML lists.

### `.base` file schema

A `.base` file is YAML with five top-level keys: `filters`, `formulas`,
`properties`, `summaries`, `views`.

```yaml
filters:                      # global, applies to every view
  and:
    - 'type == "server"'
formulas:
  yearly: 'if(monthly_cost, (monthly_cost * 12).round(2))'
properties:                   # display config per property
  file.name:
    displayName: Server
  monthly_cost:
    displayName: €/mo
views:
  - type: table
    name: By company
    groupBy:
      property: scope
      direction: ASC
    filters:                  # view-specific, extends the global filter
      or:
        - 'kind == "vps"'
        - 'kind == "droplet"'
    order:                    # columns, in order
      - file.name
      - provider
      - monthly_cost
    sort:
      - property: monthly_cost
        direction: DESC
    summaries:
      monthly_cost: Sum       # per-group subtotals
    limit: 50
```

- Property references: `note.foo` or bare `foo`; `file.name`, `file.ext`,
  `file.mtime`; `formula.yearly`.
- Filter operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, plus
  `file.hasTag()`, `file.hasLink()`, `file.inFolder()`.
- Quote filter expressions so YAML doesn't eat the inner quotes:
  `- 'status != "done"'`.
- A global `filters` block plus a marker property (`type: server`) is more
  robust than `file.inFolder(...)` — files move, markers don't.

### Views worth building

Beyond "All", the views that get used are the ones that surface problems:
group by owner/company, group by provider, and filter views for
**needs-attention** (EOL OS, idle, no backups, unconfirmed specs). A table
that only lists things is a worse version of the folder; a table that
answers "what is wrong and what does it cost" earns its place.

### Validate before committing

A malformed `.base` silently shows nothing, and a broken frontmatter block
silently drops one row. Check both:

```bash
python3 -c "import yaml;d=yaml.safe_load(open('docs/servers.base'));print([v['name'] for v in d['views']])"
python3 -c "
import yaml,glob
for f in glob.glob('docs/servers/*.md'):
    t=open(f).read()
    if t.startswith('---'):
        try: yaml.safe_load(t.split('---',2)[1])
        except Exception as e: print('BAD', f, e)
"
```

Also assert the required keys are present and print per-group totals — a
total that looks wrong is usually a missing or double-counted row.

## Companion tooling

- **glow** for the terminal (`glow docs/`, `glow file.md`). This is what
  works over SSH, where Obsidian cannot help.
- GitHub renders the vault fine **because** links are relative markdown —
  another reason the no-wikilinks rule matters.
- Skip static-site generators (mdBook/MkDocs) for internal docs: they add a
  build step and a second source of truth for files that are read far more
  often by humans and agents directly than through a browser.
