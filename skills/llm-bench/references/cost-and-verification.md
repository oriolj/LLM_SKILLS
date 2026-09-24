# Cost accounting, savings estimates, and verifying a change in production

## Where the money is actually billed

Know it per feature before estimating anything:

| Path | Where it bills | What OpenRouter's key counters show |
|---|---|---|
| OpenRouter, OpenRouter credits (e.g. `openai/gpt-6-luna`) | OpenRouter invoice | `usage` |
| OpenRouter **BYOK** (your Google/OpenAI key configured in OpenRouter) | the vendor's invoice (Google Cloud / AI Studio) | `byok_usage`; body `usage.cost` = 0, `cost_details.upstream_inference_cost` = real cost |
| Vendor SDK direct (`google-genai`, `openai`) | the vendor's invoice | nothing |
| Bench runs on the production key | the same invoice as production | bench days show as production spikes |

Consequences:

- A switch from a BYOK Gemini model to an OpenRouter-billed model **moves** spend
  between invoices; say so in every savings claim ("the spend changes invoice, it
  does not disappear").
- Vendor invoices can be missing from the bookkeeping entirely (EnaCast 2026-09:
  Gemini was paid by bank card, €294–338/month, and absent from Holded after March).
  Check the bank before concluding a cost is small.
- **Give the bench its own OpenRouter key.** Creating one is an OpenRouter-UI action
  for Oriol (`USER_TODO.md`). Until then, subtract bench days before reading the key.

OpenRouter key counters: `GET https://openrouter.ai/api/v1/key` with the key as
bearer → `usage`, `usage_daily|weekly|monthly`, `byok_usage*`, limit. Per-generation
detail: `GET /api/v1/generation?id=<gen id>`.

## Inventory first: what runs, how often, at what cost

`scripts/langfuse_costs.py` (this skill) — read-only, stdlib-only:

```
python3 <skill>/scripts/langfuse_costs.py --env backend/.envs/.local/.django --since 30d
python3 <skill>/scripts/langfuse_costs.py --env .env --since 30d --daily          # spot bulk backfills
python3 <skill>/scripts/langfuse_costs.py --env .env --since 14d --split 2026-09-24T07:45Z
python3 <skill>/scripts/langfuse_costs.py --env .env --since 7d --by user          # per tenant
```

Per generation name × model: calls, calls with a cost, mean input/output tokens,
$/call, total, calls/30 d, $/30 d. Read the "with cost" column first: a feature at 0
has no cost in Langfuse (the app sends none and Langfuse cannot price the model), so
every dashboard under-reports it. Fix the instrumentation (send
`cost_details={"total": real_cost}`, key `total`, never `total_cost`) before
estimating from it.

Then grep the code for LLM calls the traces do not show: an untraced call is
invisible spend (the EnaCast radio glossary — the platform's biggest LLM cost, ~$145
of ~$160/month — had no trace at all). Every LLM call site gets a trace named after
the feature, `user_id` = the paying tenant, and its real cost.

Watch for traces that are not production: local runs and **unit tests with real
Langfuse keys** write into the same project (no user id, toy token counts, times
that match a test run). Tests and benches must run with tracing off.

## Estimating monthly savings

For each feature: `calls/month × ($/call now − $/call candidate)`.

- calls/month from Langfuse over 30 days, **steady state** — take the median weekday
  and weekend day from `--daily`, not the window mean, when a bulk re-run sits in the
  window (enacast-ai 2026-09: 15,674 analyses in 30 days, of which ~13,300 in a
  four-day re-analysis; steady ≈ 3,000/month).
- untraced features: count their triggers in the DB (rows updated per day) or logs.
- $/call from the bench's call recorder on the same items (real tokens including
  reasoning, real cost), not from list prices × guessed tokens. Reasoning tokens
  dominate short outputs (a 60-character sub-headline spent ~2,350 reasoning tokens
  at effort medium ≈ $0.018; Luna did it for $0.00013).
- add trigger savings separately (skip when the input did not change, dedupe
  dispatch): they compound with the model switch but are not measured by the bench.
- state the range and what would change it; never present an estimate as billed.

## Shipping a change safely

- Per-feature model and effort in **one table the bench also reads**, each entry
  overridable by env (`LLM_MODEL_<FEATURE>`, `LLM_EFFORT_<FEATURE>`) so a rollback is
  a Coolify env change + redeploy, no code.
- **Context-window check** before any model change: long inputs (transcripts, full
  histories) need ≥ 1M context in the estate's projects; warn Oriol before anything
  under ~800k (Oriol, 2026-09-23).
- Prompt changes versioned (Langfuse label or code fingerprint) and benched before
  shipping; keep the previous version for rollback.
- Code checks (quote repair, schema validators, caps) go in the shared production
  step so production, experiments and the bench all get them.
- Deploy under the project's own rules (review, one deploy, `make prod-status`),
  then record it in the project's operations history.

## Verifying after the deploy

Same day:

1. The deployed commit and effective settings in the running container (the
   feature table resolves to what you shipped, no stray env override).
2. First production trace of each changed feature: model is the new one, cost is
   present, latency sane, no error level. Early morning deploys may see no traffic
   for hours — say "not yet seen", never "verified".
3. Error tracker (GlitchTip) for the touched modules.

A week later (put the reminder in the team mail, and in a personal mail to Oriol
with an agent prompt):

```
Review the LLM changes deployed <date/time UTC> in <repo> (commit <sha>, deployment <id>).
Read first: <ops record>, <llm_notes>, <llm_bench doc>, <plan>. Read-only on production;
record every verified fact, dated, in the owning doc and commit.
1. Costs: run langfuse_costs.py --since 14d --split <deploy time> (and --daily). Per feature:
   calls, $/call, $/30d before vs after; every changed feature has cost on every trace; the
   new model is the one in the traces. Compare with the plan's estimate.
2. Provider counters: OpenRouter /api/v1/key usage and byok_usage for the production key(s),
   excluding bench days; the vendor invoice / bank line if the spend moved there.
3. Triggers: how often the skip/dedupe paths fire (logs), errors, truncations.
4. Quality on real traffic: read N outputs per changed feature against their inputs;
   anything invented, wrong language, dropped fields. Error tracker since the deploy.
5. Optional: re-run the bench on the current production settings to detect drift.
6. Open decisions for Oriol.
Report: a before/after table per feature, confirmed vs not confirmed, and anything to roll back.
```
