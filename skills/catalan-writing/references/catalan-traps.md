# Catalan traps, with corrections

Working list. Add a row whenever a real draft is caught making the mistake, and
note where it came from — the point is to encode observed failures, not to copy
a grammar book.

## 1. The 2016 IEC diacritic reform

The Institut d'Estudis Catalans removed the diacritic from most homograph pairs
in 2016. Training corpora are full of pre-2016 text, so models still produce the
old spellings and they look right to anyone who learned before the reform.

**Only these 15 keep the accent**: `bé`, `déu`, `és`, `mà`, `més`, `món`, `pèl`,
`què`, `sé`, `sí`, `sòl`, `són`, `té`, `ús`, `vós` (plus their inflected forms,
e.g. `béns`, `déus`, `mans` is unaffected, `pèls`).

Frequent wrong survivors: ~~sóc~~ → **soc** · ~~dóna~~ → **dona** ·
~~vénen~~ → **venen** · ~~féu~~ → **feu** · ~~ós~~ → **os** · ~~mòlt~~ → **molt**
· ~~sòc~~ → **soc** · ~~véns~~ → **vens**.

LanguageTool `ca-ES` flags these, so this class is worth automating.

## 2. Software calques

The draft is Catalan; the thinking is English or Spanish release-note prose.

| Calque | Say instead | Why |
|---|---|---|
| publicar canvis | fer canvis / han arribat novetats | "publish changes" is deploy-speak |
| el sistema (et torna, envia, processa…) | name the product: *EnaCast recupera…* | vague agent, nobody says it |
| gestionar X | portar / administrar / fer servir | overused management verb |
| es dibuixa (una franja, un bloc) | surt / apareix | rendering metaphor leaking into UX copy |
| esperar la memòria cau | fins ara podia trigar hores a sortir-hi | names infrastructure instead of experience |
| realitzar una acció | fer | bureaucratic |
| de forma automàtica | sol / soles (*s'aturen soles*) | heavier than Catalan needs |
| en cas que vulguis | si vols | conditional bloat |
| a nivell de | pel que fa a / en | castellanism + jargon |

## 3. Castellanismes that survive a spell check

- **el mateix / la mateixa** as an anaphoric pronoun → repeat the noun, or use
  `el`, `-lo`, `hi`, `en`. (*"puja la imatge i desa la mateixa"* is Spanish.)
- **degut a** as a causal preposition → *a causa de*, *per*, *perquè*.
  (`degut` is only a participle: *un import degut*.)
- **tenir que** → *haver de*. **hi ha que** → *cal*.
- **donar-se compte** → *adonar-se*.
- **tamany** → *mida*, *grandària*. **apretar** → *prémer* (a button), *estrènyer*.
- **enterar-se** → *assabentar-se*. **despedir** → *acomiadar*.
- **sino** → *sinó* (but) vs *si no* (if not) — models mix these two.
- **inclús** → *fins i tot*. **dons** → *doncs*, and *doncs* is not *perquè*.

## 4. Pronoms febles and apostrophation

- Enclitic hyphens are dropped or doubled: *retallar-la*, *saltar-te*,
  *reaprofitar-ho*, *fes-ho*, *dona'm*, *porta'ls-hi*.
- `hi` and `en` are the ones a Spanish-shaped draft forgets:
  *no **hi** ha res*, *l'interruptor **hi** continua*, *no **en** queda cap*.
- **No apostrophe before s + consonant** ("s líquida"): *de streaming*,
  *el striptease*, *un stand*. Models write *d'streaming* constantly.
- Apostrophe before a vowel or h: *l'editor*, *d'imatges*, *l'hora* — but
  *la una*, *la ira*, *la host* keep the article where stress rules say so.
- Feminine before unstressed i-/u-: *la imatge* but *l'illa*.

## 5. Register and address

- Products aimed at small organisations use **tu**, not *vostè* — check the
  existing catalog and stay consistent inside one surface. Mixing is the tell.
- Sentence case in headings and buttons for ca/es/fr. Quoted UI labels are the
  exception: they keep whatever case the screen shows.
- Catalan tolerates fewer possessives than English: *la seva adreça no canvia*
  is fine, but *obre el teu episodi al teu editor* should lose one.

## 6. Numbers, dates, typography

- Decimal comma, thousands with a thin space or point per house style; `%` is
  written attached in Catalan/Spanish (*50%*) and spaced in French (*50 %*).
- Dates spelled out: *l'1 d'octubre*, *el 14 de setembre* (article + `de`/`d'`).
- Quotation marks: Catalan and Spanish use « » or " " per house style; French
  uses « » **with** non-breaking spaces inside, and a non-breaking space before
  `: ; ! ?`. This is the most common French typography miss in an LLM draft.
- Ellipsis, arrows and middots copied from a UI string must stay exactly as the
  UI writes them.

## 7. Terminology that is usually decided, not translated

Check the project catalog first; these are the common house answers in Oriol's
Catalan surfaces:

| Concept | Catalan used | Note |
|---|---|---|
| newsletter | **novetats** | never *butlletí* for a radio: that is the news bulletin |
| widget (embeddable) | **giny** | Softcatalà term, used in EnaCast docs |
| cookies | **galetes** (ca/es), **témoins** (fr-CA) | |
| upload | **pujar** (ca/es), **téléverser** (fr-CA) | |
| podcast | **pòdcast** (ca), **balado** (fr-CA) | |
| radio station | **emissora** | *ràdio* is the medium |
| chat | **xat** (ca), **clavardage** (fr-CA) | |
| grid (schedule) | **graella** | |
