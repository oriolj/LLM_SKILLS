---
name: api-idempotency
description: Make unsafe API writes idempotent so retries, flaky connections, and offline-queue replays can't create duplicates. Use when the user reports "I saw the record/dish/order created twice", "duplicates on bad connection", asks for "an idempotent way to make API calls", mentions idempotency keys / client tokens / exactly-once, or when building ANY backend<->frontend app with a JSON API where the client retries writes (offline queue, retry-on-timeout, mobile networks). Covers the client-generated idempotency key pattern (Stripe-style), the mint-once-per-intent rule, DB unique constraints + race handling (Django IntegrityError savepoints, Go/Postgres ON CONFLICT), the retry-middleware key-minting trap (interceptors re-run per attempt), transient-vs-permanent retry classification, and how to audit an existing codebase for the "infra exists but a path skips it" gap.
---

# API idempotency: duplicate-safe writes

## The problem, named

HTTP gives you **at-least-once delivery** the moment a client retries: a
timeout or dropped response is *ambiguous* — the server may or may not have
processed the request. Retrying a non-idempotent POST after an ambiguous
failure is the classic **duplicate request problem**. It shows up as "the row
was created twice" and correlates with bad connectivity, redeploy windows
(5xx), and offline-queue replays.

GET/PUT/DELETE are idempotent by HTTP semantics; **POST (create) is not** and
needs explicit protection. You cannot fix this client-side alone ("don't
retry" just loses data instead) — the server must be able to recognize a
repeat.

## The solution, named

An **idempotency key** (also "client token", "request token"): a
client-generated unique value sent with each *logical* write. The server
remembers it and answers a repeat with the original outcome instead of
executing again. This is what Stripe and Adyen do (`Idempotency-Key` header;
there's an IETF draft standardizing it).

Two implementation shapes — pick one:

| Shape | How | When |
|-------|-----|------|
| **Resource-scoped token column** (lighter, usually enough) | Store the key as a column on the created row + unique constraint scoped to the parent (e.g. `(meal_id, client_token)`); on repeat, return the parent/resource as a normal success | Single-resource creates from your own frontend. No TTL/store needed — the key lives on the row |
| **Generic `Idempotency-Key` store** (Stripe-style) | Middleware table keyed by `(user, key)` storing status + response body; repeat replays the stored response; entries expire after ~24h | Many endpoints, third-party API consumers, action POSTs with side effects beyond one insert (emails, invoices, payments), or when the exact original response (incl. errors) must be replayed |

The store shape has two extra states the column shape gets for free: a repeat
arriving **while the original is still executing** (answer `409` — the claim
row exists but has no stored response yet; Stripe errors here too), and the
same key arriving **with a different payload** (store a hash of the body at
claim time; on mismatch answer `422`, per the IETF draft
`draft-ietf-httpapi-idempotency-key-header`). Both must be handled or the
store silently degrades into the read-then-insert race.

Key generation: **UUIDv4 is enough** (`crypto.randomUUID()` in browsers/
WebViews, secure contexts only — keep a time+counter fallback). Don't bother
appending timestamps for "extra collision protection": 122 bits of entropy is
already overkill, and the constraint is usually scoped per-user/per-parent
anyway. Avoid *predictable* keys (sequential, timestamp-only). Cap length
server-side (e.g. 64 chars) and trim.

## The four rules (each one was a real bug)

1. **Mint ONCE per user intent, not per request attempt.** The key must be
   created when the user acts (photo captured, order submitted), *before* the
   first network attempt, and live outside the request function. The sneaky
   version of this bug: minting the key inside HTTP-pipeline machinery that
   **re-runs on every retry attempt** — an Angular/axios interceptor, a fetch
   wrapper, a request-builder hook. RxJS `retryWhen`/`retry` resubscription
   re-executes the whole interceptor chain, and axios-retry re-runs request
   interceptors, so an interceptor-minted key is fresh per attempt and dedups
   nothing while looking implemented. Mint above the retry layer, pass the key
   down (found as a real bug in an Angular app whose base service retried
   POSTs up to 7×: the retries were exactly the duplicates).
2. **Every path that can re-send must carry the SAME key.** Online attempt,
   retry-on-timeout, offline-queue replay, manual "try again" button — all of
   them. The classic gap (found in a real audit): the offline queue sent a
   token, but the online happy path sent none, and when the online attempt's
   *response* was lost the fallback enqueued with a **freshly minted** token —
   guaranteed duplicate. Idempotency infra that isn't wired into the happy
   path protects nothing.
3. **The server check must survive a concurrent race.** A read-then-insert
   (`if exists(token): return`) has a window: two same-key requests both pass
   the check, the second insert hits the unique constraint and 500s. Wrap the
   insert in a savepoint and catch the constraint violation, answering it
   exactly like the pre-check no-op. (Django + `ATOMIC_REQUESTS`: the catch
   MUST be outside an inner `transaction.atomic()` block, else the outer
   transaction is aborted and any later query raises.)
4. **Answer a duplicate with success, not an error.** Return the resource/
   parent with 200 — the client's goal ("dish exists on meal") is satisfied;
   409s force clients to special-case a situation that isn't a failure.

## Minimal implementation

Server (Django/DRF flavor; translate freely):

```python
# Model: client_token CharField(max_length=64, blank=True, default="") +
# UniqueConstraint(fields=["parent", "client_token"], condition=~Q(client_token=""))
# The partial condition is REQUIRED with empty-string defaults, or all
# token-less rows collide with each other. (NULLs are distinct by default,
# but empty strings are not.)

token = (request.data.get("client_token") or "").strip()[:64]
if token and parent.children.filter(client_token=token).exists():
    return Response(serialize(parent), status=200)          # fast-path no-op
try:
    with transaction.atomic():                              # savepoint
        Child.objects.create(parent=parent, client_token=token, ...)
except IntegrityError:
    if not token:
        raise                                               # some other constraint
    parent.refresh_from_db()
    return Response(serialize(parent), status=200)          # lost the race = same no-op
```

Server (Go/Postgres flavor — the constraint claim is a single atomic
statement, no savepoint dance needed):

```go
// Same partial unique index as the Django shape:
//   CREATE UNIQUE INDEX ON child (parent_id, client_token)
//   WHERE client_token <> '';
// ON CONFLICT with the matching predicate makes claim + insert one atomic op.
row := pool.QueryRow(ctx, `
    INSERT INTO child (id, parent_id, client_token, ...)
    VALUES ($1, $2, $3, ...)
    ON CONFLICT (parent_id, client_token) WHERE client_token <> ''
    DO NOTHING
    RETURNING id`, id, parentID, token)
if err := row.Scan(&createdID); errors.Is(err, pgx.ErrNoRows) {
    // duplicate: the key already claimed the row — fetch and return it as success
    return respondWithExisting(ctx, parentID, token) // 200, rule 4
}
// sqlc: emit the same statement with :one and check sql.ErrNoRows.
// SQLite equivalent: INSERT OR IGNORE + changes()==0 → fetch existing.
```

Client:

```ts
export function newClientToken(): string {
  try { return crypto.randomUUID(); }
  catch { return `tok_${Date.now()}_${++counter}`; }   // non-secure-context fallback
}

async function submit(intent: Intent) {
  const clientToken = newClientToken();                 // rule 1: once, up front
  try {
    await api.create(intent, clientToken);              // rule 2: online path sends it
  } catch (e) {
    if (isTransientError(e)) queueForRetry(intent, clientToken);  // rule 2: SAME token
    else surfaceError(e);
  }
}
```

Retry classification (only transient failures may re-send): network-level
failures (fetch `TypeError`, status 0), 5xx, 429, 408. Any other 4xx is
permanent — retrying can't fix it and queue-retrying it jams the queue.
Classify *non-network exceptions* (JSON parse, storage bugs) as permanent too,
or code bugs masquerade as "offline".

## Auditing an existing project

The dangerous state is *partial* adoption. Check:

```sh
# 1. Which write endpoints accept a key, and is it constrained?
grep -rn "client_token\|idempotency" --include="*.py" .
# expect: a unique constraint per parent, not just a field

# 2. Does EVERY caller of the create API send it? (the happy-path gap)
grep -rn "addDish\|createOrder\|client_token\|clientToken" src/ | grep -v test
# every call site of the mutating client fn must pass a token — a call
# without one is the bug

# 3. Do retry/queue paths reuse the original token or mint fresh?
# read the enqueue-on-failure code: the token must flow from the failed
# attempt into the queued item (queue item id == token is a clean trick:
# the drain then replays with it for free)

# 4. Race safety: is the server check read-then-insert without an
# IntegrityError catch? Two concurrent same-token posts → one 500.
```

Also check the client HTTP layer for hidden retries (axios-retry, service
worker background sync, React Query mutation retries) — any of them turns
"one tap" into "N requests" and each request needs the same key.

## Tests worth writing

- **Repeat token → no-op**: create with token, POST again with same token,
  assert 200 + count unchanged; different token → new row.
- **No token → old behavior**: two token-less posts create two rows (the
  partial constraint must not block them).
- **Concurrent race**: patch the exists() pre-check to return False (simulating
  the not-yet-committed sibling), POST a duplicate, assert 200 not 500.
- **Lost-response e2e**: intercept the create response (Playwright route
  abort *after* request reaches server), let the retry/queue fire, assert
  exactly one row server-side.

## Gotchas

- **Partial unique constraints exclude the empty sentinel** — with
  `default=""` you need `condition=~Q(client_token="")`; forgetting it makes
  the second token-less insert explode.
- **Savepoints under request-wide transactions**: catching IntegrityError
  inside an aborted outer transaction raises `TransactionManagementError` on
  the next query. Inner `atomic()` block, catch outside it.
- **The no-op response should be the current resource state**, which may
  include effects of *other* requests since the original — that's fine; don't
  try to replay a byte-identical body unless you're doing the Stripe-style
  store (payments need it; CRUD doesn't).
- **Add a fetch timeout** (AbortController) to the upload path if there is
  none: without one, a hung request neither succeeds nor enters the retry
  path, and the user retries manually — which is fine *only* once the key
  exists per intent (a manual re-capture is a new intent, new key; an
  automatic retry of the same intent must reuse the key).
- **Keys don't fix double-submits with a CHANGED payload.** A draft row whose
  fields commit separately (inline-edit tables: description saves → create in
  flight → user edits the price → second create with a different body) is the
  same user intent but a different payload — under one key it 422s, under two
  keys it duplicates. That's a client state-machine bug: serialize saves
  per-resource (buffer commits while the create is in flight, flush them as a
  PATCH once the real id arrives). Reproduced in the wild: needs only latency,
  not a failed request.
- **Meal/parent-level dedupe is separate**: "create parent" endpoints can
  often be made naturally idempotent by semantic identity (same type+date →
  return existing) without any token.
- Reference implementation of all of the above: NutriLens
  (`backend/nutrilens/meals/api/views.py` add_dish/add_dish_text,
  `frontend-capacitor/src/services/capture-queue.ts` `newClientToken`,
  `docs/API_IDEMPOTENCY.md` in frontend-capacitor).
- Reference for the lost-response e2e technique (Playwright `route.fetch()`
  then `route.abort()` — request reaches the server, response dies) and the
  changed-payload double-submit repro: BikeCRM
  `bikecrm-frontend/tests/e2e/dupe-retry-repro.spec.ts` (+ design decisions in
  `bikecrm-backend/PLANS/dupe_prevention/PLAN.md`).
