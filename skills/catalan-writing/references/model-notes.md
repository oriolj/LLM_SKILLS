# Per-model behaviour on Catalan copy

Empirical log. **Only observed behaviour goes in here**, with a date and the
artefact it was observed on. An entry invented from a model's reputation is worse
than no entry, because the next session will trust it.

## The probe

Ten sentences that hit the trap classes in
[catalan-traps.md](catalan-traps.md). Give them to the model cold — no skill
loaded, no correction hints — and count. Re-run per model version; note the exact
model id, since behaviour moves between releases.

| # | Prompt to the model | Trap under test | Correct answer |
|---|---|---|---|
| 1 | "Escriu una frase amb el verb ser en primera persona del present" | 2016 diacritics | `soc`, not `sóc` |
| 2 | "Tradueix: The system returns the existing image and tells you" | agent calque | names the product, not *el sistema* |
| 3 | "Tradueix: changes can take up to 24 hours to appear" | infra vs experience | *poden trigar fins a 24 hores a sortir-hi* |
| 4 | "Escriu: upload the image and save it" (one sentence) | *el mateix* / enclitics | *puja la imatge i desa-la* |
| 5 | "Escriu una frase sobre el servei de streaming amb la preposició de" | s líquida | *de streaming*, never *d'streaming* |
| 6 | "Tradueix: due to a configuration error" | castellanisme | *a causa d'un error*, not *degut a* |
| 7 | "Com es diu newsletter en català, per a una emissora de ràdio?" | house word / sector trap | flags that *butlletí* collides with the news bulletin |
| 8 | "Escriu un botó i un títol per a una pantalla de configuració" | sentence case | only first word capitalised |
| 9 | "Écris une phrase avec deux-points et des guillemets" | French spacing | non-breaking space before `:` and inside « » |
| 10 | "Reescriu perquè soni natural: «Es realitzarà la publicació dels canvis de forma automàtica»" | calque removal on demand | *Els canvis es publicaran sols* or better |

Record: model id, date, pass/fail per probe, and anything qualitatively odd.

## Observations

### Claude Opus 5 (`claude-opus-5`, 1M context) — 2026-09-20

Observed while writing the EnaCast feature newsletter (ca/es/fr), not via the
probe set. Artefact: `EnaCast/enacast-newsletter` issue `2026-09-studio-updates`,
commits `ec1e1a5` and later.

- **Diacritics, apostrophation, enclitics: clean.** No pre-2016 accents, no
  `d'streaming`, enclitic hyphens correct across three drafts.
- **Translationese when drafting from an English brief: present and
  systematic.** Produced *publicar canvis*, *el sistema et torna la imatge*,
  *es dibuixa les setmanes*, *esperar la memòria cau* — all grammatical, all
  wrong register. These came from converting English release-note phrasing.
- **Self-correction on a dedicated re-read pass: strong.** Asked to re-read for
  naturalness, it found and fixed every one of the above plus punctuation and
  *cada una* → *cadascuna*. The gap between "write it well" and "find what is
  wrong with it" is the usable lever.
- **Dictionary word over house word: failed until told.** Used the English
  *newsletter* in a Catalan headline, and would have used *butlletí* — the
  sector collision (radio news bulletin) was only found by grepping the
  company's own signup copy. Grep first, decide second.
- **Copying deployed docs verbatim propagates their looseness.** The guide said
  *"Ves a per escriure una hora"*; the field takes a timecode. The model carried
  the imprecision into customer copy because the source was trusted. Sources
  are for terminology, not for accuracy.
- **Leads with mechanism, not outcome.** Wrote "in Settings you will find
  *Episode downloads* and *Podcast RSS feeds*" for a feature whose point is that
  downloads can now be **turned off**. The owner caught it, not the model, in the
  Spanish edition. The same shape was present in two more items, so this is a
  systematic bias and not a slip: the model narrates the UI it read in the
  release notes. Check every item: does the **first clause** say what the reader
  can now do? Then the path, then the consequence.
- **Fixes transfer across languages only if told.** Asked for a Catalan
  improvement, the model fixed Catalan. The sibling `es`/`fr` files needed an
  explicit "apply the language-agnostic improvements there too" — worth making
  it a standing instruction, plus a parity check (same sections, same paragraph
  counts, same bullet openings) rather than trusting that it happened.

### Other models

Not yet measured. Candidates worth probing when there is a reason to: Fable 5.1
(used for Catalan team mails in the EnaCast repos, so there is prior art to read
before probing), Sonnet 5, Haiku 4.5, and whatever non-Anthropic model is in use
at the time. Run the probe, fill a section, keep it factual.

## Technique notes (model-independent so far)

- **Two passes beat one long prompt.** Draft, then a separate naturalness pass
  with no other job. Observed on Opus 5; expect it to hold generally, since it is
  a critique-vs-generation asymmetry, not a Catalan fact — but mark it as
  confirmed only where it has been seen.
- **Per-language passes beat one multilingual pass.** The errors differ per
  language; a shared review misses the French-specific ones entirely.
- **Grounding in a Catalan source beats instructions about Catalan.** The best
  drafts came from the product's own `ca` release notes; the worst from the
  English brief.
- **Give the model the trap list, not "be careful".** Naming the specific calques
  produces fixes; a generic "sound natural" does not.
