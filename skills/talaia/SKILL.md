---
name: talaia
description: Add or change synthetic smoke-test monitoring for any project in the estate using Talaia (the watchtower — scheduled black-box pytest suites against PRODUCTION, SQLite history, Pushover alerts, tailnet status UI; talaia.oriolj.com is the marketing site). Use when asked "is this project monitored?", "make sure all projects are monitored", "add smoke tests / uptime checks / synthetic monitoring for X", when a new project is deployed or a domain/hostname changes, when a Talaia alert fires and its suite needs triage, or when the user mentions Talaia, suite.yml, smoke suites, or a status page. Covers the two suite tiers (credential-free `surfaces` vs test-account flow suites), the coverage audit against hq's mother list, the safety rules for writing against production, schedule staggering, and the deploy path.
---

# Talaia — synthetic monitoring for the whole estate

Talaia (Catalan: a coastal watchtower) runs scheduled black-box pytest suites
against **production** deployments, stores runs in SQLite, alerts by Pushover
and serves a status UI. Repo `~/git/oriolj/talaia`
([github.com/oriolj/talaia](https://github.com/oriolj/talaia)); it is a
monorepo — the monitor is in `backend/`, plus a Cloudflare Pages marketing site
and Starlight docs.

Read the repo's own `CLAUDE.md` and `DEPLOY.md` before changing the harness.
This skill is the estate-level view: how projects get onto the watchtower and
stay there.

## The governing rule

**Every deployed, publicly reachable project has a suite. No exceptions —
only documented decisions.**

`backend/../docs/COVERAGE.md` maps every project in hq
`~/Syncthing/Syncthing-mobile-docs/hq/docs/projects.md` (local, Syncthing; hq has no Git remote) either to its suite or to
the reason it deliberately has none. A project present in the mother list but
in neither column of COVERAGE.md is the failure this whole repo exists to
prevent, so the audit is cheap on purpose:

```bash
cd ~/git/oriolj/talaia/backend && uv run talaia list   # left column = coverage
```

Cross-read that against hq's mother list. When a project ships, is renamed or
retires, COVERAGE.md moves in the SAME commit.

## Two tiers of suite

| Tier | Path | Needs | What it proves |
|---|---|---|---|
| `surfaces` | `projects/<project>/surfaces/` | nothing | health/version endpoints, app shells, tenant pages, commercial sites, docs are **serving** |
| flow | `projects/<project>/<flow>/` | a production **test account** | a real user journey completes (log in, create, pay, delete) |

Start every project at `surfaces`. It needs no credentials, which is the whole
point: BikeCRM's three flow suites sat disabled for weeks waiting for sandbox
creds, and without a `surfaces` suite the product was simply unwatched in the
meantime. Add flow suites later, per project, once a safe account exists.

### Writing a `surfaces` suite

`projects/<project>/surfaces/conftest.py` — one line:

```python
from talaia.smoketest.surfaces import http  # noqa: F401
```

`projects/<project>/surfaces/test_surfaces.py`:

```python
import os

from talaia.smoketest.surfaces import Surface, check_surface, parametrize

API_BASE = os.environ.get("MYPROJECT_API_BASE", "https://api.myproject.com")
APP_URL = os.environ.get("MYPROJECT_APP_URL", "https://app.myproject.com")

SURFACES = (
    Surface("api_health", f"{API_BASE}/health/", json_contains=(("status", "ok"),)),
    Surface("app", f"{APP_URL}/", contains=("MyProduct",)),
)


@parametrize(SURFACES)
def test_surface(http, surface):
    check_surface(http, surface)
```

`suite.yml`: `env.required: []`, `enabled: true`, a schedule on a free minute.

Four things that are easy to get wrong:

- **Assert a product-specific marker, never just a 200.** A broken SPA build, a
  Traefik "no route" page, a Cloudflare error page and a parked domain all
  answer happily. `contains=("MyProduct",)` is what makes the check about *this*
  app.
- **Take the marker from the page shell** (`<title>`, the product name), never
  from marketing copy. A copywriter rewording a hero line must not page anyone
  at 3am — a monitor that cries wolf gets muted, and a muted monitor is worse
  than none.
- **Default the base URLs in the module** and keep `env.required: []`. Adding a
  project must not require editing the server's `.env`, or "monitored" silently
  means "monitored once someone SSHes in".
- **Use `@parametrize(SURFACES)` on the function, not a module-level
  `pytestmark`.** A module-wide parametrize errors on every hand-written extra
  test in the file ("uses no argument 'surface'").

`Surface` fields: `name`, `url`, `contains`, `status` (default `(200,)`),
`json_contains` (dotted key → expected value, e.g. `("checks.db", "ok")`),
`follow_redirects`, `headers`. The shared client already sends a current desktop
Chrome UA, because bot filters otherwise make the check measure the filter.

### Finding a project's real URLs

Do not guess hostnames — probe, and record what you find. Sources in order:
the project's own `DEPLOY.md` / `docs/09-deploy-and-ops.md`, then hq
`docs/projects.md` and `docs/domains.md`, then `rg` the repo for its own
domain, then the Coolify API. Hostname conventions are NOT uniform
(`budget-buddy.api.oriolj.com` is hyphenated while its landing
`budgetbuddy.oriolj.com` is not), and health paths are not either — `/health/`,
`/healthz`, `/api/health/`, `/api/v1/health/` and `/up/` are all in use across
the estate.

Probe before asserting:

```bash
curl -sL -m 12 -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36' \
  -w '\n[%{http_code}]\n' https://app.example.com/ | head -c 300
```

Two traps worth knowing: a **meta-refresh** landing stub (`<meta
http-equiv="refresh">`) is not an HTTP redirect, so `follow_redirects` cannot
follow it — point the surface at the page it lands on. And an app root that
**legitimately 404s** (a per-tenant product like EnaArchive) means the tenant
page, not the root, is the real check.

**A 404 on `/` is not proof a project cannot be monitored — read its
URLconf before writing it off** (EnaStats, 2026-09-08). It had sat in
`COVERAGE.md`'s "deliberately not monitored" table because
`/`, `/healthz` and `/api/` all 404'd, and hq carried a matching TODO about
its "missing public entrypoint". Nothing was missing: the app is API +
Django admin with **no web UI**, its health path is `/health/` *with* the
trailing slash, and `/api/<version>/` requires the segment, so only
`/api/v1/` can match. Probing conventional paths answers "does this project
use my conventions", not "is this project up". For an API-only app the
surfaces are the health view, the DRF API index (a 200 there proves URL
reversing, versioning and content negotiation, not just that gunicorn is
up), the auth gate asserted as a bare **401** (a 200 would be the data
leak, a 5xx the broken gate), the admin login page (the only rendered
template), each hostname the resource serves (a Traefik router or cert that
only breaks on the second domain is otherwise invisible) — and the root
404 itself: assert the **framework's own 404 body**, because Traefik's
"no route" page is also a 404 and reads `404 page not found`, so the check
then distinguishes "serving, and correctly has no root view" from "nothing
is behind the router any more". A known-broken endpoint stays **out** of the
suite: pinning a 500 as expected cements it — report it and add the check
once it is fixed.

## Safety rules (these tests hit PRODUCTION)

- **Test accounts only.** Never point a suite at a real customer account.
- **Prefix and clean up.** Anything a test creates is named `SMOKE-` and deleted
  by the same test.
- The safety gate lives in the shared fixture, not per suite
  (`talaia/smoketest/bikecrm.py`), so no future test can write without it.
- **VeriFactu stays disabled** on BikeCRM's test business — sealed AEAT records
  are irreversible legal data.
- Flows that leave undeletable data belong in low-frequency suites (BikeCRM's
  daily `invoicing`), never in a 10-minute one.
- Suites are black box: they never import the monitored project's code.
- **Browser journeys: read the component before a test clicks anything on
  prod** (BikeCRM, 2026-09-14). Merely *opening* `/pos/orders/create` saved an
  order, and a payment button paid the whole pending amount in one click, no
  dialog — which, with auto-invoicing, would have left an undeletable invoice
  every 30 min. Explore navigation-only first, then with writes whose cleanup
  runs in a `finally`; in the suite, capture every object the UI creates from
  its 201 response (allowlisted resources) and delete it through the API,
  asserted, with the janitor as the net. Check the backend's side-effect
  conditions in code (`bikecrm/general` pays only a sheet the API confirms is
  open; it never pays a sale).
- **Frontend build drift is checkable without a frontend change** when the
  bundle carries a build stamp: `bikecrm/bundles` reads `{commit, branch,
  release, builtAt}` out of the live `main-*.js` and compares brands, skipping a
  mismatch younger than a deploy.

## Reviewing BikeCRM results and test changes

Read the repo's `docs/COVERAGE.md` and `DEPLOY.md` for current coverage and pending
changes. Do not infer deployed coverage from the local working tree. Compare
`talaia_app_info{version}` with the deployed source and inspect the latest
individual test results, including skips, retries and timestamp freshness.
BikeCRM has six suites: `surfaces`, `backend`, `general`, `invoicing`, `beta`,
and `bundles`. The browser suite now has real journeys, not just a login form.

The 2026-09-15 browser/build hardening is implemented and manually verified but
was still pending deployment at that review; consult `DEPLOY.md` before claiming
it is scheduled. It adds these reusable checks:

- Verify the browser's actual API origin and its own authenticated sandbox
  business before allowing writes, and require the verified token on mutations.
  A separately authenticated httpx client does not verify the browser session.
  Read a response body outside Playwright response callbacks when also using
  `expect_response`: nested synchronous waits can re-enter its event handling.
- Clean up in per-journey fixture teardown, even after an assertion fails.
  Unreadable creation IDs and unsuccessful cleanup must fail explicitly; attempt
  all tracked deletions before reporting failures. Keep the janitor as fallback.
- Reload saved service-sheet/sale records and assert their visible prices and
  payment states. SkooterP's separate login check blocks business writes.
- Validate frontend commit and timestamp fields even when both brands match.
  Reject invalid/unknown commits, missing timezones and future timestamps;
  mismatched valid builds skip only within the 90-minute deployment grace.

`general` tags its run with the backend release. `bundles` has no `version_url`:
it reads frontend build stamps directly. Neither proves what bundle an existing
customer's cached browser is using.

A status-only request normally needs fresh scheduled results, not another
invoice-producing run. Use the daily invoice result when it is within cadence,
and report its timestamp/release. For an authorized one-off production run,
use `docker exec` in the existing UI container (SSH to
`root@100.97.219.99`, port `1922`; discover the current container name).
Never start a second scheduler with `docker compose run scheduler`. Local
`uv run` needs `--env-file .env`; it does not load dotenv automatically.

## Scheduling

`talaia crontab` emits one supercronic line per enabled scheduled suite. Allow
at most two suite starts per minute across the fleet, and stagger suites of
the same project. `backend/tests/test_schedule.py` enforces that contract:

```bash
cd ~/git/oriolj/talaia/backend && uv run talaia crontab
```

The `X-59/15` offsets (X in 0..14) are nearly exhausted, so a new `surfaces`
suite takes a twice-hourly `X,X+30` slot. Note `X-59/15` only works for X < 15;
a higher X silently fires once an hour.

Cadence guide: app + API surfaces every 15 min, static sites and docs every
30 min, write-flow suites at whatever their side effects tolerate.

## Heartbeats — who watches the watchtower

Talaia does **not** smoke-test its own status UI: a monitor reporting on itself
proves nothing, since if it is down nobody runs the check. Its liveness is a
healthchecks.io dead-man switch (`talaia-scheduler`, oriolj project), pinged via
`heartbeat_env: HC_URL_TALAIA_SCHEDULER` on the most frequent suite
(`panotxa/api`). If the scheduler dies, healthchecks.io alerts. See the
`healthchecks-io` skill for the account model and keys.

`version_url` on a suite makes the runner tag each run with the deployed
release, so an alert can be read against the deploy that caused it — wire it for
any app whose health endpoint reports a version.

## Verifying and deploying

```bash
cd ~/git/oriolj/talaia/backend
uv run talaia list                      # discovery
cd projects/<project>/<suite> && uv run --project ../../.. python -m pytest . -q
cd ~/git/oriolj/talaia/backend && uv run --env-file .env talaia run <project>/<suite>   # DB + alerts
uv run python -m pytest tests -q        # harness tests
```

Deploy is a `git push` — Coolify redeploys the compose stack (scheduler + UI) on
oriolj-nc-1. Suites with `env.required` entries need their vars on the Coolify
resource first, or every run records as `error`.

If `uv run pytest` fails with phantom `ModuleNotFoundError`s while `uv run
python` works, the venv predates a directory move: `rm -rf backend/.venv && uv
sync`.

## When an alert fires — triage path (accountant outage, 2026-09-06)

1. **Scope it in one call**: `curl -s http://oriolj-nc-1:8611/metrics | grep
   'talaia_suite_up.* 0'` — which suites are red, and `talaia_suite_over_budget`
   while you are there.
2. **Read the suite page** `http://oriolj-nc-1:8611/suite/<id>`: the failing
   test's assertion carries URL + status + body, and the run history's first
   red row is the outage START. Write that timestamp down — deploy docs written
   from memory get it wrong (the accountant doc first said 12 min for an
   8 h 21 min outage; the Coolify deployment rows, not recollection, fix that).
3. **Probe live** with curl (browser UA). Traefik's `503 no available server`
   means no healthy container behind the router — a deploy or a healthcheck,
   not the app's code paths.
4. **Find the host** in the project's `DEPLOY.md`. No SSH path (jluv-apps-1
   is on the personal tailnet, unreachable from here)? Use the Coolify API of
   the project's SCOPE (`coolify-deploy` skill §7b): `GET /applications/{uuid}`
   (`exited:unhealthy` = nothing serving), `GET /deployments/applications/{uuid}`
   (a `failed` row at the outage start), `GET /deployments/{uuid}` (the log; a
   `Container logs:` block with the traceback appears only when the health
   gate ran out with the container still present — otherwise re-trigger with
   `POST /deploy?uuid=…` and read the new one). Token: hq
   `homelab/secrets/coolify-<scope>.env` — parse it, never `source` it (the
   `|` in the value), and send a browser UA (Cloudflare 1010).
5. **Reproduce at the deployed commit** in a detached `git worktree` under the
   scratchpad (the main checkout may belong to another live session — check
   `git status` and `origin/master` before committing or pushing there),
   against a throwaway `postgres:16-alpine` WITH data in the affected tables
   (best: the project's prod dump from R2). A from-scratch migrate that passes
   proves nothing about a DB with rows.
6. **After the fix**: watch `talaia_suite_up` flip, remove the `USER_TODO.md`
   item, and correct the project's deploy-history rows from the Coolify data.

Alert priority is suite-wide: `0` normal, `1` high, `2` emergency. Emergency
suites confirm once after 60 seconds, replacing ordinary retries; a recovered
confirmation sends a normal short-outage warning. Configuration errors stay
low priority. Cooldowns, recovery cancellation and failed-delivery retries are
implemented. Read the repo's `docs/ALERTING.md` before changing alert behavior;
failed-run counters are not counts of delivered notifications.

## Where things live

| | |
|---|---|
| Repo | `~/git/oriolj/talaia` — `backend/` (monitor), `comercial-website/`, `public-docs/` |
| Coverage inventory | `docs/COVERAGE.md` |
| Ops record | `DEPLOY.md` |
| Status UI | `http://100.97.219.99:8611` (tailnet); optional basic auth, currently off; verify `DEPLOY.md` |
| Shared fixtures | `backend/talaia/smoketest/` (`surfaces.py`, `bikecrm.py`, `bikecrm_browser.py`, `enacast.py`) |
| Suites | `backend/projects/<project>/<suite>/` — leaf dirs only |
| Related skills | `healthchecks-io` (heartbeats), `fleet-observability` (logs/metrics — a different question from "does the product work"), `coolify-deploy` |

Talaia answers "does the product still work for a user?". Prometheus/Loki answer
"what is the process doing?". A project wants both; neither substitutes for the
other.
