---
name: holded
description: Work with the Holded ERP API (v2 with a Bearer token, and the legacy v1 key) without the usual traps — reading invoices, purchases, credit notes, contacts, the ledger, payslips and bank movements, reconciling a bank movement against its documents, the monthly account-wide call quota that v1 calls also spend, cursor pagination, scopes per endpoint, comma-decimal money strings, and how v1 and v2 report the same document differently (foreign currency, drafts). Use when the user mentions Holded, "the books in Holded", bank reconciliation or "conciliar" in Holded, a Holded API key or token, a 403 or 429 from api.holded.com, the Holded MCP server, or when a task reads or writes accounting data for a company whose books are in Holded (quarter close, missing invoices, bank movements without a document). Ships scripts/holded.py, a GET-only client and an offline reader of Holded's OpenAPI spec.
---

# Holded API

Holded is the ERP that holds a company's books: sales, purchases, contacts, the
ledger, payroll and the bank feed. It has two APIs and no sandbox, so every call
runs against real books.

Verified on 2026-10-12 against one company on the Standard plan. Each claim
below is marked **verified** (a live call returned it) or **spec** (read in
Holded's OpenAPI file, not called). Holded changes this API fast: the spec had
109 paths on 2026-10-05 and 221 a week later. Re-check a spec-only claim before
relying on it, and correct this file when a call behaves differently.

## Three rules before the first call

1. **Calls cost quota, and the quota is shared.** Limits are per Holded
   account, not per key: a per-minute window and a **monthly** quota, and v1
   calls count too (verified: `GET /api/v2/usage` listed 1,254 `api_v1_legacy`
   calls made by another integration). Plans below Premium stop with 429 for
   the rest of the month when it runs out, which would also stop every other
   integration of that company. Run `holded.py --scope <s> usage` before a
   batch, fetch a date range once and work on the saved JSON, and never look
   documents up one by one in a loop.
2. **Read freely, write only what the owner approved.** There is no sandbox
   and several writes cannot be undone through the API (reconciling a
   movement, approving a document). A write needs the owner's approval of that
   specific change; do the first one of a kind on a single item and look at
   the result in Holded before doing more.
3. **Pick the API on purpose.** v2 for anything new. v1 only where a system
   already uses it. The two do not return the same figures for the same
   document (see [v1 and v2 disagree](#v1-and-v2-disagree)).

## Access

| | v1 (legacy) | v2 |
|---|---|---|
| Base | `https://api.holded.com/api/{invoicing,accounting,team}/v1` | `https://api.holded.com/api/v2` |
| Auth | header `key: <api key>` | header `Authorization: Bearer <token>` (tokens start with `pat_`) |
| Credential | one key per account | a token with chosen permission scopes |
| Status | "deprecated but still available for existing integrations" | current |

- A v1 key answers **403 "Access denied"** on every v2 route (verified). v2
  needs its own token: Holded → Settings → Developers → Credentials → Add API
  Token, choosing the permissions
  ([Holded help](https://help.holded.com/en/articles/6896051); Holded's own
  developer pages say "Settings → API", which is not where it is). The token is
  shown once.
- Every v2 endpoint names the scope it needs, in the form
  `area:resource.read|write` (`accounting:banks.read`, `sales:invoices.read`,
  `accounting:purchases.write`…). A token without it gets 403. Ask for read
  scopes first and add a write scope when a write has been agreed.
- 401 = missing, mistyped or revoked token. 403 = valid token, missing scope
  (or a v1 key on v2). Neither is fixed by retrying.
- Where a credential lives is estate state, not part of this skill. In Oriol's
  estate: v2 tokens in hq `homelab/secrets/holded-<scope>.env`
  (`HOLDED_<SCOPE>_API_TOKEN`), v1 keys in the H2A-Accountant database; the
  hq `CLAUDE.md` catalog says which exist. Load the `secrets-in-git` skill
  before touching either.

## The helper

[`scripts/holded.py`](scripts/holded.py) is GET-only by construction and never
prints the token.

```bash
S=~/git/oriolj/LLM_SKILLS/skills/holded/scripts/holded.py
python3 $S --scope smartupsoft usage                 # quota used / limit, per endpoint
python3 $S --scope smartupsoft accounts              # banking accounts, feed state, pending count
python3 $S --scope smartupsoft movements <account-id> --from 2026-07-01 --to 2026-09-30 --json > q3.json
python3 $S --scope smartupsoft get /api/v2/purchases start_date=2026-07-01 end_date=2026-09-30 --all > purchases.json
python3 $S spec --tag "Banking accounts"             # endpoints and scopes, offline, no quota
python3 $S spec --path /api/v2/payments --method post  # parameters, body and responses of one endpoint
python3 $S spec --grep reconcile
```

`spec` downloads `https://api.holded.com/openapi/api2.json` (5 MB) into
`~/.cache/holded/` and refreshes it weekly (`--refresh` to force). **Read the
spec with it before calling an endpoint you have not used**: it costs nothing,
and the endpoint's own description is more reliable than the spec's
introduction. Never commit the spec file to a repo.

## Conventions (v2)

- **Lists** answer `{"items": [...], "cursor": "...", "has_more": true}`
  (verified). Pass `cursor` back for the next page and stop when `has_more` is
  false. The spec's introduction says `page` and `limit`; that is wrong.
- **Page size** differs per endpoint: the guide says default 25, maximum 100;
  bank movements and purchases default to 50 with a maximum of 200 in the
  spec (verified: 200 accepted on movements, 100 on purchases).
- **Dates** are ISO strings (`"2026-07-01"`, bank movements carry full
  timestamps). Date filters are `start_date` / `end_date`, inclusive.
  `ledger-entries` requires both and answers 400 without them (verified).
- **Money is a string, in two formats** (verified): documents use a decimal
  comma (`"62,87"`), bank movements a dot (`"-62.87"`). `holded.money()` reads
  both. Never `float()` a document amount.
- **Field names** are snake_case (`document_number`, `contact_name`,
  `approved_at`, `currency_change`); v1 used camelCase (`docNumber`).
- **Document ids are the same in v1 and v2** (verified: a v1 purchase id
  answered 200 on `GET /api/v2/purchases/{id}`), so an id stored by a v1
  integration can be used in v2 calls.
- **Errors** are problem+json: `{"type": "https://api.holded.com/problems/…",
  "title", "status", "detail"}` (verified for 400 and 403). 422 = valid JSON
  that a business rule refused; 423 = the resource is locked by a concurrent
  update.

## Limits

From Holded's [limits page](https://www.holded.com/developers/rate-limiting)
(read 2026-10-12) and the `usage` endpoint (verified):

| Plan | Requests / minute | Calls / month |
|---|---:|---:|
| Plus | 60 | 500 |
| Basic | 60 | 2,000 |
| Standard | 120 | 7,500 |
| Advanced | 120 | 30,000 |
| Premium | 600 | 100,000 + billed overage |

- Counters are **account-wide**: more keys do not add budget.
- `GET /api/v2/usage` (scope `developers:usage.read`) returns `period`,
  `usage`, `limit` and `secondary_usages`, a count per endpoint, with v1 as
  `api_v1_legacy_1`. It is the way to find which integration spends the quota.
  The call itself is counted.
- A 429 carries `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
  `X-RateLimit-Reset` and `X-RateLimit-Window` (`minute` or `month`) (from the
  limits page; a normal 200 carried none of these headers, verified). On
  `month`, stop: waiting does not help until the next period.
- The "100 requests per minute per API key" in the spec's introduction and on
  the errors page contradicts the limits page and the usage response.

## Endpoints for accounting work

`spec --tag <name>` lists the rest; the spec has 47 tags (CRM, projects, stock,
bookings, time tracking and more).

| What | Call | Scope | State |
|---|---|---|---|
| Banking accounts | `GET /treasury/accounts` (`type`, `archived`) | `accounting:banks.read` | verified |
| Bank statement lines | `GET /treasury/accounts/{id}/bank-movements` (`start_date`, `end_date`, `status`, `limit`) | `accounting:banks.read` | verified |
| Cash-account lines | `GET /treasury/accounts/{id}/cash-movements` | `accounting:banks.read` | spec |
| Reconcile a movement | `POST /treasury/accounts/{accountId}/bank-movements/{movementId}/reconcile` | `accounting:banks.write` | verified (one document per movement, same amount; 62 calls) |
| Payments | `GET /payments` (`start_date`, `end_date`, `document_id`, `document_type`, `banking_account_id`) | `accounting:payments.read` | verified (list) |
| Sales invoices, credit notes | `GET /invoices`, `GET /credit-notes` (`start_date`, `end_date`, `status`, `approval_status`, `contact_id`) | `sales:invoices.read` | verified (list) |
| Find a sales invoice by number | `GET /invoices/find-by-number` | `sales:invoices.read` | spec |
| Purchases | `GET /purchases` (same filters), `GET /purchases/{id}` | `accounting:purchases.read` | verified, `approval_status` and dates included |
| Approve a document | `POST /invoices/{id}/approve`, `POST /purchases/{id}/approve`, `POST /invoices/bulk/approve` | `sales:invoices.write`, `accounting:purchases.write` | spec |
| Ledger | `GET /ledger-entries` (`start_date`*, `end_date`*, `account`) | `accounting:daily-ledger.read` | verified (400 without dates) |
| Chart of accounts | `GET /accounting-accounts` | `accounting:chart-of-accounts.read` | spec |
| Payslips | `GET /payslips` (`start_date`, `end_date`, `employee_id`, `kind`, `is_draft`) | `accounting:payrolls.read` | verified (list, empty) |
| Contacts | `GET /contacts` (`code`, `email`…), `GET /contacts/search` | `contacts:contacts.read` | verified (list) |
| Incoming documents (OCR inbox) | `GET /inbox`, `POST /inbox`, `POST /inbox/{id}/export` | `inbox:inbox.*` | spec |
| Usage | `GET /usage` | `developers:usage.read` | verified |

All paths are under `/api/v2`. `status` on a document is one of `pending`,
`completed`, `partial`, `cancelled`, `failed`, `overdue`, `outstanding`;
`approval_status` is `draft` or `approved`.

### Bank accounts and movements (verified)

- An account carries `type` (`bank`, `card`, `gateway`, `cash`),
  `institution_name`, `institution_id` (a slug such as `qonto`), `iban`,
  `bic`, `account_number`, `accounting_account_id` and
  `accounting_account_number`, `balance`, `archived`, **`synced_at`** and
  **`transactions_pending_to_reconcile`**. A payment-gateway account has no
  IBAN; its `account_number` is the processor's account id. A recent `synced_at` on an
  unarchived account means the bank feed is alive; do not infer that an
  account is closed from its paperwork.
- A movement carries `id` (24 hex characters, like a document id),
  `banking_account_id`, `description` (the bank's text), `note`, `amount`
  (signed, account currency), `balance`, `accounting_amount` and
  `accounting_currency` (null on unreconciled euro movements), `flagged_at`,
  `booking_date` and `value_date` (full timestamps),
  `status` (`pending`, `reconciled`, `partial`, `forced_reconciled`),
  `reconciled_amount` and `origin` (the feed provider, e.g. `bankin`,
  `afterbanks`, or `manual`, `stripe`).
- Movements come ordered by value date, newest first. Cash accounts return
  nothing here; use `cash-movements`.

### Reconciling (verified, 2026-10-12)

`POST …/bank-movements/{movementId}/reconcile` with
`{"documents": [{"document_id": "…", "document_type": "purchase"}]}`.
`document_type` is one of `invoice`, `salesreceipt`, `purchase`, `creditnote`,
`purchaserefund`, `payroll`, `payment`, `remittance`, `purchasereceipt`,
`collection`, `receipt`, `entry`. One document closes the movement; several
split it. An empty body marks the movement reconciled against nothing.

What one real call did (a euro card charge against an unpaid euro purchase of
the same amount, verified): the POST answered **200 with the body `null`**.
The movement went from `pending` to `reconciled` with `reconciled_amount`
equal to its amount. The purchase went from `pending` to `completed`, with
`payments_pending` at zero and a new entry in `payments_detail` dated on the
movement's value date and carrying the banking account id. That payment is
also listed by `GET /payments?document_id=…&document_type=purchase`, with
`reconciliation_status: "reconciled"`. So a reconciliation **creates a
payment**; nothing has to be created beforehand. Read the movement and the
document before and after every first call of a batch. Splitting across
several documents, the empty body, partial amounts and foreign-currency
documents are still spec only.

A batch of 61 more followed (one POST per movement, 0.8 s apart, each
answering 200) and a re-read confirmed every movement `reconciled` in full
and every purchase paid in full. What kept it safe: a fresh read of movements
and documents right before writing, a guard per pair (movement still
`pending`, document still fully unpaid, same currency, amount equal to the
cent, each id used once), a log written after every call, stopping on any
answer other than 200, and a fresh read after. Checking the pair in v1 works
too: a reconciled purchase shows `status: 1` and `paymentsPending: 0` there.

What makes it dangerous:

- **Not idempotent.** The same movement and document twice answers 422.
  Check the movement's `status` and the document's pending amount before each
  call, and record what was sent.
- **No undo in the API.** The spec has no endpoint that removes a
  reconciliation. A wrong one is fixed by hand in Holded. The payment a
  reconciliation creates has an id and the spec has `DELETE /payments/{id}`;
  whether deleting it also frees the movement has not been tried.
- **423** means another update holds the lock: wait and re-read, do not hammer.
- The empty-body form hides a movement from the pending list with no document
  behind it. That is the opposite of finding the missing invoice; use it only
  when the owner says a movement needs none.

How to run a reconciliation safely:

1. Read once: the movements of the period (`status=pending`), and the
   purchases, invoices and credit notes of a wider period. Save the JSON.
2. Match offline. Purchases are the one-to-one case: vendor name inside the
   bank description, same absolute amount, and the document dated at most
   about 40 days before the charge or 10 after it. A wider window pairs a
   monthly charge with the previous month's invoice and hides the missing
   one (it did, on the first try). Use each document once. Keep the
   ambiguous ones (two candidates, amount off by cents) apart.
3. Movements with no candidate are the result that matters most: each is a
   charge with no document in the books, the missing-invoice list.
4. Show the owner the proposal as a table (movement, document, why). Write
   only what they approve, one movement first.

Cases that are not one-to-one:

- **Payment-processor payouts** (Stripe and the like) are one incoming
  movement for many sales invoices, net of fees. Matching a payout to one
  invoice is wrong. It needs the payout's own breakdown, or the accountant's
  practice (often a clearing account).
- **Foreign-currency invoices**: the bank charge is in the account currency
  and includes the bank's rate, so it will not equal the invoice total. Match
  on vendor and date with a tolerance (total ÷ rate within 4 % worked), and
  see the next section. The bank charge is the real cost in euros.
- **Movements that need no document**: transfers between the company's own
  accounts, loan repayments, tax payments. Classify them first so they do
  not land in the missing-invoice list.
- **Card statements** settled as one monthly movement.

## v1 and v2 disagree

- **Foreign-currency documents.** Holded keeps a document's amounts in the
  company currency. v1 returns those stored figures while labelling them with
  the document currency; v2 returns them multiplied by `currency_change`.
  Verified on one purchase: v1 `total: 66.67, currency: "usd",
  currencyChange: 1.141`, v2 `total: "76,07", currency: "USD"`, and the ledger
  holds 66.67 €. So an integration that writes the foreign figure through v1
  (or re-sends it with a v1 `PUT`) books dollars as euros. When figures look
  off by the exchange rate, compare the ledger entry with the real invoice.
  The rate itself is **not in the v2 purchases list** (its items have no
  `currency_change`); it is on the single-document `GET /purchases/{id}` and
  on the v1 list (`currencyChange`), where one call covers a whole date range.
- **Drafts.** v1 lists show `draft: null` for everything; v2 shows a real
  `draft` boolean and takes `approval_status=draft|approved` as a filter.
  Purchases created through v1 with `approveDoc: false` showed `draft: false`
  and an empty `approved_at` in v2, came back under
  `approval_status=approved` and not under `draft` (verified on a quarter of
  53), and have ledger entries. So an empty `approved_at` does not mean
  "draft" or "not booked"; ask `approval_status` instead.
- **Pagination.** v1 document lists return a whole date range in one response;
  v1 `dailyledger` returns 250 lines a page and `contacts` 500, both with
  `?page=N` until an empty page. v2 is cursor-based everywhere.
- **Dates.** v1 uses unix seconds (`starttmp`, `endtmp`, `date`); cut a period
  in the company's timezone, because an invoice of 1 July is 30 June 22:00
  UTC. v2 uses ISO dates.
- **Custom tax keys.** An account can define its own taxes, listed next to
  Holded's built-in ones (`s_iva_21`, `p_iva_21`…). Match a tax on its exact
  rate and prefer the built-in key; a custom "21.01 %" key once took every
  21 % sale of an integration that compared rates as integers.

## The MCP server

Holded runs a remote MCP server at `https://mcp.holded.com/mcp` (OAuth 2.1,
Streamable HTTP; [docs](https://www.holded.com/developers/mcp)). Connecting it
creates an access token in the Holded account with the role chosen at
authorisation: Analyst (read only), Operator (read and write) or custom
scopes. It spends the same quota. Not tried here; a scoped token and this
script are enough for scripted work, and the MCP is an option for ad-hoc
questions if the owner connects it (Analyst first).

## Where the rest lives

- A company's state (which accounts exist, what a check found, what is
  pending) belongs to that company's notes, never to this skill. In Oriol's
  estate: hq `<scope>/taxes/` and the hq `taxes` skill for the quarter check.
- The H2A-Accountant app's own integration (v1 client, uploads, the v2
  migration plan) is documented in its repo: `agents/accountant/docs/holded_api.md`
  and `docs/todo.md`.

## Who verified what

2026-10-12: the first pass, by the session that wrote this skill, and a second
set of reads by the session building bank review into H2A-Accountant (list
fields, page sizes, the missing `currency_change`). The reconcile POST was
called that evening on one movement the owner approved, then on 61 more.

## Keeping this current

After any Holded work: move a claim from **spec** to **verified** when a call
confirms it, correct it when the call disagrees, and add the trap that cost
time. Record the date. A new endpoint family goes in the table with its scope.
