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
| Traces (OTel → host Alloy → Tempo): the pipeline, sampling policy, resource-attribute contract | `fleet-observability` skill §5f — the Django wiring is the "Tracing" section below |
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

**Tenant-scoped API (per-tenant uniqueness, hidden/draft gates, "which tenant
does this write target", sub-admin roles) → the `multitenant-drf-api` skill.**
It carries the four traps that produced ten production bugs in one day
(2026-09-03) and the regression matrix to write before shipping.

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
- 🔴 **Redefine the `django` logger in production, or Django e-mails
  every 500 to `ADMINS`.** `DEFAULT_LOGGING` is applied BEFORE your
  dict and gives `django` a `mail_admins` handler (AdminEmailHandler,
  ERROR, active when `DEBUG=False`); with `disable_existing_loggers:
  False` it survives unless you override the logger:
  ```python
  "django": {"level": "INFO", "handlers": ["console"], "propagate": False},
  ```
  Errors go to GlitchTip through `sentry_sdk` (the `glitchtip` skill),
  never to e-mail — Oriol's standing rule (2026-09-02, after EnaCast AI
  mailed him "[Django] ERROR (EXTERNAL IP)" reports). `propagate: False`
  also stops root's console handler printing each line twice.
- 🔴 **Never ship django-silk (or any request-recording profiler) in
  production.** Silk's per-request garbage collection (INSERT
  `silk_request`, DELETE past `SILKY_MAX_RECORDED_REQUESTS`) deadlocks
  Postgres whenever two requests overlap → random `deadlock detected`
  500s on real traffic (EnaCast AI, 2026-08-25 → 2026-09-02), and it
  stores every visitor's headers/bodies. Silk lives in `local.py` only,
  used against a prod snapshot (`prod-db-sync`); production profiling is
  **traces in Tempo** (`fleet-observability` §5f + the Tracing section
  below) plus the Prometheus request histogram. Running silk "at 1 % with
  bodies capped" keeps the hazards and loses the value — don't.
- **Every log line ends in `trace_id=%(otelTraceID)s span_id=%(otelSpanID)s`**
  (the token Grafana's Loki datasource turns into a Tempo link), with a
  `logging.Filter` that defaults both to `"0"` so the format never
  KeyErrors when tracing is off. Shape: `config/tracing.py`
  `TraceContextFilter` + `LOGGING["filters"]` in `oriolj/llm-index-watcher`.
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

## Tracing — the Django wiring (owned here; the pipeline is `fleet-observability` §5f)

Reference: `oriolj/llm-index-watcher` `backend/config/tracing.py` (2026-09-05).

- Deps: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`,
  `opentelemetry-instrumentation-{django,psycopg,redis,celery,httpx,logging}`
  (instrumentation versions track the SDK: `0.63b1` ↔ `1.42.1`).
- **One module, `config/tracing.py`**: `init_tracing()` is a no-op unless
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set (dev/tests/agent-less hosts run
  untraced), builds `TracerProvider(resource=…)` with
  `service.name=f"{project}-{ROLE}"`, `service.namespace=project`,
  `deployment.environment=<oj.env>`, `service.version=APP_VERSION`, adds
  `BatchSpanProcessor(OTLPSpanExporter())` (the exporter reads the env
  itself and appends `/v1/traces`), `set_tracer_provider`, then instruments
  Django/psycopg/redis/httpx/logging. `os.environ.setdefault(
  "OTEL_PYTHON_DJANGO_EXCLUDED_URLS", "up/,metrics")`. Idempotent, wrapped
  in try/except — tracing must never take the app down.
- **Call it from an `AppConfig.ready()`** (every process: web, worker,
  beat, one-offs), BEFORE anything else that might create a provider
  (Langfuse). Without `--preload` each gunicorn worker imports the app
  after fork, so this is per-worker; with `--preload` move the call to a
  `post_fork` hook (`BatchSpanProcessor` threads do not survive fork
  cleanly).
- **Celery**: `CeleryInstrumentor().instrument()` must run in the prefork
  CHILD — a `worker_process_init` receiver in `config/celery.py` calling
  `instrument_celery_worker()`; the child inherits the provider from the
  parent's `ready()`.
- **No head sampling in the app** (the agent tail-samples) — the ONE
  sampler rule is structural, not statistical: `ParentBased(ALWAYS_ON)`
  wrapped so a CLIENT span with no valid parent is dropped (`/metrics`
  collector queries, heartbeat Redis calls, beat polls, migrations would
  each be a one-span trace otherwise — `_NoOrphanClientSpans` in the
  reference). `traces_sample_rate` in `sentry_sdk.init` stays 0.
- **Langfuse coexistence**: one global provider per process. When tracing
  owns it, Langfuse's OTLP exporter is added to THAT provider behind a
  span-processor wrapper that forwards only `pydantic-ai`/`langfuse` scopes
  (so Django/DB spans never spend Langfuse quota); Langfuse creates its own
  provider only when tracing is off. Never `set_tracer_provider` twice.
- LOGGING: the `trace_id=` suffix + filter from the LOGGING contract above.
- Tests: no endpoint → `init_tracing()` False and no SDK provider; endpoint
  set → resource attributes as above, idempotent; Langfuse after tracing
  reuses the provider; the filter defaults to `"0"`. Reset
  `trace._TRACER_PROVIDER` / `_TRACER_PROVIDER_SET_ONCE._done` in the
  fixture — the SDK allows one global provider per process.

## Cache resilience — the contract (owned here, learned 2026-09-04 on EnaCast)

A Django cache that raises turns every request into a 500: DRF's throttles,
tenant lookups and the cache middleware all touch it before the view. A cache
that silently never raises is wrong for two consumers. The house contract:

1. **The configured backend never raises and never stores an oversized
   value.** Wrap the backend (get → miss, set → False, log rate-limited to
   one ERROR line per exception type per minute, that line IS the Sentry
   event — no extra `capture_exception`), and cap writes at
   `CACHE_MAX_VALUE_BYTES` (512 KB) INSIDE the backend, measured with a
   counting pickler that stops at the limit. Reference:
   `EnaCast/enacast` `generic_tools/cache_backends.py` + `docs/cache.md`.
2. **Then decide per consumer, in a table in `docs/cache.md`:**
   - throttles that ARE an abuse control (signup, magic link, social login)
     read a `strict` alias (same store, unwrapped) and answer 429 on an
     outage (`FailClosedAnonRateThrottle`); the global "anon/user" limits stay
     fail-open;
   - `cache.add` dedupe locks fail OPEN (a duplicate beats dropped work):
     False must not mean both "held" and "unavailable";
   - tenant/session/response caches degrade to the DB.
3. **Django cache = its own Redis** (`allkeys-lru`, `maxmemory`, no
   persistence), never the Celery/RQ broker DB, never pylibmc/memcached
   (libmemcached 1.0.16 marks the server dead for `retry_timeout` after ONE
   refused write — that was the outage). Local L1 rule as in CLAUDE-global.
4. **Deploy flush once per release**, from the first container that starts
   (`SET NX` on the release tag, raw redis client, non-zero exit when it did
   not happen). Ten containers each flushing what the others re-warmed, or a
   flush that "succeeds" on a dead backend, are both wrong.
5. **Module-level `redis.StrictRedis(...)` clients are banned**: one factory
   (`get_redis(db)`) reading `settings.REDIS_CLIENT_KWARGS` (connect timeout,
   keepalive, health check; no socket_timeout where a worker BLPOPs).
6. `?ordering=` goes through a `SafeOrderingFilter` (unknown or
   serializer-only terms ignored, `pk` accepted, full lookup path validated) —
   DRF's stock `OrderingFilter` without `ordering_fields` orders by any
   serializer field and 500s on method-backed ones.

## Health endpoints per role (owned here)

- **web**: `/health/` view returning db+cache status
  (`config/views.py::health_check`); Coolify UI check ON against it.
- **worker/beat**: an in-process HTTP `/healthz` on its own port
  (`config/healthserver.py`, started from `worker_ready`/`beat_init`
  signals) so Coolify's check can be ON for every resource — the estate
  end-goal is every resource `healthy` in Coolify, not just images.
  Container-level: `grep -q celery /proc/1/cmdline`, NEVER
  `celery inspect ping` (global `CLAUDE.md`).
  ⚠️ With `init: true`, or celery launched via its python shebang, PID 1 /
  argv[0] are NOT celery — use the argv[0..1] scan form in the
  `coolify-deploy` skill §5 (EnaCast prod, 2026-09-03).

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
12. Tracing: `config/tracing.py` + `AppConfig.ready()` + Celery
    `worker_process_init`; `OTEL_EXPORTER_OTLP_ENDPOINT=http://oj-alloy:4318`
    as runtime-only env on every role once the host's agent has the trace
    lane (`fleet-observability` §5f ordering); `trace_id=` in the log format;
    `make traces-slow / traces-errors / traces-sql / traces-routes / trace ID=`
    in the Makefile next to `make logs*`; the «<Project> trazas» dashboard.
    After the first deploy and after every later one: `make traces-errors`
    + `make traces-slow SINCE=30m` are part of the verification
    (`fleet-observability` §5g) — an agent that deploys and does not look
    at the traces has not verified the deploy.
