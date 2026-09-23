---
name: revenuecat
description: Set up and verify RevenueCat for in-app subscriptions (Google Play + App Store) with a backend that trusts the webhook — key kinds and where each may go, the Test Store trap, reading the dashboard with a public key, the entitlement/package contract between dashboard, app and backend, webhook Authorization, and lifetime (non-renewing) purchases. Use when adding RevenueCat to an app, handling RevenueCat keys (test_/goog_/appl_/sk_), configuring entitlements/offerings/packages, wiring or debugging the RevenueCat webhook (401s, "purchase went through but no access"), or when the user pastes RevenueCat's onboarding prompt. Field-tested on Panotxa 2026-09-23.
---

# RevenueCat

Field notes from Panotxa (Capacitor app + Django backend, 2026-09-23). The
project-specific record lives in that repo's `REVENUECAT.md`; this skill is
the reusable part.

## The model

RevenueCat sits between the stores and your backend. **The backend should
trust the webhook, not the app**: the SDK's `customerInfo` is a UI hint for
the "purchase went through" moment, and the webhook upserts the subscription
row that access decisions read. Identify the customer with YOUR user id
(`Purchases.logIn(<user uuid>)`), never an anonymous RevenueCat id, so the
webhook's `app_user_id` names an account you can find.

## Key kinds — where each may go

| Prefix | What | Where it may go |
|---|---|---|
| `goog_` / `appl_` | public SDK key per platform | the app bundle. It is public by design, so hardcode it as a literal default rather than an env var that three build machines can forget |
| `test_` | **Test Store** public SDK key: simulated purchases, no Play or App Store behind them | **local debug builds only**. In a production build a free fake "purchase" reaches the production webhook and grants access. Make the store-build preflight fail on `test_` unconditionally |
| `sk_` (v2 secret) | project API: configuration + customers | secrets store; a backend only if it reconciles |
| webhook Authorization | a value you invent | secrets store + backend env + dashboard. It must match the **whole** header, `Bearer ` included, if you use that form |

The onboarding wizard hands out a `test_` key first, with a generic "integrate
the SDK" prompt. That key is not a production key.

## Reading the dashboard without a secret key

A public key can read the offerings:

```bash
curl -s -H "Authorization: Bearer $PUBLIC_KEY" -H "X-Platform: android" \
  "https://api.revenuecat.com/v1/subscribers/<any-id>/offerings"
```

The answer gives `current_offering_id` and each package's
`platform_product_identifier`. **Entitlements cannot be read with a public
key.** Changing the configuration (entitlements, products, offerings,
packages) needs a v2 secret key or the dashboard. Store connections (a Play
service-account JSON, an App Store in-app purchase key) and store agreements
are dashboard-only.

## The contract that silently breaks

Three places must agree, and a mismatch shows no error, only purchases that
grant nothing:

1. **Entitlement identifier.** The wizard proposes `<app>_pro` style names.
   If the app and backend check `premium`, every purchase is ledgered as
   "no entitlement" and access never arrives. Entitlement identifiers are
   effectively permanent: create the one the code expects, attach the
   products, delete the wrong one — or change both code sides together.
2. **Package identifiers** (`$rc_monthly`, `$rc_annual`, `$rc_lifetime`): the
   app picks packages by id from the current offering; unknown ones are
   ignored.
3. **Product ids → plan.** A backend that infers the plan from the product id
   (`yearly`/`annual` → annual, `lifetime` → lifetime) needs every id to
   follow that naming on BOTH stores (Play `product:base_plan`, App Store
   flat id).

Also: do **not** configure a store introductory trial if the backend runs
its own trial. The two stack.

## Webhook

- URL on your API, with Authorization = the invented value. An empty backend
  secret must reject everything (401), never accept.
- Compare with `hmac.compare_digest` on **bytes**: a non-ASCII header makes
  the str version raise TypeError, which answers 500.
- Prove it live with the dashboard's *Send test event*, or a hand-made
  `{"event": {"type": "TEST", "id": "…"}}` POST carrying the stored value.
  The backend should ledger it as `ignored`. A 401 means the value differs:
  check by hash, never by printing, and check that the container was
  restarted after the env change.
- RevenueCat retries 5 times (~2.5 h), then gives up. Keep a
  "last delivery received" metric, or a silent pipe looks like zero sales.
- Events worth handling: `INITIAL_PURCHASE`, `RENEWAL`, `PRODUCT_CHANGE`,
  `CANCELLATION` (three meanings: auto-renew off, refund, store-side),
  `UNCANCELLATION`, `EXPIRATION`, `BILLING_ISSUE` (grace), `TRANSFER`
  (restore into another app user: move the rows), `SUBSCRIPTION_EXTENDED`,
  `NON_RENEWING_PURCHASE`, `TEST`.
- Test Store events carry their own `store` value. Force them to the sandbox
  environment in the backend so they never count as revenue.

## Lifetime (non-consumable)

It arrives as `NON_RENEWING_PURCHASE` with **no `expiration_at_ms`**, so
model it as a plan with no end, not a subscription with a missing date. A
refund comes as `CANCELLATION` with reason `CUSTOMER_SUPPORT`.

## RevenueCat Paywalls / Customer Center

The wizard pushes `@revenuecat/purchases-capacitor-ui` (hosted Paywalls) and
Customer Center. If the app already has its own paywall covering web
(Stripe) and native, with translated copy and server-driven gating, a
RevenueCat Paywall is a second, native-only paywall whose copy lives outside
your i18n catalogs. Keep your own paywall. Customer Center is a reasonable
later add for native "manage subscription".

## Capacitor specifics

- Import `@revenuecat/purchases-capacitor` **dynamically**, behind a
  native-only guard. Its web shim throws, and the PWA must never load it;
  keep it out of the shared vendor chunk.
- Serialize `logIn`/`logOut` with purchases and restores in one queue, so an
  account switch cannot land mid-purchase.
- After a purchase, poll the backend (5–60 s typical, 90 s cap) rather than
  trusting `customerInfo`.
