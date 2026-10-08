---
name: leadhunter
description: Operate H2A-LeadHunter — AI that ranks thousands of prospects against a target persona so the best are worked first, and the system of record for every relationship and outreach across every scope (EnaCast, SmartupSoft/BikeCRM, …) — through its REST API: auth with the agent token, importing and scoring account lists, organizations → projects, reading accounts/campaigns/funnel stats, exporting campaign lists, marking clients and do-not-contact, logging an email/WhatsApp send and its reply so the funnel counts it (with the message purpose on opted-out accounts), reading an account's whole conversation, next steps with due dates (create / complete / reschedule, quick-add templates and suggested follow-ons, reminders, the daily digest and calendar feed), account notes, and AI drafts. Use when the user mentions LeadHunter, leads, prospects, "mark our clients", "log that message", "who did we contact", "what's the next step / follow-up with X", "remind me to … on <date>", outreach funnel, cold-email campaign lists, relationship_types, or do-not-contact; and before any cold outreach send.
---

# LeadHunter — leads and outreach log

H2A-LeadHunter (`leadhunter.humans2agents.com`, personal scope, code in
`~/git/oriolj/humans2agents/agents/leadhunter/`): AI that ranks thousands of
prospects (website research + persona scoring with reasons, per goal) so the
best are worked first, then keeps every relationship moving and measures
what works. It holds every lead of every product: accounts, contacts,
campaigns, AI scores, the log of what was sent and answered, next steps,
and cost / ROI per campaign and channel. **It logs outreach; it does not send it.** A message
goes out from a real mailbox / WhatsApp, then is logged here.

This skill is mechanics. Decisions, rules and campaign records live in hq
[growth/outreach](../../../../../Syncthing/Syncthing-mobile-docs/hq/growth/outreach/README.md)
(read it before any outreach). Full API reference:
[backend/docs/API.md](../../../humans2agents/agents/leadhunter/backend/docs/API.md)
(+ [GLOSSARY.md](../../../humans2agents/agents/leadhunter/GLOSSARY.md),
[docs/models/](../../../humans2agents/agents/leadhunter/backend/docs/models/ACCOUNT.md)).

## Access

- Token + base URL: hq `homelab/secrets/h2a-leadhunter.env` —
  `H2A_LEADHUNTER_API_TOKEN`, `H2A_LEADHUNTER_API_URL`
  (`https://leadhunter.api.humans2agents.com`). Parse with grep/cut, never
  `source`, never print the token.
- Header `Authorization: Token <token>`, and always a full current Chrome
  UA (a truncated `Mozilla/5.0` got a non-JSON answer on 2026-10-03).
- User `agent@humans2agents.com` (no usable password), ProjectUser
  `member`. **Visibility is per project membership**: a project the agent
  was not added to is invisible (see Tenancy for how each endpoint
  answers). Check `GET /api/projects/` first.
- 401 = token revoked (Token row deleted in Django admin) → ask Oriol.
- Throttle: 200 req/min per user; LLM actions (propose, scoring, enrich)
  share 60/min. 429 carries `Retry-After`.

```bash
# bash, not fish. HDR goes in the session scratchpad, mode 0600, so the
# token is never in argv (ps) or in the terminal.
H=~/Syncthing/Syncthing-mobile-docs/hq/homelab/secrets/h2a-leadhunter.env
HDR=<scratchpad>/lh-auth.hdr
U=$(grep '^H2A_LEADHUNTER_API_URL=' "$H" | cut -d= -f2-)
(umask 077; printf 'Authorization: Token %s\n' "$(grep '^H2A_LEADHUNTER_API_TOKEN=' "$H" | cut -d= -f2-)" > "$HDR")
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
# --fail-with-body: a 401/429/502 exits 22 and prints the error body, so
# it never reaches the next jq as if it were data
lh() { curl -sS --fail-with-body -A "$UA" -H @"$HDR" "$U$1"; }
lh /api/organizations/
lh '/api/accounts/?project=bikecrm&status=customer'   # quote: & backgrounds
```

Delete `$HDR` when the session ends.

## Tenancy

**Organization** groups **projects**; the project is the data tenant
(since 2026-09-28). Today: `enacast` → `enacast`; `smartupsoft` →
`bikecrm`, `petcrm`, `motorcrm`, `fichachat`. Every endpoint takes
`?project=<slug-or-uuid>`. An unknown project, or one the agent is not
a member of, gives **400** on accounts and messages, an **empty page** on
`GET /api/campaigns/?project=`, and **zeros** on the dashboard stats (no
error). Organizations list only member projects.

## Reading

| Need | Call |
|---|---|
| Projects / orgs | `GET /api/projects/[?organization=<slug>]`, `GET /api/organizations/` |
| Accounts | `GET /api/accounts/?project=…&relationship_types=client,partner&status=customer&country=…&search=…&ordering=-created_at` |
| Accounts, advanced | `filter=<url-encoded JSON DSL>` / `cf_<key>=` / `saved_filter=<id>` (`docs/CUSTOM_FIELDS.md`) |
| Accounts CSV | `GET /api/accounts/export_csv/?<same filters>` |
| One account (+ campaign memberships, histories) | `GET /api/accounts/{id}/` |
| Campaigns | `GET /api/campaigns/?project=…&status=…&archived=all` |
| Campaign totals | `GET /api/campaigns/statistics/?project=<uuid>` (counts by status and `by_goal`) |
| Campaign CSV (reading only, never a send list) | `GET /api/campaigns/{id}/export-accounts/?review_status=approved&fields=name,email,contact_email,status,score,score_label,language,relationship_types,…` (CSV; unknown field → 400). Never `review_status=all`: it brings back the rows you rejected. Send lists: § Send list |
| Campaign inbox (latest message per account) | `GET /api/campaigns/{id}/inbox/?tab=all` — same filters as the campaign-accounts list (`review_status`, `score_label` incl. `unscored`, `score_band`, `min_score` / `max_score` on the effective score, `search` = every word must match name / contact / email / note / directions; bad value → 400 keyed by the param); rows have `ai_score` and `effective_score` |
| Messages (an account's whole conversation, every campaign + none) | `GET /api/messages/?lead=<account_id>&ordering=-sent_at,-created_at,-id&page_size=50` (newest first); older: `?before=<next_before from the previous response>`; filters `channel=whatsapp,email`, `direction=inbound`, `campaign=<uuid>\|none` |
| Next steps (due dates, ours / theirs) | `GET /api/next-steps/?account=<id>` or `?project=…&assignee=me&status=open&due=overdue,today` (§ Next steps) |
| My reminders (what the bell shows) | `GET /api/next-steps/reminders/` |
| Funnel | `GET /api/dashboard/stats/?project=<slug>` or `?organization=<slug>`; per product/campaign `GET /api/dashboard/breakdown/?project=<slug>` |
| What's due / waiting today (one call) | `GET /api/dashboard/today/?project=<slug>&scope=mine\|team&today=YYYY-MM-DD` (§ Today) |
| Campaign scoring runs | `GET /api/dashboard/scoring-runs/?project=<slug>` (running, or started in the last 14 days; progress, cost) |

Pagination: `count/next/previous/results`, default 20, **max 100**
(`page_size=500` silently gives 100). Always loop on `next` — except
messages read newest first, which page by keyset: follow `next_before`
(`?before=`), never page numbers (deletes elsewhere shift numbered pages).
Garbage query params answer **400 keyed by the param** (since 2026-10-05
the csv filters too, e.g. `{"channel": "Unknown value(s): …"}`); dates
must be 1900–2999.

Humans see the same data on Today (`/dashboard`), at `/dashboard/accounts/<id>` (Next steps card,
Brief & Notes, Conversations card → `/dashboard/accounts/<id>/conversations`),
`/dashboard/follow-ups` and the topbar bell. Link those when reporting.

## Account fields that gate outreach

- `status` (lifecycle, single): `prospect`, `contacted`, `in_negotiation`,
  `in_trial`, `customer`, `lost`, `do_not_contact`. **Read-only on PATCH**:
  change it with `POST /api/accounts/{id}/change-status/`
  `{"status","reason","source"}` (writes history, fires webhooks).
- `relationship_types` (multi): `client`, `prospect`, `reseller`,
  `affiliate`, `supplier`, `partner`, `investor`, `press`, `influencer`,
  `analyst`, `competitor`, `candidate`, `personal_network`, and (marketing
  partners M1, live since 2026-10-08, LeadHunter `7ef56b0d`) `community`,
  `event_organizer`. PATCHable on `/api/accounts/{id}/` — send the
  **whole** array (it replaces).
- **Marketing partners** (contract in
  [API.md § Marketing partners](../../../humans2agents/agents/leadhunter/backend/docs/API.md#marketing-partners)):
  an account with a marketing type (influencer, press, partner,
  affiliate, analyst, community, event_organizer). A *pure* partner (no
  other type, status not customer / in_trial) is left out of client
  stats; list them with `?marketing=only`, hide them with
  `?marketing=exclude`. `partner_stage` (to_contact, contacted, talking,
  agreed, active, past, declined, not_a_fit) is read-only on PATCH: move
  it with `POST /api/accounts/{id}/change-partner-stage/ {"stage","reason"}`
  (400 on a non-partner); a partner without a stage gets `to_contact`.
  `audience_size` (followers / circulation) is plain PATCH.
- `do_not_contact_purposes`: per-goal opt-out, only via
  `POST /api/accounts/{id}/record-dnc/` `{"purpose":"sales","action":"opt_out","source":"inbound_request","reason":…}`.

Guardrails when adding to a campaign (`bulk_add`, `bulk-add-from-filter`;
[`campaigns/services.py::partition_accounts_for_outreach`](../../../humans2agents/agents/leadhunter/backend/leadhunterbackend/campaigns/services.py),
goal matrix in [`campaigns/goals.py`](../../../humans2agents/agents/leadhunter/backend/leadhunterbackend/campaigns/goals.py), checked 2026-10-03). **They run only on adds.**
Logging an outbound message enforces only DNC (403); a CSV export
re-applies nothing.

- **Hard, never overridable**: `status=do_not_contact`, a goal in
  `do_not_contact_purposes`, `personal_network` (any goal), `competitor`
  (all goals except press / event / research).
- **Soft** (overridable per add): `status=customer` (`include_customers`)
  and `status=in_trial` (`include_trials`), both only on goals that block
  customers (sales and most others; expansion, renewal, event, research
  and partnership admit customers by default); supplier / investor /
  press / analyst / candidate (`include_suppliers`, `include_investors`,
  `include_press`, `include_analysts`, `include_candidates`, per goal);
  plus influencer / community / event_organizer
  (`include_influencers`, `include_communities`,
  `include_event_organizers`) on every goal that soft-blocks press.
- **Mark existing clients before any cold campaign — and the guardrail
  keys on `status=customer`, NOT on `relationship_types` `client`**.
  A `client` tag alone does not keep an account out of a sales campaign.
  Set both: tag `client` (PATCH `relationship_types`) and status
  `customer`. **For clients that already existed, send
  `"source": "pre_existing"`** on `POST /api/accounts/{id}/change-status/`
  or `POST /api/accounts/bulk-change-status/`
  (`{"account_ids": [...], "status": "customer", "source": "pre_existing", "reason": "…"}`):
  the funnel's `closed (won)` metric excludes that source
  (`dashboard/services.py::CLOSED_EXCLUDED_SOURCES`), so a backfill keeps
  its audit trail without a fake spike of wins. The default `manual`
  counts every `→ customer` as a win that day. No shell needed.
- **Existing campaign rows are not removed** by marking a customer: the
  guardrail only filters *adds*. Reject the account's sales-goal rows
  (`campaign_memberships` on the account detail →
  `POST /api/campaign-accounts/{campaign_lead_id}/reject/ {"reason": "existing client"}`).
  The EnaCast backfill of 2026-10-03 did exactly this
  ([hq growth/enantena](../../../../../Syncthing/Syncthing-mobile-docs/hq/growth/enantena/README.md#enacast-clients-marked-in-leadhunter--2026-10-03)).

## Send list

The guardrails ran when each row was added (§ above); an account marked
`customer`, `in_trial` or DNC since then is still in the campaign. So the
list that goes to a mailbox or WhatsApp is built from the API and
re-checked, never taken from the CSV (it has no DNC purposes and no
`campaign_lead` id to log the send against). Only rows never contacted
(`outreach_status=not_started`) come back: a follow-up to people already
mailed is a different list. The filter copies the per-goal matrix of
`goals.py` (hard and soft relationship blocks, DNC) and drops customers
and trials on every goal. It is interim until LeadHunter's `?sendable=1`
filter ships ([USER_TODO](../../USER_TODO.md)).

Run it as ONE bash script together with the Access block (`bash -s` or a
file): `set -e` is what stops it on a 401/429/502 instead of writing a
list that silently lost rows.

```bash
set -euo pipefail
C=<campaign uuid>; OUT=<scratchpad>/send-$C; mkdir -p "$OUT"
camp=$(lh "/api/campaigns/$C/")
GOAL=$(jq -er .goal <<<"$camp"); P=$(jq -er .project_slug <<<"$camp")
ROWS="/api/campaign-accounts/?campaign=$C&review_status=approved&outreach_status=not_started&ordering=created_at&page_size=100"
TOTAL=$(lh "$ROWS" | jq -er .count)
pages() {        # $1 first URL, $2 jq per page; follows next (100 per page)
  local url=$1 page
  while [ -n "$url" ]; do
    page=$(lh "$url"); jq -c "$2" <<<"$page"
    url=$(jq -r '.next // empty' <<<"$page"); url=${url#"$U"}
  done
}
pages "$ROWS" '.results[] | {campaign_lead: .id, account}' > "$OUT/rows.ndjson"
# offset pages can shift under concurrent writes: refuse duplicates or gaps
jq -se --argjson total "$TOTAL" 'length == $total and (map(.campaign_lead) | unique | length) == $total' "$OUT/rows.ndjson" >/dev/null \
  || { echo "rows changed while paging (duplicates or gaps): re-run" >&2; exit 1; }
pages "/api/accounts/?project=$P&in_any_campaign=true&archived=all&page_size=100" \
  '.results[] | {id, name, email, status, relationship_types, do_not_contact_purposes}' > "$OUT/accounts.ndjson"
jq -n --arg goal "$GOAL" --slurpfile accs "$OUT/accounts.ndjson" --slurpfile rows "$OUT/rows.ndjson" '
  # goals.py 2026-10-07 (marketing partners M1): soft relationship blocks
  # per goal; $mkt joins every goal that soft-blocks press (live since
  # 2026-10-08).
  ["influencer", "community", "event_organizer"] as $mkt
  | (["supplier", "investor", "press", "analyst", "candidate"] + $mkt) as $sales
  | {sales: $sales, partnership: [], press: ["supplier", "investor", "candidate"],
     influencer: ["supplier", "investor", "candidate"],
     investor: (["supplier", "press", "analyst", "candidate"] + $mkt),
     recruiting: (["supplier", "investor", "press", "analyst"] + $mkt),
     customer_expansion: $sales, win_back: $sales, event: [], research: [],
     renewal: $sales}[$goal] as $soft
  | if $soft == null then error("goal \($goal) not in the copied matrix: re-read goals.py") else . end
  | (["personal_network"] + (if $goal | IN("press", "event", "research") then [] else ["competitor"] end)) as $hard
  | ($accs | map({key: .id, value: .}) | from_entries) as $acc
  | $rows | map(. + {acc: ($acc[.account] // error("no account for row \(.campaign_lead)"))})
  | map(select(
      ((.acc.relationship_types // []) as $rt
       | (.acc.status | IN("customer", "in_trial", "do_not_contact") | not)
         and ((.acc.do_not_contact_purposes // []) | index($goal) | not)
         and ([$rt[] | IN(($hard + $soft)[])] | any | not))))
' > "$OUT/send.json"
wc -l < "$OUT/rows.ndjson"; jq length "$OUT/send.json"   # approved vs sendable
```

Report both counts and what was dropped. Customers and trials are
dropped on every goal, even the ones LeadHunter lets them into
(partnership, customer_expansion, event, research, renewal): a campaign
that targets them on purpose is not a cold send, so ask Oriol before
relaxing that filter. Each row of
`send.json` carries the `campaign_lead` to log the message against.

## Adding accounts to a campaign from a filter (2026-10-08, `7ef56b0d`)

`POST /api/campaigns/{id}/bulk-add-from-filter/` takes
`{"list_query": {<the same params as GET /api/accounts/>}, "dry_run": true}`
and resolves them through the SAME queryset as the list, so it adds
exactly what the list shows (search, country, status, relationship_types,
`marketing=exclude`, saved_filter, `filter` DSL, `research_id` …).
- Always dry-run first: it answers `matched`, `would_create`,
  `already_in_campaign` and `blocked_counts` per guardrail bucket
  (`blocked_*` id lists are capped at 100 ids). Then send the real add
  with `expected_count` = the previewed `matched`; a changed size → 409
  (recount and ask again).
- A query that narrows nothing → 400 unless `"all": true` (ask Oriol
  first); more than 10,000 matches → 400 (`over_limit`, `max_add`):
  narrow the list. Partners hidden by `marketing=exclude` stay out unless
  you drop that param on purpose (Press / Influencer campaigns).
- A stale or other-project `saved_filter` → 400 keyed `saved_filter`;
  unknown `status` / `relationship_types` values → 400 keyed by the param;
  a request body that isn't a JSON object → 400 on every endpoint.
- Merges keep the most advanced status (do-not-contact wins) and refuse a
  `status` override (400); change status afterwards with `change-status`.

## Reviewing campaign accounts: Shortlist / Defer / Not a fit (2026-10-08, not deployed yet)

The UI words are **Shortlist / Defer / Not a fit**; the API values stay
`review_status=approved` / `deferred` (new) / `rejected` / `pending`. The
send list above (`review_status=approved`) = the shortlist.
- **One account**: `POST /api/campaign-accounts/{id}/approve|reject|defer|reset/`
  (`reject` / `defer` take an optional `reason`, ≤ 500 stored; `reject`
  also appends `Rejected: <reason>` to the row's notes). A `PATCH
  {"review_status": …}` is the same manual decision, ALWAYS recorded —
  on a row a bulk choice set it turns it `manual` even at the same
  status (undoing that bulk batch then keeps it). A PATCH of other
  fields (notes, contact) never changes the review status. Payload carries
  `review_source` (`manual` / `bulk` / `""`), `reviewed_at`,
  `reviewed_by_email`, `review_reason`.
- **Only per-account decisions teach the scoring** (the calibration
  few-shot reads `review_source=manual`). Shortlisting rows one by one
  through the single endpoints IS a fit judgement, so do it only for
  accounts you actually judged; for a triage of a band use bulk.
- **Bulk**: `POST /api/campaigns/{id}/bulk-review/` with `decision`
  (`shortlist|defer|not_a_fit|pending`) and either `ids` (campaign-account
  ids) or `filters` (`review_status`, `score_label` incl. `unscored`,
  `score_band` `8-10|6-8|4-6|0-4|unscored`, `min_score` / `max_score`,
  `search`) plus optional `top_n` (best effective score first). Always
  `"dry_run": true` first (answers `matched`, `changed`, `unchanged`,
  `by_previous_status`), then the real call with `expected_count` =
  `matched` (409 → recount). Max 10,000 rows (400 with `matched`; use
  `top_n` or narrow). Keep the `batch_id`: `POST …/undo-review/
  {"batch_id"}` reverts rows nobody changed since; `GET …/review-batches/`
  lists the last 20. Ask Oriol before a bulk decision on a whole
  campaign.
- **Bands**: `GET /api/campaigns/{id}/score-bands/` — counts per band
  (effective score = per-campaign override else AI score; `[min,max)`,
  8-10 includes 10) × review status, plus totals. Use it for counts,
  never page through the list to count.
- **List**: `/api/campaign-accounts/?campaign=…&score_band=8-10&ordering=-effective_score`;
  `min_score` / `max_score` read the effective score (since 2026-10-08);
  `review_status` and `score_label` are csv (unknown → 400). An unscored
  row has `ai_score: null`, `score_label: ""` — it is NOT a mismatch.

## Scoring: estimate before you start (2026-10-08, not deployed yet)

Scoring spends LLM money. Before `POST /api/campaigns/{id}/score_leads/`
read `GET /api/campaigns/{id}/scoring-estimate/?force=false` (answers
`accounts_to_score`, `batches`, `model`, `est_cost_usd` (null = no
price), `basis` `history|heuristic`, `note`), tell Oriol the count and
cost, and start with `{"expected_count": <accounts_to_score>}` (409 when
the worklist changed → re-estimate). Project-wide:
`GET /api/campaigns/scoring-estimate-remaining/?project=<slug>` then
`POST /api/campaigns/batch-score-remaining/?project=<slug>` with
`expected_count`. Without `expected_count` both still start (old
behaviour), but don't rely on that. A plain run scores only accounts
without a score; to refresh out-of-date scores (`stale: true`) use
`?stale_only=true` on the estimate and `{"stale_only": true,
"expected_count": N}` on `score_leads` (rescores just those; `force`
rescores everything and wins). `expected_count` must be an integer ≥ 0
(a boolean / float → 400).

## Fit score on accounts (2026-10-08, not deployed yet)

`GET /api/accounts/?project=…&fit_product=<product uuid>&fit_goal=sales&min_fit=7&ordering=-fit_score`
adds `fit {score, label, scored_at, product_id, goal, criteria_version, current_criteria_version, stale}` to each row (null
without `fit_product`); `fit=scored|unscored` filters; `min_fit` /
`max_fit` / `fit` without `fit_product` → 400. The same params work in
`bulk-add-from-filter`'s `list_query` ("add every 7+ account"). The
account detail has `fit_scores` (every product × purpose score with its
reasons).

## Fit criteria and ranking without a campaign (2026-10-08, not deployed yet)

**Fit criteria** = what a product looks for, per purpose (goal). One row
per (product, goal) at `/api/fit-criteria/` (same as `/api/icps/`):
`?project=&product=&goal=`; rows carry `version` and `status`
(approved|draft). Generate without a campaign:
`POST /api/fit-criteria/generate/ {"product": "<uuid>", "goal": "sales", "hints": "one per line"}`
→ 202 (async; poll the list for the row / a higher `version`). A PATCH
of name / summary / industries / job_titles / pain_points / size is a
new version; `GET /api/fit-criteria/{id}/versions/` lists them. Scores
made with an older version say `stale: true` (`fit`, `fit_scores`,
campaign-account rows; `score-bands` `totals.stale` counts them). The
`fit` block now also has `criteria_version`, `current_criteria_version`.

**A campaign with a scoring brief has its own scores** (`fit_criteria
{key: "campaign:<id>", own_brief: true}` on the campaign). Rescoring it
never changes other campaigns, the Accounts fit column or Today, and a
shared rescore never changes its own scores. Where it has no own score
yet (brief just added, accounts added later) it shows the shared score as
`stale: true` with `score_source: "shared"` (own scores say
`"campaign"`, unscored `null`); rescore those with `stale_only`.

**Rank a list (no campaign)** — always estimate, tell Oriol count and
cost, then start with a cap:

1. `POST /api/ranking-runs/estimate/ {"project": "<slug>", "product": "<uuid>", "goal": "sales", "list_query": {...accounts-list params...}}`
   (or `"account_ids": [...]`, a non-empty list; exactly one; a
   `list_query.project` other than the run's → 400 keyed `list_query`)
   + optional `force`,
   `sample_size` → `accounts_matched`, `accounts_to_score` (excludes
   up-to-date scores unless `force`), `est_cost_usd`, `over_limit`
   (max 20,000), `pricing_available`, `est_enrichment_reserve_usd`
   (website discovery set aside before scoring; NOT in `est_cost_usd` —
   the cap must cover both). No fit criteria → 400 "Generate fit
   criteria first."
2. `POST /api/ranking-runs/` same body + `"max_cost_usd": <USD, required>`
   + `"expected_count": <accounts_to_score>` → 201 run. 409 = the count
   changed (re-estimate) or a run of that product + goal is already
   running (`run_id`). 400 `code: "no_pricing"` = the model (or, with a
   Gemini key, the website-discovery model) has no price: the cap can't be
   enforced, so the run won't start — tell Oriol, don't retry. The run
   keeps its `model` to the end. Try `"sample_size": 50` first on a new
   product.
3. Follow `GET /api/ranking-runs/{id}/` (`status`, `progress`,
   `spent_usd` — live: every recorded call adds its cost at once, rounded
   up to 4 decimals; the exact sum at the end —, `stop_reason`:
   `budget_reached` → ended `partial`, what
   it scored is kept; `usage_not_recorded` → a call's cost couldn't be
   recorded, the run stopped). `POST /api/ranking-runs/{id}/cancel/`
   stops it within one batch.
4. Act: `results_query` is the accounts-list query of what it scored,
   best first (`?ranking_run=<id>&fit_product=…&ordering=-fit_score`);
   pass it (plus e.g. `min_fit: 8`) as `list_query` to
   `bulk-add-from-filter` to put the best into a campaign.

The cap counts everything the run pays for (website discovery during
enrichment and the scoring calls). The run checks its spend before every
AI call (website lookups and scoring batches) and stops when the cap is
reached. Calls already in flight finish, so the final spend can go a
little over the cap, typically by less than one batch. Several chunks run
in parallel, so the overshoot can be up to one call per running chunk.
Set the cap with that margin, and never tell Oriol a run "can't" pass it.

Merges and deletes during or after a run are safe: an account deleted
before the run scored it counts in `counts.gone`, one merged into another
in `counts.merged` (the survivor is scored only if it is itself in the
run); already-scored rows keep their outcome; `run_processed` still
reaches `run_total`. A run copy that lost its chunk to another worker
writes nothing (no stale scores over newer ones).

## Importing files and cleaning duplicates (2026-10-08, not deployed yet)

Import wizard (multipart upload, then JSON):
1. `POST /api/accounts/import_preview/` (`project_slug`, `file` .csv/.xlsx,
   ≤ 10 MB, ≤ 200,000 rows) → `file_id`, `headers`, plus
   `suggested_mapping` `{header: field|"skip"}` (from the header names,
   free and deterministic), `unmapped_columns`, `column_samples` and
   `target_fields` `[{value, label}]`. Start from `suggested_mapping`.
2. Optional: `POST /api/accounts/import_suggest_mapping/`
   `{file_id, columns: [<unmapped headers>], taken_fields: [<fields in use>]}`
   — one LLM call (costs money, `llm` throttle); only maps the asked
   columns and never a taken field. Skip it when the headers mapped.
3. `POST /api/accounts/import_mapped/` `{file_id, project_slug, column_mapping,
   dry_run?}` — always `dry_run: true` first. ≥ 2,000 rows → 202 with
   `research_id`; poll `GET /api/research/{id}/`.
- The full list of skipped rows is a CSV:
  `GET /api/research/{id}/import-report.csv/?kind=invalid` (rows dropped
  as invalid / rejected, with errors) or `?kind=duplicates` (row, reason,
  matched value, `existing_account_id`). Keep the trailing slash. Counts
  ride on `configuration.import_report_counts` and on the sync response.
  ≤ 10,000 rows per kind.
- The accounts one import created: `GET /api/accounts/?import_research=<research id>`
  (the same set "Undo this import" deletes); works in `bulk-add-from-filter`'s
  `list_query` too ("add everything from that file to the campaign").
  Check the run's `import_membership` (on `GET /api/research/{id}/` and
  the list): `"exact"` (every import since 2026-10-08) = exactly the
  accounts that run created (a duplicate re-import selects nothing);
  `"approximate"` = an older run, matched by file fingerprint + time
  window, which can include another import of the same file — say so
  before acting on it.
- Undo: `POST /api/research/{id}/revert-import/` (destructive, ask Oriol
  first). Exact runs delete only their own accounts. An approximate run
  whose window shares accounts with another old import of the same file
  answers **400, nothing deleted** ("…can't be told apart…") — don't
  retry; list the accounts and decide with Oriol which to delete.

Duplicates (no project-size limit any more):
- `POST /api/accounts/find-duplicates/` `{project, mode: "exact"|"fuzzy",
  page, page_size ≤ 100, campaign?}` → `duplicate_groups[]` (`reason`
  = `name_city_exact` 95 / `phone_match` 90 / `website_domain` 85 /
  `google_place_id` 100 / `fuzzy_name` = the WEAKEST name similarity in
  the group, so a `confidence ≥ 90` filter holds for every member),
  `size`, `total_groups`,
  `num_pages`, `counts_by_type`. One account appears in one group.
- Before merging: `POST /api/accounts/merge-preview/` for one group, or
  `POST /api/accounts/bulk-merge/` with `dry_run: true` (≤ 100 groups) to
  see each survivor (oldest) and golden record. Merges are irreversible
  and delete the absorbed accounts: show Oriol the preview and get a yes
  before any real merge.
- Merges and campaign decisions: when both accounts are in one campaign
  and only the absorbed one was decided, the survivor takes the decision
  WITH its review events, so `review-batches` counts hold and
  `undo-review` of that batch reverts the survivor. A survivor that was
  already decided keeps its decision; the absorbed one's is dropped
  (listed in `merge_history[-1].folded_review_decisions`, each dropped
  event archived under `events`: from / to status, source, reason,
  reviewer id `by_id`, batch id, timestamps) and undoing its batch never
  touches the survivor.

## Today and Runs (2026-10-08, not deployed yet)

"What should we do today / who is waiting on us" = ONE call:
`GET /api/dashboard/today/?project=<slug-or-uuid>&scope=mine|team&today=<local YYYY-MM-DD>`
(`project` required; unknown / foreign → 400; bad `scope` / `today` → 400;
`&sections=due_steps,replies_waiting` returns only those sections,
unknown → 400).
Four sections, each `{count, results}` with the exact count and the top N:

- `due_steps` (20; + `overdue` / `today` / `tomorrow` counts) — open next
  steps due on or before tomorrow, in the `/api/next-steps/` row shape.
  `scope=mine` = assigned to the token's user — for an agent token that
  is usually Oriol; use `team` to see everyone's.
- `replies_waiting` (20, newest first) — accounts whose latest sent
  inbound message has no sent outbound at or after it (drafts don't
  count), not archived, not `do_not_contact`. Team-wide. Heuristic: an
  answer on any channel clears it. **Logging your send (§ Logging a send
  and a reply) is what clears a reply** — check this list before saying
  "nobody answered X".
- `clients_to_contact` (10) — Client Pulse overdue clients; `enabled:
  false` + empty when the project's pulse is paused.
- `best_prospects` (10) — highest fit scores of `prospect` accounts
  nobody is working (never contacted, no open next step, not shortlisted
  or contacted in any campaign, not "not a fit" or deferred for that product + goal,
  no opt-out for that goal, not a pure marketing partner; `mismatch`
  never). One row per account (its best eligible score, deduped before
  the top 10 is cut, so 10 rows whenever `count` ≥ 10) with
  `product_name`, `goal`, `score`, `score_label`, `top_reason`; `count` =
  distinct accounts.

Scoring runs: `GET /api/dashboard/scoring-runs/?project=` → `results[]`
`{campaign_id, campaign_name, status, run_total, run_processed, progress,
started_at, finished_at, summary{error, cancelled_at, newly_scored, …},
api_cost{total (USD string), currency, call_count, total_input_tokens,
total_output_tokens, by_model[]}}` (the standard api_cost block); cancel one with
`POST /api/campaigns/{id}/cancel-scoring/`. Imports / enrichment /
searches stay on `GET /api/research/?project=`.

UI (link these when reporting): Today = `/dashboard`; Runs =
`/dashboard/runs` (the old `/dashboard/tasks` redirects there); Insights =
`/dashboard/insights?tab=funnel|breakdown|usage` (old `/dashboard/stats`
and `/dashboard/usage` redirect). Sidebar: Today · Accounts · Campaigns ·
Clients · Marketing · Insights · Runs · Settings.

## Marketing actions and results (2026-10-08, not deployed yet)

Contract: [API.md § Marketing actions and results](../../../humans2agents/agents/leadhunter/backend/docs/API.md#marketing-actions-and-results-m2-2026-10-08).
An **action** = one collaboration / placement with a partner (reel,
article, fair booth, newsletter slot…). It is a channel with
`action_type` set, so it lives on `/api/channels/`; `account` = the
partner.

- List: `GET /api/channels/?project=<slug>&is_action=true[&partner=<account uuid>&action_stage=…&action_type=…&search=…]`.
  Each row has a `results` block: `reach` (manual), `clicks`, `accounts`
  (attributed, partners excluded), `trials` (in trial now or ever),
  `clients` (status customer now), `revenue_*`, `cost_*` (in-kind
  included), `cost_per_client`, `roi_ratio` (null + reason when currencies
  differ). Add `&summary=none` for slim option rows.
- Create: `POST /api/channels/ {"project", "label": "<name, required>",
  "action_type": "event_booth|post|reel|video|article|ad|podcast|newsletter|event_talk|sponsorship|giveaway|affiliate_deal|other",
  "account": "<partner uuid>", "started_on", "published_on", "ended_on",
  "manual_reach", "content_links": [...], "promo_code"}`; `kind` is
  optional (defaults from the type: event_* / sponsorship → event, post /
  reel / video / giveaway → influencer, affiliate_deal → referral, else
  partner). The stage starts at `idea`; change it with
  `POST /api/channels/{id}/change-action-stage/ {"stage": "proposed|agreed|scheduled|published|done|cancelled", "reason"}`
  (PATCH ignores it). In-kind costs: `POST /api/channel-expenses/` with
  `"in_kind": true` at list price.
- **Attribute accounts to an action (first touch, one per account)**:
  `POST /api/channels/{id}/attribute-accounts/` with ONE of `account_ids`
  / `names` (matched ignoring case, accents, punctuation) / `list_query`
  (+ `all: true` if it narrows nothing, else 400 with `matched`; a
  `list_query.project` other than the channel's → 400 keyed `list_query`;
  `account_ids` must be non-empty and may name archived accounts).
  **Dry run by default** (it ignores `expected_count`): show the
  plan (`counts.will_attach / already_this / has_other_channel`,
  `unmatched_names`, `ambiguous_names`) to Oriol, then repeat with
  `"dry_run": false, "expected_count": <matched>` (409 if the set
  changed). Accounts on another channel are skipped unless
  `"overwrite": true`. `acquired_at` is set only where empty
  (`acquired_on`, else the action's start / publish day). Status is not
  touched. Server-side the same is `manage.py attribute_accounts_to_action
  --project <slug> --action <uuid> --names-file f.txt` (dry run; `--commit`
  writes) — e.g. the Sea Otter Europe Girona 2026 list on bikecrm: dry
  run, Oriol approves the printed list, then `--commit`.
- One account: PATCH `/api/accounts/{id}/ {"acquisition_channel_obj": "<action uuid>"}`
  (the enum follows the action's kind).
- Who it brought: `GET /api/channels/{id}/attributed-accounts/`.
- Dashboard: `GET /api/marketing/summary/?project=&period_start=&period_end=`
  (actions by action date; totals, `by_action_type`, `by_partner_kind`,
  `top_actions`). Per partner: `GET /api/marketing/partner-results/?project=&accounts=<≤100 uuids>`.
- UI: Marketing dashboard `/dashboard/marketing`, Actions
  `/dashboard/marketing/actions`, an action `/dashboard/marketing/actions/<id>`.
- Auto-attach never puts an enum-only account on an action; attribution
  to actions is always explicit.

## Logging a send and a reply

After the message has actually gone out:

```jsonc
POST /api/messages/
{"campaign_lead": "<CampaignAccount uuid>",      // or "account": "<uuid>" — exactly one
 "direction": "outbound", "channel": "email",    // email|whatsapp|linkedin|instagram|twitter_x|phone_call|sms|other
 "original_text": "…", "original_language": "ca",
 "generation_mode": "log_sent", "status": "sent",
 "sent_at": "2026-10-03T09:12:00Z",
 "external_id": "<Message-ID or WAHA id>"}
```

- **Use `campaign_lead` whenever the account is in a campaign.** The
  funnel (`initiated` / `responded`) counts per CampaignAccount, and
  `outreach_status` advances (`sent` → `responded`) only through it.
  Campaign-less (`account`-only) messages are stored but invisible to the
  funnel: a project whose sends were all logged without `campaign_lead`
  shows a funnel of 0 however many messages it holds.
- **Always pass `external_id`** (email `Message-ID`, WAHA message id): a
  retry returns 200 with the existing row instead of a duplicate.
- Reply: same call with `"direction": "inbound"`,
  `"generation_mode": "inbound_paste"`. Inbound is never DNC-blocked.
- Outbound to a DNC account → 403. `direction` and `campaign_lead` are
  immutable after create; a sent message can't go back to draft.
- **`purpose`** (LeadHunter `3727c9a`, deployed 2026-10-05): every message
  carries the outreach purpose it serves, a campaign-goal value (`sales`,
  `partnership`, `press`, `influencer`, `investor`, `recruiting`,
  `customer_expansion`, `win_back`, `event`, `research`, `renewal`). A
  campaign message gets its campaign's goal (omit `purpose`). An
  **account-only outbound** message on an account with per-purpose opt-outs
  (`do_not_contact_purposes` non-empty) MUST send `purpose`: without it →
  400 `{"purpose": ["This account opted out of sales outreach. Say which
  purpose this message serves."]}`, an opted-out purpose → 403. Pick the
  purpose the message really serves (a reply to a customer's question is
  not `sales`); never pick one just to get past a 403 — that is an opt-out,
  ask Oriol. Accounts without opt-outs and inbound messages: unchanged.
- A foreign or unknown `account` / `campaign_lead` answers the same 400
  ("does not exist") — check the id, not your access.
- Edits lock the row: a PATCH can't undo a send that committed meanwhile;
  a sent message's `purpose` is fixed (echoing the stored value is fine).
- Reading a thread: § Reading (messages row). Humans read the same stream
  at `/dashboard/accounts/<id>/conversations`.

## Account notes

`POST /api/accounts/{id}/add-note/ {"text": "…"}` appends
`[YYYY-MM-DD <your email>] text` to `Account.notes` in one UPDATE (no
GET+PATCH race; 5,000 chars). The UI renders notes as Markdown and those
dated lines as a log. Put **what happened** there; put **what must happen
next, with a date**, in a next step (below), not in a note. Never PATCH the
whole `notes` field from a stale copy (it overwrites a human's edit).

## Next steps

Something due on an account (live since 2026-10-06; contract
[backend/docs/API.md § Next steps](../../../humans2agents/agents/leadhunter/backend/docs/API.md),
design [NEXT_STEPS.md](../../../humans2agents/agents/leadhunter/backend/docs/NEXT_STEPS.md)).
They feed the account's Next steps card, the bell, `/dashboard/follow-ups`,
a daily email digest to the assignee (07:00 Madrid) and their calendar
feed. **When a meeting, call or message ends with a commitment, record it
here** — LeadHunter is the canonical list; no Todoist integration exists
or should be built (Oriol, 2026-10-07).

```jsonc
POST /api/next-steps/
{"account": "<uuid>",
 "text": "Send the 2027 prices",
 "side": "ours",                 // ours | theirs ("waiting for their client list")
 "due_on": "2026-10-15",         // optional; 1900–2999
 "due_time": "16:30",            // optional, needs due_on
 "assignee": "<user uuid>",      // optional, defaults to the caller; must be an active project member
 "contact": "<contact uuid>",    // optional, same account
 "source": "agent:recordings",   // who wrote it
 "external_id": "<stable id>"}   // retries answer 200 with the stored row
```

- Close / move: `POST /api/next-steps/{id}/complete/`, `/cancel/`,
  `/reopen/`, `/reschedule/ {"due_on": "…"}` (the time is **kept** unless
  you send `due_time`; `null` clears it). A done / cancelled step refuses
  date changes (400 "Reopen the step first.").
- Prefer complete / cancel over DELETE (history). `status`,
  `completed_*` are read-only on PATCH.
- **Templates** (live 2026-10-07, `3e204239`): when a step matches a
  quick-add type, create it from the template —
  `GET /api/next-steps/templates/?project=<slug>&status=<account status>`
  lists the project's types (built-ins such as `follow_up`, `book_demo`,
  `send_proposal`, `await_decision`, `await_documents`, `onboarding`,
  `check_trial_usage`, `payment_setup`, plus custom `c_…` keys; none for
  do-not-contact) with `label`, `side` and a `due_offset`
  (`{value, unit}` or null; compute the date from today, months clamp at
  month end). Send `"template_key": "<key>"` on the create (validated
  against the account's project; immutable). `POST …/{id}/complete/` then
  answers `follow_on` (`{key, label, …}` or null — null on a repeat
  complete) = the logical next step to offer, e.g. book_demo →
  prepare_demo; create it only if the user wants it. Editing templates
  is a per-project Settings page (`/dashboard/settings/next-steps`);
  agents don't change templates unless asked.
- **Assign to Oriol** unless told otherwise; an agent token creating a step
  without `assignee` assigns it to the agent's user, whom nobody reminds.
  Find his user id once via `GET /api/projects/<slug>/members/`.
- Dedupe before creating: list the account's open steps first
  (`?account=<id>&status=open`) and update / reschedule a matching one
  instead of adding a twin.
- `bikecrm` Sea Otter accounts still carry the stopgap custom fields
  `next_step` / `next_follow_up` until `migrate_stopgap_next_steps` runs
  there (pending Oriol's go, 2026-10-07); after that, next steps only.

## AI drafts

`POST /api/messages/propose/ {"campaign_lead": "<uuid>", "channel": "email", "continuation": false}`
returns ~3 `variants` (render `variants.length`). Persists nothing; steered
by `Campaign.outreach_brief` and per-account
`CampaignAccount.outreach_directions`. A draft is raw material: the text
that goes out is approved by Oriol word for word (hq growth/outreach).

## Prod shell one-offs

Only for bulk fixes the API can't express (or would take thousands of
calls). When the selection fits the API's filters, a status change goes
through `POST /api/accounts/bulk-change-status/` (one transaction,
history, webhooks), not the shell; the template's `change_status` loop is
for selections only the ORM can make. Swap the loop body for any other
write. Read-only queries need no guard. **Any write
uses this template and nothing else**: run it with `DRY_RUN = True`,
show Oriol the printed counts, and flip it only on his go for those
counts.

```bash
ssh root@91.98.122.198 -p 1922        # jluv-apps-1; MagicDNS may not resolve from minisforum
docker ps --filter name=083x8zai4t2duat7dn2dq6gw   # web app uuid → container
docker exec -i <container> python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
from django.db import transaction
from leadhunterbackend.accounts.models import Account
from leadhunterbackend.accounts.services.status import change_status

DRY_RUN = True   # False only after Oriol's go on the counts below
agent = get_user_model().objects.get(email="agent@humans2agents.com")
with transaction.atomic():
    qs = Account.objects.filter(project__slug="<slug>", ...)   # the exact selection
    print("matched", qs.count())
    for a in qs:
        change_status(lead=a, new_status="<status>", source="<source>",
                      user=agent, reason="[<date>] <why>")
    if DRY_RUN:
        transaction.set_rollback(True)
        print("DRY RUN: rolled back, nothing written")
PY
```

The rollback is complete for `change_status`: its webhook enqueue waits
for commit (`transaction.on_commit`), so a dry run sends nothing. Before
calling any other service in this block, check that its side effects
(Celery tasks, webhooks, mail) also wait for commit (the
[celery-deploy-safety](../celery-deploy-safety/SKILL.md) skill covers
`transaction.on_commit` dispatch). Never paste this
recipe into a heredoc of your own (a `<<'PY'` inside an outer `<<'PY'`
ends the outer one early and runs the rest, `ssh` included, locally).

## Traps

- **Prospect personal data never goes into hq** — exports live in the
  session scratchpad and are deleted; hq notes carry counts and links.
- Nothing is sent to a prospect without Oriol's go on the exact text.
- Clients not marked = they get cold email. Check
  `status=customer` (the guardrail) and `relationship_types=client` counts
  per project before any send, against the last reconciled counts in hq
  ([enantena](../../../../../Syncthing/Syncthing-mobile-docs/hq/growth/enantena/README.md#enacast-clients-marked-in-leadhunter--2026-10-03),
  [smartupsoft](../../../../../Syncthing/Syncthing-mobile-docs/hq/growth/smartupsoft/README.md#all-bikecrm-customers-in-leadhunter--2026-09-28)).
  Neither syncs automatically.
- Build every send through § Send list (exports and old rows skip the
  guardrails).
- Campaign-less logs don't move the funnel (above).
- `page_size` caps at 100.
- **Rate limit: `?search=` loops hit 429** (2026-10-03, 4 parallel
  workers). Go sequential and honour `Retry-After`; ~700 searches take
  ~25 min. A 502 / a hung request usually means a deploy is in flight
  (Coolify `GET /deployments/applications/083x8zai4t2duat7dn2dq6gw`),
  so wait it out, don't retry-storm.
- Matching an external client list: exact email, then email/website
  domain (skip gmail/hotmail/…), then exact normalised name + same town.
  Name-only matches were right for EnaCast radios except foreign
  namesakes (an Italian "Urban Radio"), so check city/country.
