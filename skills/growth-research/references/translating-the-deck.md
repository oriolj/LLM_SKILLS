# Translating the deck into another language

When the user asks for the deck (or the final PDF) in another language — e.g. *"make a
Spanish copy"*, *"traduce esto al español"*, *"can we get a German edition"* — produce a
**language mirror** of the repo and render a localized PDF from it. The markdown is the
source of truth, so translating the markdown + localizing the PDF chrome is all it takes.
`build_pdf.py` reads an optional `pdf.config.json`, so **no code edits are needed** for a
new language.

This was first done for a Spanish (Spain / es-ES) edition; the procedure below is what
worked, including the gotchas.

---

## Procedure

### 1. Mirror the repo into a language folder
Create `<workdir>-<lang>/` (e.g. `growth-research-plugin-b2b-es/`) with the same
`research/<topic>/` subfolders. You only need the **markdown** there — the PDF reads
markdown, not JSON/xlsx. (Optionally also copy/translate the JSON if you want localized
xlsx/HTML too; usually skip — see "What not to translate" below.)

### 2. Fan out one translation agent per markdown file, in parallel
Send a single message with N `Agent` calls (`general-purpose`, `run_in_background: true`),
one per `GROWTH_RESEARCH.md` + each `research/<topic>/<topic>.md`. **Have each agent Read
its source file itself** (pass the absolute path) rather than pasting file contents into
the prompt — keeps the parent's context clean and parallelizes the I/O.

Translation-agent prompt template (adapt language + per-file path):

> You are a professional `<lang>` (e.g. Spanish, Spain / es-ES) translator. Use the Read
> tool to read this file in full: `<ABSOLUTE_PATH>`. Translate its ENTIRE contents into
> natural, professional `<lang>` in a business/marketing-research register.
>
> PRESERVE EXACTLY (do not translate, do not reformat): all Markdown structure (heading
> levels; tables — keep the SAME number of columns and the `|---|` separator rows intact;
> lists; **bold**/*italic*; blockquotes; inline/fenced code; `---` rules; `[text](url)`
> links); URLs, emails, @handles, subreddit names (r/…); brand/product/company/person/
> event/publication names; numbers, prices, currency symbols, %, dates, ISO codes, version
> numbers; the surface tag `Plugin (B2B)`; canonical role/status labels (PARTNER, CHANNEL,
> COMPETITOR, RED FLAG, etc. — translate enums like In force / High only where they read
> as prose or in summary tables, per the slice); acronyms (LMS, CRM, SaaS, ICP, TCO, GDPR…
> — keep the acronym, gloss on first use if natural).
>
> DO translate: all prose, sentences, table HEADER labels and descriptive cells, section
> titles, list items, "why it matters" notes. Use `<lang>` conventions and sentence case
> for headings. Translate the first H1 too.
>
> Output: return ONLY the full translated Markdown in a single ```markdown fenced code
> block. No commentary before/after. Do NOT write any files.

For the **regulatory** slice add a glossary so enums/legal names stay consistent (e.g. es:
In force→En vigor, Phased rollout→Despliegue por fases, Buyer→Comprador, GDPR→RGPD with
acronym in parentheses). For **competitor_intel** translate the threat-level table labels
(High→Alta…). For **pricing** translate billing_model/confidence values.

### 3. Persist each translation (extract the fenced block + clean entities)
Extract the ```markdown block from each agent's transcript and write it to the mirror.
Two gotchas, both handled by the snippet below:

- **Nested code fences.** `GROWTH_RESEARCH.md` (and any doc with a repo-tree block) contains
  ` ``` ` fences *inside* the outer ` ```markdown ` wrapper. Take from the FIRST
  `` ```markdown `` to the LAST `` ``` ``, not the first closing fence.
- **Over-escaped HTML entities.** Translators frequently emit `&amp;`, `&lt;`, `&gt;` for
  literal `& < >` (especially around code/trees/`&&`). Clean them or they render literally
  in the PDF.

```python
# persist_translation.py <transcript.jsonl> > research/<topic>/<topic>.md
import json, sys
cands = []
def walk(o):
    if isinstance(o, str):
        (o.find("```markdown") >= 0) and cands.append(o)
    elif isinstance(o, dict): [walk(v) for v in o.values()]
    elif isinstance(o, list): [walk(v) for v in o]
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if line:
        try: walk(json.loads(line))
        except json.JSONDecodeError:
            "```markdown" in line and cands.append(line)
s = max(cands, key=len)
start = s.index("\n", s.index("```markdown")) + 1
out = s[start:s.rindex("```")].rstrip() + "\n"
for ent, ch in {"&amp;":"&","&lt;":"<","&gt;":">","&quot;":'"',"&#39;":"'","&apos;":"'","&nbsp;":" "}.items():
    out = out.replace(ent, ch)
sys.stdout.write(out)
```

Sanity check after writing: `grep -l '&amp;\|&lt;\|&gt;' research/*/*.md GROWTH_RESEARCH.md`
should return nothing.

### 4. Drop a `pdf.config.json` in the mirror to localize the PDF chrome
No script edits — `build_pdf.py` merges this over the English defaults. Translate the
chapter titles, cover text, "Contents"/"Chapter", footer, and month names. Example
(Spanish), abbreviated:

```json
{
  "product": "GuitarGiro Subscriptions",
  "output": "GuitarGiro-Investigacion-de-Crecimiento-ES.pdf",
  "rows_from": "../growth-research-plugin-b2b",
  "chapter_titles": {
    "__exec__": "Resumen ejecutivo y plan de acción",
    "pricing": "Precios y empaquetado",
    "competitor_intel": "Inteligencia competitiva",
    "partners": "Ecosistema de socios y canales",
    "magazines": "Revistas y prensa especializada",
    "conferences": "Conferencias y eventos",
    "influencers": "Influencers y líderes de opinión (KOL)",
    "regulatory": "Vientos de cola regulatorios"
  },
  "strings": {
    "kicker": "Investigación de Go-to-Market",
    "subtitle": "Informe de investigación de crecimiento — dónde anunciarse, con quién asociarse, quién mueve la opinión, cómo es la competencia, qué normativas abren ventanas y qué precio poner.",
    "contents": "Contenido", "chapter": "Capítulo",
    "footer_suffix": "— Investigación de crecimiento",
    "slices_word": "áreas de investigación", "rows_word": "filas",
    "generated": "Generado el", "edition_note": "Edición en español (España)",
    "date_template": "{day} de {month} de {year}",
    "months": ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
  }
}
```

`rows_from` is optional — point it at the source repo so the cover's row count is right
even though the mirror ships markdown only.

### 5. Render
```bash
python3 scripts/build_pdf.py        # picks up pdf.config.json automatically
```
Spot-check the cover + contents page render with correct accents and localized labels.

---

## Lessons learned (from the es-ES run)

- **One agent per file, parallel, agents Read their own file.** 9 files translated
  concurrently in ~the time of the slowest. Don't paste file bodies into prompts.
- **Translators over-escape `& < >` to HTML entities** — always run the entity cleanup in
  step 3, or `&amp;`/`&lt;`/`&gt;` show up literally in tables and trees.
- **Nested ``` fences** in `GROWTH_RESEARCH.md`/repo-tree blocks break naive extraction —
  span first `` ```markdown `` to last `` ``` ``.
- **What NOT to translate:** URLs, @handles, r/sub names, brand/person/event names, prices,
  numbers, dates, ISO codes, the `Plugin (B2B)` surface tag, canonical role labels
  (PARTNER/CHANNEL/COMPETITOR/RED FLAG). DO translate prose + table headers + descriptive
  cells + enum labels in summary tables.
- **JSON sidecars / xlsx / html are usually left in English.** The PDF is built from
  markdown, so the translated deck is complete without them. Translate the JSON only if the
  user specifically wants localized spreadsheets/explorer (then re-run build_xlsx/build_html
  in the mirror).
- **Localize the PDF via `pdf.config.json`, never by forking the script.** Keeps one builder
  for all languages.
- **Length drift:** Spanish ran ~10% longer than English (71 → 78 pages). Expect a few
  extra pages in Romance languages; layout handles it (page-break-before per chapter).
- **Keep the mirror as a sibling folder** (`<workdir>-<lang>/`). The markdown there is the
  language's source of truth; commit/treat it like the primary repo.
