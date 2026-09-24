# Vision features — benchmarking image-in, structure-out LLM calls

Photo → structured analysis (Panotxa: dish photo → identification, portion,
calories, macros, composition, processing, a 0–100 quality score and tips; menu
photo → items with boxes). Everything in the main skill applies; this file is what
changes when the input is an image.

## Freeze the exact bytes the model saw

- Production usually preprocesses (Panotxa: Pillow downscale to ≤ 768 px long edge,
  JPEG q90 — one vision tile — in `encode_image_for_gemini`). Freeze the image
  **after** that step, through the same function, and store its sha256 in the item.
  Re-encoding at replay time with a different Pillow version changes the input.
- Store images as files next to `items.jsonl` (`assets/<item-id>.jpg`), never base64
  inside JSONL (diffs and git history explode).
- The resolution is part of the experiment: a candidate may do better at 1,536 px
  but cost 4 tiles. Bench the preprocessing as a variant (`--image-size`) rather
  than changing it silently.

## Whose photos

User photos are personal data (Panotxa: public-read objects at unguessable URLs on
B2, traces in Langfuse carry the base64 image with the user id). Before freezing
any user photo into a dataset:

- prefer **own and licensed photos** (Panotxa `scan-dataset-test/` mixes Oriol's
  photos with Wikimedia Commons ones, licences in `attribution.json`);
- user photos only when the product's privacy policy covers internal quality
  evaluation, stored in a **private** repo or restricted bucket (never in a public
  repo, never in an image — `.dockerignore`), with the source object id and a
  deletion path: when a user deletes their account, their dataset items go too
  (record the user id in `meta`, never in the file name);
- never send user photos to a provider the account's data settings do not already
  allow for production (OpenRouter account privacy settings, zero-retention
  endpoints) — a bench is not a reason to widen where photos go.

Decisions about user data are Oriol's; put them in the project's `USER_TODO.md`.

## The provider seam

Vision features in the estate call the vendor SDK directly (Panotxa:
`google-genai` `generate_content` with an inline `Blob`, no OpenRouter). To bench
another vendor:

1. Add `model=` to the production function (default = the feature table), and a
   thin transport: `google/*` models keep the native SDK path; anything else goes
   through OpenRouter with the image as `{"type": "image_url", "image_url": {"url":
   "data:image/jpeg;base64,…"}}` and the same system/user text.
2. Keep JSON handling identical across both paths (same parser, same validators,
   same schema). Better: fix the schema first — Panotxa has no `response_schema`
   and 3.6 % of responses were invalid JSON; a bench on unconstrained JSON measures
   the parser as much as the model.
3. Compare same-vendor candidates first (`gemini-3.5-flash-lite` vs
   `gemini-3.8-flash`, thinking on/off) — no transport risk — then cross-vendor.

## Deterministic checks for image analyses

- parses; required keys present (the project's own prompt contract, e.g. Panotxa
  `check_prompt_contract`, lists them);
- `is_food` false on the negative items (a shoe, a menu, a blurry photo) and no
  nutrition invented for them;
- numbers in range (kcal 0–3,000 per dish, percentages 0–100, scores 0–100);
- internal consistency: 4·protein + 4·carbs + 9·fat within ±20 % of kcal;
  composition percentages sum ≤ 100; portion grams plausible for the dish;
- boxes as fractions in [0,1], non-degenerate, one per detected dish — check the
  RAW answer, before the product's repair: 21-28 % of Gemini answers mix
  conventions, and `gemini-3.8-flash` answers per-mille with the right/bottom
  EDGES in `w`/`h` (Sprite `x 265, w 296`). A repair that rescales cannot tell an
  edge from a size, so the boxes silently cover half the photo. Ask for Gemini's
  native `box_2d: [ymin, xmin, ymax, xmax]` on 0-1000 and convert in code, or
  enforce a schema;
- language of the free-text fields = the requested language;
- `finish_reason` not a length cut.

## Judging an image output

- The judge gets **the same image bytes** + the same text context (meal type, diet,
  intolerances, the user's note or correction) + the post-processed output.
- Dimensions that worked as a starting point for food analysis:
  **identification** (are the dishes and main ingredients what the photo shows),
  **portion** (plausible for what is visible, deduct by ratio of error),
  **nutrition** (calories and macros plausible for the identified food and portion),
  **quality verdict** (score and explanation consistent with the visible food and
  the product's scoring rules — give the judge the rules), **tips** (actionable,
  specific to this plate, not generic), **language**.
- Claim check on the explanation and tips with the image as the source: "the
  plate includes legumes" must be visible.
- Judges cannot weigh food either. For numbers, the judge scores plausibility; only
  labels measure accuracy. Say so in the notes next to every nutrition number.

## Ground truth that is worth collecting

Cheap and decisive, in this order:

1. **Negatives and edge cases** — not food, a menu, a drink only, leftovers, a
   shared plate, multiple dishes: labels are yes/no and the failures are the ones
   users notice.
2. **Dish identity** — the list of dishes per photo (set F1).
3. **Expert quality score** — the product's own 0–100 by a professional
   (Panotxa: `N.nutritionist.json`, one rater, 15 photos). Use it to validate the
   judge's quality dimension, then let the judge score the rest.
4. **Weighed portions** — expensive; only for a small calibration set.

## Candidates through OpenRouter: what went wrong (Panotxa 2026-09-24)

- Open-weight vision models are served by third-party providers of very uneven
  speed: `gemma-4-31b-it` 32 s p50 / 83 s p95 on a 5k-token photo prompt.
  `mistral-small-2603` hit provider 429s at 4 workers; run it with `--workers 1`.
  Transport failures must not be cached as results; rerunning fills them.
- A model's DEFAULT reasoning can dominate: `qwen3.8-flash` spent ~2.9k reasoning
  tokens per photo, truncated, and returned lists where objects were expected
  (production crashed with `TypeError`, not its clean error). Bench `none` as well
  as the default.
- A text-model winner does not transfer to vision: `gpt-6-luna` (the EnaCast
  winner) identified food worse and agreed less with the nutritionist than
  flash-lite, at 2.4× its latency.

## Cost and latency are part of the score

Vision calls are dominated by image tokens (fixed per tile) — output tokens and
thinking tokens decide the difference between models. Report per item: input
tokens (image share), output tokens, reasoning tokens, $/call, **latency p50/p95**.
A photo analysis is a user waiting on a spinner (Panotxa's progress bar assumes
7 s): a model that is 5 points better and 6 s slower is a product decision, not a
bench win.
