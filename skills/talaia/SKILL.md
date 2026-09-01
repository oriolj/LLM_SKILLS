---
name: talaia
description: Add or change synthetic smoke-test monitoring for any project in the estate using Talaia (the watchtower — scheduled black-box pytest suites against PRODUCTION, SQLite history, Pushover alerts, status UI at talaia.oriolj.com). Use when asked "is this project monitored?", "make sure all projects are monitored", "add smoke tests / uptime checks / synthetic monitoring for X", when a new project is deployed or a domain/hostname changes, when a Talaia alert fires and its suite needs triage, or when the user mentions Talaia, suite.yml, smoke suites, or a status page. Covers the two suite tiers (credential-free `surfaces` vs test-account flow suites), the coverage audit against hq's mother list, the safety rules for writing against production, schedule staggering, and the deploy path.
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
[`docs/projects.md`](https://github.com/oriolj/hq) either to its suite or to
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
`docs/projects.md` and `docs/domains.md`, then `grep -r` the repo for its own
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

## Scheduling

`talaia crontab` emits one supercronic line per enabled suite. Every suite gets
its own minute offset so nothing thunders:

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
cd ~/git/oriolj/talaia/backend && uv run talaia run <project>/<suite>   # full path: DB + alerts
uv run python -m pytest tests -q        # harness tests
```

Deploy is a `git push` — Coolify redeploys the compose stack (scheduler + UI) on
oriolj-nc-1. Suites with `env.required` entries need their vars on the Coolify
resource first, or every run records as `error`.

If `uv run pytest` fails with phantom `ModuleNotFoundError`s while `uv run
python` works, the venv predates a directory move: `rm -rf backend/.venv && uv
sync`.

## Where things live

| | |
|---|---|
| Repo | `~/git/oriolj/talaia` — `backend/` (monitor), `comercial-website/`, `public-docs/` |
| Coverage inventory | `docs/COVERAGE.md` |
| Ops record | `DEPLOY.md` |
| Status UI | tailnet + the domain in `DEPLOY.md`; basic auth (`TALAIA_UI_*`) |
| Shared fixtures | `backend/talaia/smoketest/` (`surfaces.py`, `bikecrm.py`, `enacast.py`) |
| Suites | `backend/projects/<project>/<suite>/` — leaf dirs only |
| Related skills | `healthchecks-io` (heartbeats), `fleet-observability` (logs/metrics — a different question from "does the product work"), `coolify-deploy` |

Talaia answers "does the product still work for a user?". Prometheus/Loki answer
"what is the process doing?". A project wants both; neither substitutes for the
other.
