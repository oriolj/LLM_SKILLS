---
name: django-house-setup
description: Assemble or retrofit a Django project to the house standard — the one index over every Django rule and skill, plus the mechanics that have no other home. Use when creating a new Django project, reviewing whether an existing one is "house standard", wiring logging/access logs (gunicorn + Loki), adding /health endpoints or the ROLE one-image pattern, or when the user asks "how do we usually set up Django", "add the logger", "wire prometheus the usual way", "is this project set up like the others". Covers the settings layout, the LOGGING contract (disable_existing_loggers=False — True silently swallows gunicorn's access logs), gunicorn flags (access logs to stdout for Loki), health endpoints per role, and POINTERS to the owning skills for metrics, Celery safety, idempotency, auth resilience — never duplicating them.
---

# Django, the house way — assembly index

One page to make a Django project look like every other Django project of
the estate. **This skill owns only what has no other home**; everything
else is a pointer — follow it, don't copy it here (single source, no
drift).

## The index — where each concern is owned

| Concern | Owner |
|---|---|
| uuid4 PKs (users included), uv for deps, pytest, latest LTS Django | global `CLAUDE.md` |
| Celery prod sizing (concurrency 2, max-requests, no Flower, cheap healthchecks) | global `CLAUDE.md` §right-sizing |
| Celery deploy safety (acks_late, AOF, orphan sweeps, dedupe) | `celery-deploy-safety` skill |
| DRF pagination/list-page footguns | global `CLAUDE.md` §DRF + Next.js |
| `/metrics`, prom.py collectors, multiproc, scrape lanes, dashboards/orgs | `fleet-observability` skill §5, §5c |
| Idempotent write endpoints (client tokens) | `api-idempotency` skill |
| JWT/session login resilience | `auth-session-resilience` skill |
| Tenancy isolation | `multitenancy-guardrails` skill |
| LLM calls (PydanticAI + Langfuse) | `pydantic-ai-langfuse` skill |
| Email: Resend via django-anymail, Mailpit locally, send from Celery | global `CLAUDE.md` |
| Coolify resources, blue-green, env vars, server moves | `coolify-deploy` skill |
| Release identifier (git SHA in app/Sentry/`app_info` metric) | global `CLAUDE.md` §Releases |
| Deploy doc + status table per repo | hq `shared/docs/deploying-a-new-project.md` |

Reference implementations, newest first: `JLUV-smallbets/NutriLens`
(`backend/`), `oriolj/llm-index-watcher`, `oriolj/public_contract_scanner`
— copy the shape from the one whose layout matches.

## Settings layout

`config/settings/{base,local,production,test}.py` + `django-environ`;
local env files under `.envs/.local/`, prod values ONLY in Coolify
(runtime-only). `config/` also holds `celery_app.py`, `prom.py`,
`healthserver.py`, `urls.py`, `api_router.py`.

## LOGGING — the contract (owned here)

- 🔴 **`"disable_existing_loggers": False` in EVERY settings file.**
  Django's dictConfig runs inside the gunicorn worker AFTER gunicorn
  configured its own loggers; `True` silently disables `gunicorn.access`,
  so `--access-logfile -` produces NOTHING and you debug production
  blind (found 2026-08-31 on Panotxa, mid-incident, with zero request
  visibility — the cookiecutter's production.py shipped `True`).
- Apps log to **stdout/stderr only** (the host Alloy agent ships container
  stdout to Loki — `fleet-observability`); never to files in the
  container.
- **Gunicorn ships access logs** in the start script:
  ```bash
  exec gunicorn config.wsgi --bind 0.0.0.0:5000 \
    -c /app/gunicorn.conf.py \
    --access-logfile - \
    --access-logformat '%({x-forwarded-for}i)s "%(r)s" %(s)s %(B)s %(M)sms' \
    ...
  ```
  (`gunicorn.conf.py` exists for the prometheus `child_exit` hook — see
  `fleet-observability` §5.) Verify in Loki after deploy:
  `{project="<p>", env="prod", service="web"} |~ "\"GET /"` — an
  access-log CONFIG without a Loki line is exactly the swallowed-logger
  bug above.

## Health endpoints per role (owned here)

- **web**: `/health/` view returning db+cache status
  (`config/views.py::health_check`); Coolify UI check ON against it.
- **worker/beat**: an in-process HTTP `/healthz` on its own port
  (`config/healthserver.py`, started from `worker_ready`/`beat_init`
  signals) so Coolify's check can be ON for every resource — the estate
  end-goal is every resource `healthy` in Coolify, not just images.
  Container-level: `grep -q celery /proc/1/cmdline`, NEVER
  `celery inspect ping` (global `CLAUDE.md`).

## One image, ROLE-selected process (owned here)

Web/worker/beat are three Coolify **Dockerfile** resources built from ONE
image; `role-entrypoint` dispatches on `ROLE` env (`web`→`/start`,
`worker`→`/start-celeryworker`, `beat`→`/start-celerybeat`), explicit
commands bypass it so `docker exec … manage.py` one-offs still work.
Dockerfile resources keep blue-green; keep migrations additive —
during the rolling overlap the OLD code runs against the NEW schema.

## New-project checklist (each row = go to its owner)

1. Settings layout + `.envs/` + env inventory table BEFORE first deploy
   (hq deploying doc §0b).
2. LOGGING contract above; access logs verified in Loki.
3. Health endpoints per role; Coolify checks ON.
4. `oj.*` labels → logs; `config/prom.py` + `METRICS.md` + hub scrape +
   dashboard in the SCOPE org + alerts in org 1 (`fleet-observability`).
5. Celery: `celery-deploy-safety` + sizing rules; heartbeat/task hooks →
   Redis if worker/beat are unscrapeable resources.
6. Auth throttles on public endpoints; `api-idempotency` on unsafe POSTs.
7. Resend + anymail, mail from Celery tasks; Mailpit locally.
8. Sentry/GlitchTip with `release=` + `environment=` matching `oj.env`.
9. Release SHA: `app_info{version}` metric + `SOURCE_COMMIT`.
10. Backups per `coolify-deploy` + verify the R2 object, not the status.
11. Repo carries `DEPLOY.md`/`09-deploy-and-ops.md` with the standard
    status table, updated same-turn.
