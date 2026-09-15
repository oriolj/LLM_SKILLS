---
name: gatus
description: Operate Gatus, the estate's config-as-code uptime monitor and public status page (status.enacast.com, hq-monitoring/gatus, Coolify Dockerfile app on internal-1). Use when registering a new project's public surfaces for uptime monitoring, adding/changing an endpoint or its conditions, changing alert tiers (Pushover/email), debugging "why did/didn't Gatus alert", reading the status page's API/metrics, or when the user mentions Gatus, the status page, uptime checks, or `make gatus-*`. Carries the config-directory merge rules, the condition conventions, the Pushover priority-2 trap, the Alpine-not-scratch image reason, and the deploy loop.
---

# Gatus — the estate's uptime monitor and status page

**Live**: [status.enacast.com](https://status.enacast.com) (public, read-only).
**Code**: `~/git/oriolj/hq-monitoring/gatus/` — Dockerfile + `config/`.
**Runs**: Coolify Dockerfile app `dqtz0sqiqiq7bpwt944xpbp5` (Enantena team,
project *Internal services*, server **internal-1**), blue-green, health
check `/health`, named volume `gatus-data` → `/data`. Design + ops record:
hq `shared/docs/gatus.md`. Chosen over Uptime Kuma on 2026-09-13
(everything in git, no clicky SQLite state, no login surface on the
internet, reviewable diffs); the SmartupSoft Uptime Kuma was deleted the
same day (it had zero users and zero monitors after 8 months).

## 1. The model — one YAML per project, merged at startup

`GATUS_CONFIG_PATH=/config` is a **directory**: every `*.yaml` under it
(subdirectories included) is deep-merged by `TwiN/deepmerge`:

- maps merge, lists **append** (`endpoints:` from every file add up);
- a key with a **primitive value may be defined only ONCE across all
  files** — a second definition is a startup error. So `web`, `ui`,
  `storage`, `metrics`, `concurrency`, `alerting` live in
  `config/_global.yaml` and nowhere else;
- YAML anchors resolve **per file** (before the merge), so a per-project
  defaults block must have a **unique top-level key per file**:
  `x-<project>: &<project>` — two files both declaring `x-defaults` with
  the same primitive keys would collide. Unknown top-level keys are ignored
  by Gatus, which is what makes the `x-` trick work.

Layout: `config/<scope>/<project>.yaml` (`personal/`, `enantena/`,
`smartupsoft/`, `shared/`) — the **scope is the one in hq
`docs/projects.md`**, the file name is the project slug. The template every
file follows:

```yaml
# <Project> — what it is. Surfaces mirror the Talaia suite <path>.
x-<slug>: &<slug>
  group: <slug>            # dashboard group = project
  interval: 60s            # APIs 60s; static sites override with 5m
  client: {timeout: 15s}
  alerts:
    - type: pushover       # both providers on every endpoint (tiers below)
    - type: email
  extra-labels: {scope: <scope>, project: <slug>}   # → Prometheus labels

endpoints:
  - name: api-health
    <<: *<slug>
    url: "https://api.example.com/health/"
    conditions:
      - "[STATUS] == 200"
      - "[BODY].status == ok"
      - "[CERTIFICATE_EXPIRATION] > 168h"
  - name: site
    <<: *<slug>
    url: "https://example.com/"
    interval: 5m
    conditions:
      - "[STATUS] == 200"
      - "[BODY] == pat(*Example*)"      # product marker — a parked domain also answers 200
      - "[CERTIFICATE_EXPIRATION] > 168h"
```

Endpoint keys (`<group>_<name>`) must be unique estate-wide
(`ValidateUniqueKeys`); names within a group therefore unique.

## 2. Conventions (what the 96 endpoints of 2026-09-13 follow)

- **Source of truth for "which surfaces exist" is the project's Talaia
  suite** (`~/git/oriolj/talaia/backend/projects/<p>/surfaces/`): same
  URLs, same markers, same JSON assertions. Gatus is the cheap 60-second
  black-box probe + public page; Talaia is the deeper synthetic test. Keep
  them in step: a new surface goes to both.
- One endpoint per public surface: API health (with the JSON fields the
  view reports — `[BODY].checks.db == ok`), app, comercial site, docs,
  tenant/customer pages that prove multi-tenant routing (`app/demo/`,
  `santjust.chat`, `girona.enaarchive…`).
- `[CERTIFICATE_EXPIRATION] > 168h` on every https endpoint (7 days
  before expiry is when the row goes red — auto-renewal has had weeks).
- No `[RESPONSE_TIME]` conditions in v1: they flap on slow static hosts.
  Duration is a metric; alert on p95 in Grafana if ever needed.
- Deliberate non-200s are asserted as such (`enastats` root is
  `[STATUS] == 404` + Django's own body — Traefik's "no route" 404 reads
  differently and would fail).
- Hyphenated JSON keys: `[BODY].real-time-stats` does not parse; use
  `[BODY] == pat(*real-time-stats*)`.
- `Accept: application/json` header where the view content-negotiates
  (DRF browsable API).
- Tailnet-only surfaces (Grafana, Prometheus, GlitchTip) are probed by
  **literal `100.x` address** from the container: MagicDNS does not
  resolve inside a container (verified 2026-09-13 on internal-1). That is
  one of the two sanctioned exceptions to the MagicDNS-names rule.
- Register the surface even if it is red today (evpricemap.com answered
  503 on day one) — a status page that only lists green things is
  decoration. Report the red one loudly instead.

## 3. Alert tiers (mirror of hq `shared/docs/alerting.md`)

Both providers are configured once in `_global.yaml` with a
`default-alert` (description, `failure-threshold: 3`, `success-threshold:
2`, `send-on-resolved: true`, `minimum-reminder-interval: 4h`), so an
endpoint just lists `- type: pushover` / `- type: email`:

| Tier | How | Gatus |
|---|---|---|
| default (= alerting.md `important`) | Pushover priority 0 + email | what every endpoint gets |
| critical | Pushover **priority 1** (high, bypasses quiet hours) + email | per-endpoint `provider-override` — see below |
| emergency (priority 2, siren + retry until acked) | **NOT available in Gatus** | Gatus sends no `retry`/`expire` with the message and Pushover rejects priority 2 without them (`alerting/provider/pushover/pushover.go`, v5.36.0 — verified). Emergency stays with Grafana's `critical` route. |

```yaml
alerts:
  - type: pushover
    provider-override: {priority: 1}
    description: "customers cannot log in"
  - type: email
```

Failure threshold 3 = 3 min on a 60 s endpoint, 15 min on a 5 m site.
`resolved-priority: -1` (quiet recovery push). Email goes out on every
tier — the written record — through Resend SMTP `smtp.resend.com:587`
(Hetzner allows 587; a netcup host would need 2587). Sender
`SMTP_FROM=internal-1@oriolj.com`, recipient `ALERT_EMAIL_TO=oriol@enacast.com`
(Enantena sysadmin: the resource lives in the Enantena team).

Grafana is the cross-watch (`hq-monitoring/grafana/provisioning/alerting/gatus.yml`):
`gatus-scrape-absent` (important) when the `gatus` job vanishes from
Prometheus, `gatus-endpoint-red-30m` (email) when a surface has failed
every probe for 30 min — the case where Pushover/Resend themselves broke.
And Gatus watches the hub back (`config/shared/hq-monitoring.yaml`).

## 4. The deploy loop

```
cd ~/git/oriolj/hq-monitoring/gatus
make validate   # docker build + REAL startup, placeholder secrets, --network none → /health + "Validated N endpoints"
make deploy     # validate → commit+push gatus/ → wait for the webhook deploy of that commit → prove → make status
make status     # per-group up/down + failing endpoints (?pageSize=1: newest result only)
make logs       # last Coolify deployment log
make restart    # restart the container
```
(also `make gatus-<target>` from the repo root). Coolify API access goes
through hq `homelab/tools/coolify-lib.sh`, `coolify-deploy.sh` and
`coolify-restart.sh` — never a hand-rolled curl with its own token grep.

- Gatus has **no `--check` flag**: the only validator is a real start. An
  invalid config exits before `/health` answers; `make validate` fails on
  that with the log. Placeholder credentials make Gatus *ignore* the
  provider (`Ignoring provider=pushover due to error=application-token
  must be 30 characters long`), so a validation run can never page.
- **Push OR trigger, never both.** A push touching `gatus/**` deploys
  through the GitHub App webhook (`watch_paths: gatus/**`, ~70 s from push
  to finished). The first `make deploy` also POSTed `/deploy`, which
  rolled the container out twice per change (seen 2026-09-15: an API and
  a webhook deployment of the same commit one second apart). `make
  deploy` now waits for the deployment row whose `commit` is the pushed
  SHA, and triggers by API only when nothing under `gatus/` was pushed.
- **`prove` after every deploy** checks three things: `/health`; both
  providers in the live container log (`configuredProviders=[email
  pushover]` from `GET /applications/<uuid>/logs` — Gatus silently
  ignores a provider with an empty credential, so a wiped env var would
  mute all paging while `/health` stays green); and live endpoint count ≤
  validated count, restarting the container when the old blue-green
  container wrote a removed endpoint back.
- **Every endpoint change is a container restart.** Result history lives
  in SQLite on the `/data` volume (`storage.type: sqlite`) precisely so
  history survives those restarts; it is a cache, not a source of truth —
  no backup, no register note.
- Secrets are runtime-only Coolify env vars on the resource
  (`PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY`, `RESEND_API_KEY`,
  `SMTP_FROM`, `ALERT_EMAIL_TO`), expanded from `${VAR}` in the YAML at
  startup. Never a value in the repo. A `$` in a condition must be `$$`.

## 5. Verifying (what "it works" looks like)

- `curl https://status.enacast.com/health` → `{"status":"UP"}`.
- `curl https://status.enacast.com/api/v1/endpoints/statuses` → one object
  per endpoint with `results[]` (`make status` summarises it).
- `/metrics`: `gatus_results_endpoint_success{group,name,project,scope}`
  0/1, `gatus_results_total{success}`, `gatus_results_duration_seconds`,
  `gatus_results_certificate_expiration_seconds` — scraped by the hub as
  job `gatus` with `honor_labels: true` (so the endpoint's own
  project/scope win over the target's), dashboard **Gatus uptime** (uid
  `gatus`, org `hq`).
- Alert proof (done 2026-09-13 with a temporary `_canary.yaml` — an
  unresolvable host with `failure-threshold: 1`): the container log shows
  `Sending initial pushover alert … TRIGGERED` and the same for email with
  no "Failed" line, and the push arrives. Delete the canary right after,
  it reminds every 4 h.

## 6. Traps met on day one

- **Upstream image is `FROM scratch`** (no shell, no wget): Coolify's UI
  health check has nothing to exec and would roll every deploy back. The
  estate image copies the upstream binary onto `alpine`, nonroot uid
  65532, `/data` pre-created and chowned so the empty named volume
  inherits it. **Coolify's UI check is the one that gates the swap**
  (the deploy log shows "Attempt 1 of 10"), so the image has no
  HEALTHCHECK of its own; its start period is 3 s on the resource (Gatus
  answers `/health` in ~1 s — the old 15 s was slept in full per rollout).
- **`alerting.pushover.title` is a fixed string** — `[ENDPOINT_NAME]`
  placeholders are NOT expanded there (only in bodies/custom providers).
  Leave it unset: the default is `Gatus: <group>/<name>`.
- **`/api/v1/endpoints/statuses` lists only endpoints that have a result
  yet** for the first seconds after start; count endpoints from the log
  line `Validated N endpoints`, not from the API, in validation.
- **Validate with `--network none`.** Parsing happens before any probe,
  so an offline start proves the config; with a network it sent ~100 GETs
  to production from the workstation per run. Health is checked with
  `docker exec … wget`, and the container is removed with `docker rm -fv`
  (the image declares `VOLUME /data`; without `-v` every run leaked one).
- **The Coolify `custom_labels` field must be base64** — sending `""`
  fails the whole PATCH ("should be base64 encoded"); omit the field.
- **A removed endpoint can linger on the page after a blue-green deploy.**
  Both containers share the SQLite volume; the new one deletes stale keys
  at startup (`Total endpoint keys to preserve: N`), but the OLD container
  keeps probing for a few seconds and writes the removed endpoint back
  (seen with `_canary`: 97 on the page after a 96-endpoint deploy). It
  vanishes at the next restart — `POST /applications/<uuid>/restart` (a
  ~20 s blip) or the next deploy. `make status` shows it as a group with
  `0/1`.
- **No per-endpoint links** (verified upstream 2026-09-15): rows are not
  clickable, the endpoint `ui` struct only has hide flags + badge
  thresholds; the only links are `ui.link` (logo) and `ui.buttons`
  (global header row). Upstream TwiN/gatus#106 open since 2021, #1219
  closed as its duplicate; maintainer plans `endpoints[].ui.links` "in
  the next year or so" (2026-08-18). Use `ui.buttons` for the consoles
  (Grafana, Beszel, GlitchTip, Talaia — set 2026-09-15) and a homepage
  for a linked per-surface list. Do not build around a per-endpoint link.
- Kuma → Gatus migration was a no-op: **check the old tool's DB before
  planning a migration** (`sqlite3 kuma.db "select count(*) from
  monitor"`) — the 8-month-old instance had never been set up.
