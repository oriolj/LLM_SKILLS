---
name: leadhunter
description: Operate H2A-LeadHunter, the system of record for leads and outreach across every scope (EnaCast, SmartupSoft/BikeCRM, …), through its REST API — auth with the agent token, organizations → projects, reading accounts/campaigns/funnel stats, exporting campaign lists, marking clients and do-not-contact, logging an email/WhatsApp send and its reply so the funnel counts it, and AI drafts. Use when the user mentions LeadHunter, leads, prospects, "mark our clients", "log that message", "who did we contact", outreach funnel, cold-email campaign lists, relationship_types, or do-not-contact; and before any cold outreach send.
---

# LeadHunter — leads and outreach log

H2A-LeadHunter (`leadhunter.humans2agents.com`, personal scope, code in
`~/git/oriolj/humans2agents/agents/leadhunter/`) holds every lead of every
product: accounts, contacts, campaigns, AI scores, and the log of what was
sent and answered. **It logs outreach; it does not send it.** A message
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
| Campaign inbox (latest message per account) | `GET /api/campaigns/{id}/inbox/` |
| Messages | `GET /api/messages/?project=…` or `?lead=<account_id>` |
| Funnel | `GET /api/dashboard/stats/?project=<slug>` or `?organization=<slug>`; per product/campaign `GET /api/dashboard/breakdown/?project=<slug>` |

Pagination: `count/next/previous/results`, default 20, **max 100**
(`page_size=500` silently gives 100). Always loop on `next`.

## Account fields that gate outreach

- `status` (lifecycle, single): `prospect`, `contacted`, `in_negotiation`,
  `in_trial`, `customer`, `lost`, `do_not_contact`. **Read-only on PATCH**:
  change it with `POST /api/accounts/{id}/change-status/`
  `{"status","reason","source"}` (writes history, fires webhooks).
- `relationship_types` (multi): `client`, `prospect`, `reseller`,
  `affiliate`, `supplier`, `partner`, `investor`, `press`, `influencer`,
  `analyst`, `competitor`, `candidate`, `personal_network`. PATCHable on
  `/api/accounts/{id}/` — send the **whole** array (it replaces).
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
  press / analyst / candidate (`include_<type>`, per goal).
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
  # goals.py 2026-10-03: soft relationship blocks per goal (all 5 = sales set)
  ["supplier", "investor", "press", "analyst", "candidate"] as $all5
  | {sales: $all5, partnership: [], press: ["supplier", "investor", "candidate"],
     influencer: ["supplier", "investor", "candidate"],
     investor: ["supplier", "press", "analyst", "candidate"],
     recruiting: ["supplier", "investor", "press", "analyst"],
     customer_expansion: $all5, win_back: $all5, event: [], research: [],
     renewal: $all5}[$goal] as $soft
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
  immutable after create.

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
