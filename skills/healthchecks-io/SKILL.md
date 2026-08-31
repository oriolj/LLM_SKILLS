---
name: healthchecks-io
description: Use healthchecks.io for beat/cron heartbeat monitoring across the estate — the shared-account model (one account, per-project API keys), where the keys live, the v3 API basics, and how jobs get wired. Use when adding a heartbeat to a Celery beat schedule, supercronic job or any scheduled task, filling a deploy doc's "Jobs monitored by healthchecks.io" row, or when the user mentions healthchecks.io, ping URLs, or cron monitoring.
---

# healthchecks.io — heartbeats for scheduled jobs

## Account model (Oriol, 2026-08-31)

**ONE shared healthchecks.io account for all three realms** (exception to
"accounts follow the scope"), partitioned by **project**, and **API keys
are per-project**. Keys live in `hq/homelab/secrets/healthchecks.env` as
`HEALTHCHECKS_API_KEY_<PROJECT>`:

| Project | Key | State (2026-08-31) |
|---|---|---|
| `ORIOLJ` | delivered | API-verified, 0 checks (fresh) |
| `ENANTENA` | delivered | API-verified, 12 checks |
| bikecrm | ⏳ | Oriol's paste duplicated the enantena key — not stored |
| smartupsoft | ⏳ | unknown whether the project exists |

`hcw_` prefix = a project API key (read/write on that project's checks).
Never mix projects: a check created with the wrong key lands in the wrong
realm's dashboard.

## API (v3, verified)

- `X-Api-Key: <key>` header; base `https://healthchecks.io/api/v3/`.
- `GET  /api/v3/checks/` — list (also the cheap key validation).
- `POST /api/v3/checks/` — create; body e.g. `{"name": "...", "slug":
  "...", "timeout": 3600, "grace": 900, "channels": "*"}` (or `schedule`
  + `tz` for cron-shaped checks). Response carries `ping_url`.
- The PING url (`https://hc-ping.com/<uuid>`) is what jobs call — it is
  NOT secret-equivalent to the API key, but treat it as config, not code.

## Wiring pattern (the house shape)

- **Celery beat**: end each scheduled task with a best-effort
  `httpx.get(ping_url, timeout=5)` (never fail the task on ping failure),
  or ping from a `task_postrun` hook filtered to beat-scheduled tasks.
  Ping URLs are env/config (`HEALTHCHECKS_PING_URL_<JOB>`), never
  hardcoded.
- **supercronic**: append `&& curl -fsS -m 5 https://hc-ping.com/<uuid>`
  to the crontab line (start/fail variants: `/start` and `/fail`
  suffixes).
- Every deployed repo's status table has a "Jobs monitored by
  healthchecks.io" row (hq `shared/docs/deploying-a-new-project.md`) —
  wiring a project's heartbeats closes it.
