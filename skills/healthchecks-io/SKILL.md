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

Checks in the oriolj project (2026-09-02, 11): `llmwatch-beat` (5 min/grace 15 min, fed by a no-op `beat_heartbeat` Celery task on a 5-min beat schedule — the beat→worker dead-man switch) + `llmwatch-dispatch-daily-batches` (1 h/30 min), `licita-radar-pipeline` (10-min supercronic pipeline, timeout 600 s / grace 900 s) + `licita-radar-daily-digest` (cron `0 7 * * *` UTC, grace 1 h) — both pinged by the repo's `backend/run-job.sh` wrapper (the supercronic variant below), `panotxa-orphan-resume`
(hourly Celery sweep ping), `talaia-scheduler` (pinged by talaia's most
frequent suite via `heartbeat_env`), and H2A-LeadHunter's five
`h2a-leadhunter-{beat,orphan-research,orphan-scoring,budget-check,contact-cadence}`
(beat 5 min/grace 15 min; hourly sweeps 1 h/30 min; daily 1 d/6 h).
**H2A-Accountant's four** (2026-09-04): `h2a-accountant-beat` (5 min/15 min,
fed by a no-op `config.celery.beat_heartbeat_task` on a 300 s beat entry),
`h2a-accountant-collect-daily` (cron `0 6 * * *` UTC, grace 2 h),
`h2a-accountant-check-missing-weekly` (cron `0 8 * * 1` UTC, grace 6 h),
`h2a-accountant-orphan-sweep` (1 h/30 min) — LeadHunter's per-check env
shape (`HEALTHCHECKS_PING_URL_<CHECK>` on the worker AND beat apps,
`backend/config/healthchecks.py` with `task_prerun` → `/start`, SUCCESS →
ping, FAILURE → `/fail`). Total in the oriolj project: 15.

🔴 **The oriolj project has ZERO notification channels (found 2026-09-04
via `GET /api/v3/channels/`)** — every check there (LeadHunter's six, the
accountant's four, llmwatch, licita-radar, panotxa, talaia) can go `down`
and nobody is told; `channels: "*"` on create binds nothing when the list
is empty. Adding an email/Pushover integration is a UI click (Oriol) —
until it exists, treat healthchecks.io in that project as display-only
and say so in the project's status row. Check `GET /api/v3/channels/`
before claiming a project's jobs are "monitored".
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
- **supercronic**: do NOT append `&& curl …` to the crontab line — a
  failing ping would fail the job (and a `|| curl …/fail` would mask a
  real failure as success in supercronic's metrics). Wrap the job
  instead (Licita Radar `backend/run-job.sh`, 2026-09-02): `run-job.sh
  <CHECK> "<cmd>"` reads `HEALTHCHECKS_PING_URL_<CHECK>`, pings `/start`,
  runs `sh -c "<cmd>"`, pings the bare URL on success or `/fail` on
  failure — every ping best-effort (`curl -fsS -m 10 --retry 2 … || true`)
  — and exits with the COMMAND's status, so `supercronic_executions −
  supercronic_successful_executions` (and the Grafana failure alert)
  keep meaning what they mean. Unset URL = no ping (dev/tests). The
  crontab needs `sh -c` semantics (supercronic runs commands through
  `$SHELL -c`, default `/bin/sh`) — quote the whole command as one arg.
- Every deployed repo's status table has a "Jobs monitored by
  healthchecks.io" row (hq `shared/docs/deploying-a-new-project.md`) —
  wiring a project's heartbeats closes it.
- **Per-check env variant (H2A-LeadHunter, 2026-09-02)**: one env var
  per check, `HEALTHCHECKS_PING_URL_<CHECK>`, read by
  `backend/leadhunterbackend/common/healthchecks.py`: a static
  `TASK_CHECKS` task-path→check map + a `task_postrun` SUCCESS-only
  receiver (`dispatch_uid`, connected from `config/celery_app.py`). The
  `BEAT` dead-man switch is an EXISTING 5-min beat task mapped in the same
  dict (`worker_heartbeat_task`) — never add a second heartbeat task when
  one already ticks: two PeriodicTask rows for one fact (2026-09-02
  simplify pass removed exactly that). A `NO_CHECK` frozenset lists the
  scheduled tasks deliberately without a check, and a `django_db` test
  asserts every enabled `PeriodicTask` is in one of the two sets, so a new
  `*_beat_schedule` migration cannot ship unmonitored. Unset/empty env =
  no-op, so tests and dev never ping; tests mock `httpx.get`. Adding a
  check needs a code change to the map (vs Panotxa's JSON env) — the
  trade is grep-able names in code. The worker pings, so on a split web/worker/beat deploy
  the env vars go on the **worker** app.
- **LLM Index Watcher (2026-09-02)** copies Panotxa's JSON-env shape
  (`HEALTHCHECKS_PINGS` on `llmwatch-worker`, hook `_task_healthchecks_ping`
  in `config/celery.py`) and adds the dead-man task itself:
  `apps.runs.tasks.beat_heartbeat`, a no-op `@shared_task` in
  `CELERY_BEAT_SCHEDULE` every 300 s. First ping ~4 min after the beat
  container came up. Tests mock `httpx.get` (`apps/runs/tests/test_ops_hooks.py`).
- **Reference implementation (Panotxa, 2026-08-31)**: env-driven mapping
  `HEALTHCHECKS_PINGS` (JSON task-path → ping URL, Coolify env on the
  worker) read by a `task_postrun` success-only hook
  (`backend/config/celery_app.py::_task_healthchecks_ping`, httpx 5 s,
  best-effort). Adding a check later = create it via API + extend the env,
  no deploy.
