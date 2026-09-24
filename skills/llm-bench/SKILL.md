---
name: llm-bench
description: Build and run an offline LLM benchmark for any project that calls LLM APIs (text or vision) — frozen real inputs, replay of the production function with any candidate model / reasoning effort / prompt, LLM judges plus deterministic checks, claim-level hallucination rate, ground-truth metrics, real per-call cost, leaderboards — and use it to change models and prompts with numbers, estimate monthly savings, ship behind per-feature settings and verify the result in Langfuse. Use when the user asks "benchmark our LLM features", "is model X better/cheaper for this", "test the new model on our use case", "judge the outputs", "LLM-as-judge", "evals", "which model should we use", "are we hallucinating", "how much do we spend on LLMs / tokens and where", "will switching save money", "compare prompts", or wants to apply what EnaCast did (gpt-6-luna switch, bench, quote check) to another repo such as Panotxa/NutriLens photo analysis. Also for auditing LLM spend per feature from Langfuse (scripts/langfuse_costs.py) and for the one-week post-change review.
---

# LLM bench: measure, change, verify

A bench answers one question with numbers before production sees anything: **if this
feature used model X / effort Y / prompt Z, would the output be better, worse,
cheaper, slower?** It is a frozen set of real inputs, the production code replayed on
them, a fixed scoring recipe, and a leaderboard with production as the baseline row.

Built twice in 2026-09 and it paid off both times:

- **enacast-ai** (episode analysis from transcripts): `gemini-3.5-flash-lite` →
  `gpt-6-luna` low + stricter prompts + a quote check in code: global 89.3 → 97.4,
  hallucinated claims 11.4 % → 2.9 %, cost −70 %.
- **enacast platform** (8 features: glossary, news article, headlines, tags,
  editor commands, sub-headline, entities, onboarding agent): glossary 70 → 87 at
  1/20 of the cost, news-article hallucinated claims 26 % → 7 %, editor quotes
  0 % → 100 % word for word; ~$160 → ~$17/month.

The cheap bench (≈ $15–25 per full run) found problems nobody had seen in
production: the most expensive call was untraced, quotes were invented, a feature
reasoned 2,350 tokens to write 60 characters.

## Workflow

0. **Read the project's own rules first** — its `CLAUDE.md`, existing LLM docs,
   deploy and team-mail conventions. Where the project already has eval scripts
   (Panotxa: `manage.py test_dataset`, `food-dataset-test/`), build on them.
1. **Inventory** every LLM call site: file, feature, input modalities, output
   shape, model and how it is chosen, prompt location/versioning, tracing,
   trigger and volume. Delegate the sweep to an Explore agent in big repos. Write
   it as `docs/llm_usage.md` in the project.
2. **Make every call visible**: a trace per call named after the feature, tenant as
   `user_id`, real cost (`cost_details={"total": …}`). Then run
   `scripts/langfuse_costs.py --since 30d --daily` for calls/month and $/call.
   Untraced calls are invisible spend: grep for them.
3. **Add the seams** production needs for replay, behaviour-preserving: a per-feature
   model/effort table with env overrides that production and the bench both read;
   a `model=` argument on each LLM function; prompt building split from the call.
4. **Freeze datasets** from a local copy of production data (read-only): 20–60
   items per feature, stratified (language × size × tenant kind, ≤ 2 per tenant),
   with the reference output production shipped and human truth where it exists.
   Committed in the private repo, excluded from Docker images.
5. **Run the baseline** (production settings) and **the shipped reference**, read
   ten outputs by hand, fix the rubric and the checks until the scores match what
   you see. Only then run candidates.
6. **Candidates**: models (same vendor first, then cross-vendor), reasoning effort,
   prompt variants, code checks. One variable at a time; same items, same judges.
7. **Decide per feature** with a plan doc: model, effort, prompt, code checks,
   trigger fixes, the bench numbers and the expected monthly money. Decisions are
   Oriol's (see below).
8. **Ship** behind the per-feature table, deploy under the project's rules, record
   the operation, verify the first traces, send the requested mails, and schedule the
   one-week review with an agent prompt (see
   [cost-and-verification.md](references/cost-and-verification.md)).

## Rules that came from real mistakes

- **Replay production, never re-implement it.** Call the production function with a
  candidate model, inside a context manager that turns off tracing, error reporting
  and metrics. A bench-only copy of the prompt drifts within a week.
- **The judge sees exactly what the writer saw** — glossary, client notes, user
  profile, the image — and the post-processed output. Without the glossary, 30–45 %
  of "invented" deductions were correct facts.
- **Same judge panel for every row**, judges from vendors not under comparison.
  Default: `openai/gpt-6-sol` on all items + `anthropic/claude-opus-5.5` on 20.
  `gemini-3.8-flash` as a judge is lenient: never alone. Changing a judge changes
  every absolute number; re-judge the baseline.
- **Hallucination is measured claim by claim**, not by a judge's impression: extract
  atomic claims, verify each against the source, report the rate and the share of
  outputs with zero bad claims.
- **Model-generated "expected" values are not ground truth**: they measure drift
  from the model that wrote them. Human labels measure accuracy; spend scarce ones
  calibrating the judges.
- **Never ask the model for something the source may not contain** ("always quote",
  "always name the guest", "always N sections"): it complies by inventing. Ask for it
  when present and say what to do when absent.
- **What can be checked in code is checked in code** (quotes aligned with the
  source, caps, ranges, schema). Put the check in the shared production step so
  production and bench get it together.
- **Structured output needs a schema**, not "JSON mode" (Panotxa: 3.6 % invalid JSON
  without `response_schema`). A bench on unconstrained JSON measures the parser.
- **Rubrics say what is NOT an error** — deliberate product choices scored as
  misses made production look worse than it was.
- **Freeze the prompt's source, not the assembled prompt**, when the prompt is built
  from data; freeze Langfuse prompts into the manifest so edits there don't change a
  rerun.
- **Reasoning tokens are the hidden cost** of short outputs; bench effort levels
  (minimal/low/medium) as well as models.
- **The model matters more than the prompt** (both EnaCast benches), but prompts
  still add 2–10 points on the weak dimensions: do both, measured separately.
- **Differences under ~2 points are noise**; small datasets need per-item reading.
- **Cost comes from the provider's counters**, not from summing result files (cached
  judgements are re-counted). Benches bill the production key until the bench has its
  own — say so wherever bench-day spend appears.
- **Tests and benches never write to production Langfuse**: client off *and*
  `LANGFUSE_TRACING_ENABLED=false`. Unit tests that mock HTTP but keep real keys
  send fake generations to production (seen 2026-09-23).
- **A deploy is not verified until real traffic shows the new model with a cost.**
  "No trace yet" is a state to report, not a success.
- Results are history: never delete a result file; stamp each with model, effort,
  prompt fingerprint, rubric version, judge ids, dataset version, git sha.

## Scoring recipe

Per item: rubric judges (0–100 per dimension, deductions) + claim check where the
output states facts + deterministic checks (`format` = share passed) + ground-truth
metrics where labelled. Item global = the feature's weighted dimensions + 0.10
format; a failed generation (error, refusal, unparsable, truncated) scores 0. Run
global = macro-average over languages (or other strata). Also per run: dimensions,
per stratum, hallucination and clean rates, check pass rates, **real $/item**,
judge cost, latency p50/p95, tokens (prompt / completion / reasoning), failures.

Details and pitfalls: [judging.md](references/judging.md).

## What to build in the project

| Piece | Where |
|---|---|
| bench app: schemas, replay + call recorder, judges, scoring, runner, leaderboard, feature adapters, CLI, tests | [architecture.md](references/architecture.md) |
| datasets and results | `bench/datasets/<feature>/<v>/`, `bench/results/<feature>/<v>/` (committed; cache gitignored; `bench/` in `.dockerignore`) |
| Makefile | `bench-features`, `bench-build`, `bench-run MODEL= EFFORT= FEATURE=`, `bench-reference`, `bench-leaderboard`, `bench-compare` |
| docs | `docs/llm_usage.md` (inventory), `docs/llm_bench.md` (mechanics), `docs/llm_notes.md` (dated facts + results log, newest first), `plans/<change>.md` (decision + outcome); for accuracy-critical products an `ACCURACY.md` (where errors come from, principles, standings) |
| ops | the project's operations-history entry for the deploy; team mail only when asked |

Vision features (photo → analysis) add image freezing, privacy of user photos, a
provider seam when production calls a vendor SDK directly, image-aware judges and
consistency checks: [vision.md](references/vision.md).

## Decisions that belong to Oriol

Ask, or put in the project's `USER_TODO.md` with why and what it blocks:

- putting any production model with **< 1M context** in place (warn; ~800k maybe
  fine) — long inputs have no fallback;
- freezing **user data** (transcripts, photos, messages) into a dataset, and which
  providers may see it;
- a **separate OpenRouter key** for benches (UI action);
- the model/prompt switch itself and its deploy, and any team mail.

Spending bench money on a candidate is not a decision to escalate when the user
asked for the bench; state the estimate (`--dry-run`) before long runs.

## Applying it to a project (checklist)

- [ ] Inventory written; every call traced with feature name, tenant `user_id`, real cost.
- [ ] `langfuse_costs.py --since 30d --daily` numbers in `llm_notes.md` (steady-state calls/month, $/call).
- [ ] Per-feature model/effort table with env overrides; `model=` on each LLM function.
- [ ] Structured outputs on a schema; parse failures counted, not repaired silently.
- [ ] Datasets frozen (privacy decision recorded), manifest with prompt hashes.
- [ ] Baseline + shipped reference scored and read by hand; rubrics fixed.
- [ ] Candidates run; per-feature plan with money; Oriol's decision.
- [ ] Shipped; first traces show the new model with cost; ops record; one-week review scheduled.

## Worked starting points

- **EnaCast (text, OpenRouter)** — reference implementations: enacast
  `enacast_backend/llm_bench/` + `docs/llm_bench.md`, enacast-ai
  `backend/enacast_ai/bench/` + `backend/docs/{BENCH,ACCURACY,QUOTING,LLM_NOTES}.md`.
- **Panotxa / NutriLens (vision, google-genai direct)** — state on 2026-09-24:
  eleven call sites, one model for all (`GOOGLE_GEMINI_MODEL`, default
  `gemini-3.5-flash-lite`, no thinking config), prompts in Langfuse (`production`
  label), JSON mode without schema, `LLMUsage` ledger with its own price table,
  Langfuse traces with `user_id`. Existing assets: `backend/food-dataset-test/`
  (16 photos; per-field targets generated by the model = drift only; 15 expert DQ
  scores by one nutritionist = real truth), `backend/scan-dataset-test/` (11 scanner
  photos, 7 Wikimedia-licensed, expected behaviour in prose, unread by code),
  `manage.py test_dataset` (range pass/fail, stdout only). First steps there:
  per-feature model table + `model=` seam (photo analysis, menu extraction first);
  `response_schema`; freeze both photo sets through `encode_image_for_gemini`;
  features `dish_photo`, `menu_extraction`, then the text ones (`meal_quality`,
  `daily_insight`, `chat`); judges with the image; nutritionist scores to calibrate
  the quality dimension; candidates `gemini-3.8-flash` (thinking off/low) and
  `gpt-6-luna`; latency p95 reported next to quality.

## Scripts

- `scripts/langfuse_costs.py` — read-only Langfuse spend/volume per generation name ×
  model (or per `userId`), before/after split at a deploy time, per-day view. Stdlib
  only; reads `LANGFUSE_PUBLIC_KEY/SECRET_KEY/BASE_URL` from env or `--env <file>`.
  Uses the v2 observations API (cursor) and falls back to v1 pages.
