---
name: stripe-billing
description: Set up and operate Stripe Billing (subscriptions, Checkout, Customer Portal, Stripe Tax, webhooks) from the API with one secret key, without the traps that make every checkout fail. Use when creating products/prices, changing a price amount, configuring the Customer Portal or Stripe Tax, registering a webhook, wiring a Django backend to Stripe Checkout, testing a sandbox, or when the user mentions Stripe, sk_test/sk_live, whsec, price ids, lookup keys, VAT/IVA on subscriptions, or "checkout fails". Field-tested on Panotxa 2026-09-23.
---

# Stripe Billing — API-first setup and the traps

Field-tested on Panotxa (personal scope, Django backend, Checkout + Portal +
Stripe Tax, ES VAT) on 2026-09-23. Project facts (ids, prices) live in that
repo's `SUBSCRIPTION.md` "Stripe access"; this skill holds only the mechanics.

## What one key can and cannot do

- **One secret key per mode is enough.** With `sk_test_…` everything in the
  sandbox is API-creatable: products, prices, Customer Portal configuration,
  Stripe Tax settings + registrations, webhook endpoints, customers, Checkout
  Sessions. The publishable key is unused when the backend creates Checkout
  Sessions (redirect flow).
- **Not by API**: activating the account for live charges (business details,
  identity, bank) — dashboard only for a standard account. `charges_enabled=false`
  in `GET /v1/account` means not activated.
- **Sandbox and live are separate worlds**: a test key never sees live
  objects. Going live = run the same setup again with the live key (new price
  ids, new webhook secret). Never put an `sk_test_` on prod.
- For a deployed backend prefer a **restricted key** (`rk_live_…`) scoped to
  Products, Prices, Customers, Checkout, Subscriptions, Billing Portal,
  Webhooks and Tax.
- The account id is in `GET /v1/account` (`acct_…`); keys never expire, they
  are rolled in Dashboard → Developers → API keys. A 401 = rolled/revoked key.

Credentials follow the estate rules (`secrets-in-git` skill): the key goes in
the scope's secrets store, never in the project repo; local dev gets it in the
gitignored env file.

## Setup: make it a script, not clicks

Write an idempotent, stdlib-only setup script in the repo (reference:
Panotxa `backend/scripts/stripe_setup.py`): dry run by default, `--apply`
creates only what is missing, finds prices **by `lookup_key`** so a re-run never
duplicates, prints the `STRIPE_PRICE_*` env values, and warns when an existing
price's amount differs from the code. Same script for sandbox and live — the key
decides. Pin `Stripe-Version` to the backend SDK's version.

## Traps (each one verified)

1. **`tax_id_collection` on an existing customer needs
   `customer_update[name]=auto`**, or Checkout Session creation fails with
   "Tax ID collection requires updating business name on the customer". A
   backend that always passes `customer=` (get-or-create customer first) hits
   this on EVERY B2B checkout. Unit tests with a mocked Stripe never catch it —
   create one real sandbox session with the backend's exact parameters.
2. **`automatic_tax` needs a tax code on every line item** (product
   `tax_code`, e.g. `txcd_10103001` SaaS) or a default in tax settings, plus
   active tax settings (head office address) and a registration for the
   country. Missing → "You must specify a tax code in all line items".
3. **Prices are immutable.** A new amount = a new price created with the same
   `lookup_key` and `transfer_lookup_key=true`, then the old price
   `active=false`. The price id changes, so the env vars change too.
4. **`tax_behavior` is per price**: consumer (B2C) prices `inclusive`, B2B
   prices `exclusive` (quote them "+ VAT" everywhere).
5. **Customer Portal `subscription_update.products` is not returned unless
   expanded** — `expand[]=features.subscription_update.products`. Without it a
   successful update looks like it did nothing.
6. **Portal `adjustable_quantity` defaults to enabled** when you list
   products: a consumer could buy quantity 2 of a single-seat plan. Set
   `features[subscription_update][products][0][adjustable_quantity][enabled]=false`,
   and list only the products customers may switch between (not per-seat B2B
   prices whose quantity the backend syncs).
7. **The webhook signing secret (`whsec_…`) is returned once, on creation.**
   Store it in the secrets store in the same step.
8. **Do not register a sandbox webhook pointing at prod** when prod has no
   Stripe config: every event fails and Stripe eventually disables the
   endpoint. Without a staging backend, test webhooks locally: `stripe listen
   --forward-to …`, or (no CLI) replay real sandbox events signed with
   `t=<ts>,v1=HMAC-SHA256(secret, "<ts>.<body>")` (Panotxa
   `backend/scripts/stripe_replay_events.py`).
9. **curl form bodies: `+` in an email becomes a space** (`-d email=a+b@x`
   → "Invalid email address: a b@x"). Use `--data-urlencode`.

## Verification before calling it done

- `GET /v1/account` (right account, mode), `GET /v1/tax/settings` (`status:
  active`), `GET /v1/tax/registrations`.
- One real Checkout Session per price combination with the backend's exact
  kwargs (subscription mode, automatic tax, customer update, tax id
  collection) — `status: open` proves the configuration, no payment needed.
- Then the manual walk: pay with `4242 4242 4242 4242`, failed payment with
  `4000 0000 0000 0341`, portal switch/cancel, webhook rows processed.
