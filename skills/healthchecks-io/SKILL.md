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

Checks in the oriolj project (2026-09-02, 7): `panotxa-orphan-resume`
(hourly Celery sweep ping), `talaia-scheduler` (pinged by talaia's most
frequent suite via `heartbeat_env`), and H2A-LeadHunter's five
`h2a-leadhunter-{beat,orphan-research,orphan-scoring,budget-check,contact-cadence}`
(beat 5 min/grace 15 min; hourly sweeps 1 h/30 min; daily 1 d/6 h).
Five sequential creates 4 s apart all answered 201 that day, so the 403
burst below is not deterministic — still create one at a time. Body
fields that work: `name`, `slug`, `tags` (space-separated string),
`desc`, `timeout`, `grace`, `channels: "*"`, `unique: ["slug"]`
(re-running the create updates instead of duplicating).

`hcw_` prefix = a project API key (read/write on that project's checks).
Never mix projects: a check created with the wrong key lands in the wrong
realm's dashboard.

🔴 **`POST /checks/` can answer a bare `403` — and it is NOT reliably
"account limit reached"** (the docs say it is): on 2026-08-31 a BURST of
creates 403'd from the second call onward with only 13 checks account-wide,
and single creates succeeded minutes later at a higher count. Treat a 403
as "back off and retry a single create later" before concluding the
account is full. Independently of that: budget checks anyway — one
**dead-man switch per app** (its most frequent scheduled task pinging on
success) beats one-check-per-job; per-job depth belongs in Grafana
(task_last_run alerts).

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
- **Per-check env variant (H2A-LeadHunter, 2026-09-02)**: one env var
  per check, `HEALTHCHECKS_PING_URL_<CHECK>`, read by
  `backend/leadhunterbackend/common/healthchecks.py`: a static
  `TASK_CHECKS` task-path→check map + a `task_postrun` SUCCESS-only
  receiver (`dispatch_uid`, connected from `config/celery_app.py`) and a
  5-min beat task `healthchecks_beat_heartbeat_task` (its own data
  migration) for the dead-man switch. Unset/empty env = no-op, so tests
  and dev never ping; tests mock `httpx.get`. Adding a check needs a code
  change to the map (vs Panotxa's JSON env) — the trade is grep-able
  names in code. The worker pings, so on a split web/worker/beat deploy
  the env vars go on the **worker** app.
- **Reference implementation (Panotxa, 2026-08-31)**: env-driven mapping
  `HEALTHCHECKS_PINGS` (JSON task-path → ping URL, Coolify env on the
  worker) read by a `task_postrun` success-only hook
  (`backend/config/celery_app.py::_task_healthchecks_ping`, httpx 5 s,
  best-effort). Adding a check later = create it via API + extend the env,
  no deploy.
