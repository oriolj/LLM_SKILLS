---
name: catalan-writing
description: Write Catalan (and its Spanish/French siblings) that sounds like a person wrote it, not like a translation — for customer emails, newsletters, UI strings, landing pages and docs. Covers the generate-then-re-read method that actually removes translationese, the calque and barbarism blacklist, the 2016 IEC diacritic reform LLMs still get wrong, pronoms febles and apostrophation traps, the house-lexicon rule (use the word the product already uses, never the dictionary word), verification with LanguageTool/Softcatalà and a quoted-label checker, and a per-model log of what each LLM does badly. Use when writing or reviewing anything a Catalan speaker will read, when copy "sounds translated", when choosing terminology for a ca/es/fr catalog, or when the user mentions català, Catalan copy, translationese, castellanismes or Softcatalà.
---

# Writing Catalan that does not sound translated

Catalan copy produced by an LLM is usually **grammatical and wrong**: every word
is a valid Catalan word, the syntax is Spanish or English underneath, and the
terminology is the dictionary's rather than the product's. It passes a spell
check and a quick read, then a native reader feels it in the first sentence.

This skill is about removing that. It assumes the facts are already settled —
getting the content right is a different job.

## The method that works

1. **Write from Catalan sources, do not translate.** If a Catalan version of the
   material exists — the product's `ca` catalog, Catalan release notes, an
   existing Catalan page — draft from that, not from the English or Spanish
   brief. Translating an English draft produces English syntax wearing Catalan
   words, and no amount of "write natural Catalan" in the prompt fixes it,
   because the model is anchored on the sentence it is converting.
2. **Generate, then re-read as a separate pass.** Models are much better at
   *finding* translationese than at *not producing* it. Finish the draft, then
   start a fresh pass whose only job is: "read this aloud; what would a native
   speaker not say?" The second pass reliably catches what the first pass wrote.
   Do the pass **per language** — a fix in `ca.md` is not a fix in `es.md`.
3. **Say it out loud.** The test is not "is this correct" but "would a person say
   this". Rewrite anything that fails, even when it is literally correct.
4. **Use the house word, not the dictionary word.** See below — this is the
   single highest-value rule and the easiest to get wrong.
5. **Verify the parts that are checkable** (quoted UI labels, spelling,
   diacritics) with a script, not with judgement. See *Verification*.

## The house word beats the dictionary word

Terminology comes from **what the product and the company already say**, in this
order: the app's `ca` catalog → the public site/docs → the dictionary. A correct
translation that nobody in the company uses is wrong.

Worked example that cost a real rewrite (EnaCast, 2026-09-20): the newsletter
headline said *"des de la darrera newsletter"*. The dictionary answer for
newsletter is **butlletí** — and it is a trap: to a radio station, *butlletí* is
the **news bulletin** they broadcast every hour. The company's own signup page
says *"Novetats per email"* and *"Subscriure'm a les novetats"*, so the house
word is **novetats**. Both the anglicism and the dictionary word were wrong; the
right answer was sitting in the product.

Before choosing any term, grep the catalogs:

```bash
grep -rn "the concept" path/to/messages/ca.json path/to/site/src/i18n/ca.*
```

Sector words carry this risk most: a word that is generic in one industry is
occupied in another. Check what the *reader's* trade means by it.

## Quoted UI labels are quoted, never translated

When copy tells someone to click something, the string must be **byte-identical
to what the screen shows**, even when it breaks the style guide (menu entries are
often title-cased where the style guide says sentence case). Translating a label
sends the reader looking for a button that does not exist.

Make it checkable rather than promising to be careful — extract every bolded
span and require it to exist in the catalog or the deployed docs:

```python
labels = [b for b in re.findall(r"\*\*(.+?)\*\*", body) if len(b) <= 40]
unverified = [b for b in labels if norm(b) not in catalog_values and norm(b) not in deployed_docs_text]
```

On the EnaCast newsletter this runs at 153/153 verified across ca/es/fr and has
caught nothing yet — which is the point: it is cheap and it makes "I copied the
labels" a fact instead of a claim.

## Traps, calques and the diacritic reform

Full list with corrections: [references/catalan-traps.md](references/catalan-traps.md).
The four that show up in almost every LLM draft:

- **Software calques**: *publicar canvis*, *el sistema*, *gestionar*, *es
  dibuixa*, *esperar la memòria cau*. Say what happens to the reader instead:
  *han arribat unes quantes novetats*, *EnaCast recupera la imatge*, *fins ara
  podien trigar hores a sortir-hi*.
- **The 2016 IEC diacritic reform**: models trained on older corpora still write
  *sóc*, *dóna*, *vénen*, *féu*. Only **15** diacritics survive (bé, déu, és, mà,
  més, món, pèl, què, sé, sí, sòl, són, té, ús, vós). Everything else lost it.
- **Castellanismes that look native**: *el mateix* as a pronoun, *degut a*,
  *tenir que*, *donar-se compte*, *tamany*, *apretar*.
- **Apostrophation**: no apostrophe before s + consonant (*de streaming*, *el
  striptease*), and the enclitic hyphens (*retallar-la*, *saltar-te*,
  *reaprofitar-ho*) that models drop or double.

## Verification

- **[LanguageTool](https://github.com/languagetool-org/languagetool)** (15k
  stars, LGPL) with `language=ca-ES` **is** the Softcatalà corrector engine —
  [softcatala.org/corrector](https://www.softcatala.org/corrector/) states it
  runs on LanguageTool, and the Catalan rules are maintained by Softcatalà
  people. Self-host it (`docker run -p 8010:8010 erikvl87/languagetool`) and
  `POST /v2/check`; the same server covers `es` and `fr-FR`/`fr-CA`. Softcatalà
  itself exposes no public API.
  - Run it **report-only, on the prose outside quoted labels**. Quoted product
    labels violate prescriptive rules on purpose, so an unfiltered run produces a
    permanent ignore list nobody maintains.
  - Do not paste unreleased customer copy into the public `api.languagetool.org`
    — that publishes it to a third party. Self-host or skip.
- **The label checker** above, which is the one that catches the expensive error.
- Neither tool judges naturalness. That is step 2 of the method, and it stays
  human-shaped.

## What does not work

- *"Write in natural Catalan"* in the system prompt, with an English source in
  front of the model. It changes almost nothing.
- Translating es → ca. Vocabulary comes out fine and the syntax stays Spanish
  (word order, *el mateix*, periphrasis, possessives where Catalan uses `hi`/`en`).
- Asking for all three languages in one pass. Quality drops on languages 2 and 3
  and the errors are different in each.
- A style rule written down once and never checked. If it matters, it needs a
  re-reading pass that is a step in the workflow, or a script.

## Per-model behaviour

Different models fail differently, and the difference is worth tracking rather
than guessing. The log and the probe protocol live in
[references/model-notes.md](references/model-notes.md).

**Rule for that file: only write down what was observed, with the date and the
artefact.** Do not fill it in from intuition about a model's reputation — a wrong
entry there is worse than an empty one.
