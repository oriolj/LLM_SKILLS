# Judging — rubrics, panels, claim checks, ground truth, calibration

What a score means is decided here. Most wrong conclusions in the EnaCast benches
came from the judging setup, not from the models.

## Order of preference for a signal

1. **Deterministic checks** — free, exact, never drift: parses, schema, lengths,
   counts, ranges, language, "every quoted string appears in the source",
   bounding boxes inside the image, macros consistent with calories (4/4/9 kcal/g).
2. **Ground truth** when humans labelled it — the only thing that measures
   accuracy rather than plausibility. Metrics per type below.
3. **Claim check** for anything that states facts about a source — atomic claims,
   each verified against the source. Gives a hallucination rate, which is the
   number that moved every decision in 2026-09.
4. **Rubric judges** for everything that needs taste: usefulness, tone, language
   quality, whether the output does the job.

Blend them per dimension (e.g. faithfulness = mean(judge faithfulness,
100 × (1 − hallucination rate))), weights per feature, format checks 10 %.

## Writing a rubric

- One dimension = one question a reviewer can answer from INPUT + OUTPUT. Typical:
  faithfulness (nothing the input does not support), accuracy (what is said is
  right), language (correct, natural, the requested language), usefulness (does
  the job for the user named in the description), format/structure, plus
  feature-specific ones (sections placed where topics start; grounding of each
  glossary term).
- **Start at 100 and deduct**, with the deduction sizes written down ("−15 per
  invented fact, −5 per overstated adjective, floor 0"). Absolute scales without
  deductions drift between judges and between runs.
- **Proportional deductions for long list outputs** (a 60-line glossary): deduct per
  share of bad lines, not per line — per-line deductions floored every item at 0
  and the dimension stopped discriminating (enacast glossary rubric v2).
- **Say what is NOT an error**, especially deliberate product choices. The entity
  extractor excludes the article's own town and passing mentions on purpose;
  rubric v1 counted them as misses and made the production model look worse than a
  candidate that ignored the rule (recall 38 % vs 70 % flipped to 89.3 vs 88.6 in v2).
- Ask the judge to **list every invented fact and error it deducted for** (in the
  input's language). The lists are what you read, grep and quote in the notes;
  a bare number cannot be audited.
- Every rubric change bumps `rubric_version`; cached judgements with an older
  version are redone; rows judged by different rubric versions are not compared.

## The judge must see what the writer saw

Everything the production prompt gives the model — glossary, client notes, user
profile, diet and intolerances, previous corrections, the image — goes to the
judge too, labelled as context. Otherwise correct background facts count as
invented: in enacast-ai ~30–45 % of production's "invented" deductions were
glossary facts the judge had never been shown. Say how context may be used
("standing background, spelling and roles; never evidence that this episode
covers it"). Version it (`context_version`) and re-judge older results.

Give the judge the **post-processed output** — what users would see after the
production checks (quote repair, validators, clamping) — not the raw completion.

## The panel

- **Same panel for every row.** A judge never scores its own model's family (it
  is lenient to itself), so a Gemini judge silently drops out of the Gemini rows
  and the panel changes between rows. Pick judges from vendors the bench does not
  compare, or accept that the panel is fixed and exclude nothing.
- Default 2026-09: `openai/gpt-6-sol` on every item + `anthropic/claude-opus-5.5`
  on a subset (first 20 per feature) for cost. Sol 6 and Opus 5.5 agree closely;
  `gemini-3.8-flash` as a judge was markedly lenient (overall 90–97 where Sol/Opus
  gave 69–88 on the same outputs) — use it only as a cheap extra, never alone.
- All three accept images (OpenRouter `input_modalities` include `image`, checked
  2026-09-24), so vision features keep the same panel.
- Judges run at temperature 0 with low reasoning; blind (no model name in the
  prompt); strict JSON schema with the dimension names as required integer fields.
- **Absolute numbers depend on the panel.** Replacing a judge (Fable → Opus, Sol
  5.6 → Sol 6) moved every row; only compare rows judged by the same panel, and
  re-judge the baseline (`--rescore`) whenever the panel changes.

Watch the judges' known biases: **length** (longer summaries score higher on
"usefulness" — check the per-dimension numbers, not only global), **position** in
pairwise comparisons (randomise order), **self-preference** (above).

## Claim check (hallucination rate)

For outputs that make factual statements about a source (summaries, articles,
headlines, insights about the user's week, a nutrition explanation):

1. Extract ≤ 40–60 atomic, checkable claims from the output with a cheap model
   (who / what / numbers / dates / places / names / outcomes; skip opinions).
2. Verify all claims in one call with a strong model against the source:
   `supported | unsupported | contradicted` + the shortest deciding quote. Be strict:
   a plausible detail not in the source is unsupported.
3. Per item: hallucination rate = (unsupported + contradicted) / claims;
   **clean** = zero bad claims. Per run: mean rate and clean-output share. The
   clean share is what a customer experiences ("47 % of articles with nothing
   invented, was 3 %").

For image sources the verifier gets the image as the source, and "supported"
means visible in the photo (or stated in the user's own note).

## Ground-truth metrics

| Output type | Metric |
|---|---|
| number (kcal, grams, a 0–100 score) | MAE, share within tolerance (±15–25 % for estimates), Pearson/Spearman vs the expert |
| category (meal type, NOVA group, is_food) | accuracy, confusion matrix; negatives (not food) matter as much as positives |
| set (dishes on a plate, entities, tags) | precision / recall / F1 after normalising names (casefold, accents) and a fuzzy match |
| boxes | IoU ≥ 0.5 match rate; boxes within [0,1] as a deterministic check |
| text span (a quote) | exact / near-exact against the source after normalisation |

**Model-generated "expected" values are not ground truth.** A baseline written by
the production model (Panotxa `food-dataset-test/*.json`, produced by
`--update-expectations`) detects drift from that model and nothing else — a better
model scores worse on it. Keep them as a regression signal, label them so, and
build accuracy on human labels only.

Scarce expert labels (Panotxa: one nutritionist, 15 dish-quality scores) are best
spent **calibrating the judges**: if the judge's quality score correlates with the
expert's, the judge can score the unlabelled majority.

## Humans in the loop

- Read ten outputs of every new row by hand before believing a number, and the
  ten items that moved most between two rows (`bench compare`).
- Once in a while promote a run to blind human voting (enacast-ai: bench promote →
  experiment in the production admin → staff vote without model names) and track
  judge/human agreement per rubric version.
- A human verdict overrides a judge; a disagreement pattern is a rubric bug.

## Noise

Differences under ~2 global points are noise until a repeat run confirms them.
Small datasets (16 photos) are worse: report per-item results, not only means, and
do not declare a winner on a 1-point mean difference.
