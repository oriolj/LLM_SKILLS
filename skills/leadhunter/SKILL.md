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
`agents/leadhunter/backend/docs/API.md` (+ `GLOSSARY.md`, `docs/models/`).

## Access

- Token + base URL: hq `homelab/secrets/h2a-leadhunter.env` —
  `H2A_LEADHUNTER_API_TOKEN`, `H2A_LEADHUNTER_API_URL`
  (`https://leadhunter.api.humans2agents.com`). Parse with grep/cut, never
  `source`, never print the token.
- Header `Authorization: Token <token>`, and always a full current Chrome
  UA (a truncated `Mozilla/5.0` got a non-JSON answer on 2026-10-03).
- User `agent@humans2agents.com` (no usable password), ProjectUser
  `member`. **Visibility is per project membership**: a project the agent
  was not added to is invisible (organizations list only member projects,
  stats return zeros, `?project=` returns 400). Check `GET /api/projects/`
  first. Verified 2026-10-03: sees enacast, bikecrm, fichachat, motorcrm,
  petcrm.
- 401 = token revoked (Token row deleted in Django admin) → ask Oriol.
- Throttle: 200 req/min per user; LLM actions (propose, scoring, enrich)
  share 60/min. 429 carries `Retry-After`.

```bash
H=~/Syncthing/Syncthing-mobile-docs/hq/homelab/secrets/h2a-leadhunter.env
T=$(grep '^H2A_LEADHUNTER_API_TOKEN=' $H | cut -d= -f2-); U=$(grep '^H2A_LEADHUNTER_API_URL=' $H | cut -d= -f2-)
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
lh() { curl -s -A "$UA" -H "Authorization: Token $T" "$U$1"; }
lh /api/organizations/
```

## Tenancy

**Organization** groups **projects**; the project is the data tenant
(since 2026-09-28). Today: `enacast` → `enacast`; `smartupsoft` →
`bikecrm`, `petcrm`, `motorcrm`, `fichachat`. Every endpoint takes
`?project=<slug-or-uuid>`; an unknown or foreign one → **400** (accounts,
messages) — except `GET /api/campaigns/?project=` which answers an empty
page.

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
| Campaign list for a send | `GET /api/campaigns/{id}/export-accounts/?review_status=approved\|all&fields=name,email,contact_email,score,score_label,language,relationship_types,…` (CSV; unknown field → 400) |
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

Guardrails when adding to a campaign (`bulk_add`, `bulk-add-from-filter`)
and on logging an outbound message:

- **Hard, never overridable**: `status=do_not_contact`, a goal in
  `do_not_contact_purposes`, `personal_network` (any goal), `competitor`
  (all goals except press / event / research).
- **Soft** (sales goal): `status=customer` (`include_customers`),
  supplier / investor / press / analyst / candidate (`include_<type>`).
- **Mark existing clients before any cold campaign — and the guardrail
  keys on `status=customer`, NOT on `relationship_types` `client`**
  (`campaigns/services.py::partition_leads_by_status`, checked 2026-10-03).
  A `client` tag alone does not keep an account out of a sales campaign.
  Set both: tag `client` and `change-status` to `customer`. Side effect:
  every `→ customer` history entry counts as `closed` in the funnel on
  that day, so a bulk backfill shows a fake spike of wins; say so in the
  hq record (or backfill through the shell without a history entry, if
  Oriol prefers clean stats).

## Logging a send and a reply

After the message has actually gone out:

```json
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
  funnel — verified 2026-10-03: BikeCRM's 33 WhatsApp messages are all
  campaign-less and its 30-day funnel reads 0.
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

Bulk fixes the API can't express (or would take thousands of calls):

```bash
ssh root@91.98.122.198 -p 1922        # jluv-apps-1; MagicDNS may not resolve from minisforum
docker ps --filter name=083x8zai4t2duat7dn2dq6gw   # web app uuid → container
docker exec -i <container> python manage.py shell <<'PY'
from leadhunterbackend.accounts.models import Account
from leadhunterbackend.projects.models import Project
...
PY
```

Prefer the API (status changes via the service keep history and webhooks);
in the shell call the same services (`accounts.services.status.change_status`).
Dry-run first, print counts, then write.

## Traps

- **Prospect personal data never goes into hq** — exports live in the
  session scratchpad and are deleted; hq notes carry counts and links.
- Nothing is sent to a prospect without Oriol's go on the exact text.
- Clients not marked = they get cold email. Check
  `status=customer` (the guardrail) and `relationship_types=client` counts
  per project before any send (2026-10-03: enacast 0 / 0, bikecrm 84 / 84).
- Campaign-less logs don't move the funnel (above).
- `page_size` caps at 100.
