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
| Moving the database to another engine (MariaDB/MySQL → PostgreSQL/TimescaleDB) with proof of before = after | `django-db-migration` skill |
| DRF pagination/list-page footguns | global `CLAUDE.md` §DRF + Next.js |
| Slow endpoints: measuring per route, deep pagination, join-only filters, deferred-field N+1, stale `_<fk>_cache` checks, cache-busters | "Query performance" below |
| `/metrics`, prom.py collectors, multiproc, scrape lanes, dashboards/orgs | `fleet-observability` skill §5, §5c |
| Traces (OTel → host Alloy → Tempo): the pipeline, sampling policy, resource-attribute contract | `fleet-observability` skill §5f — the Django wiring is the "Tracing" section below |
| Idempotent write endpoints (client tokens) | `api-idempotency` skill |
| JWT/session login resilience | `auth-session-resilience` skill |
| Tenancy isolation | `multitenancy-guardrails` skill |
| LLM calls (PydanticAI + Langfuse) | `pydantic-ai-langfuse` skill |
| Email: Resend via django-anymail, Mailpit locally, send from Celery | global `CLAUDE.md` |
| Email subjects and text/plain bodies from templates: `{% autoescape off %}` + a static test | "Plain-text email templates" below |
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

**`DATABASES` `OPTIONS` timeouts are production behaviour, not a probe
setting** (EnaStats, 2026-09-10): a `read_timeout` bounds EVERY statement of
every process, and a review's `read_timeout: 10` killed the collector's
legitimately slow writes for half an hour after each MariaDB restart (cold
33 GB buffer pool — 76 write errors, 8 crashed passes in 4 min). Set it above
the slowest legitimate statement INCLUDING cold-cache phases (300 s there),
or bound only the probe's own connection — `fleet-observability` §5f.

## LOGGING — the contract (owned here)

- 🔴 **`"disable_existing_loggers": False` in EVERY settings file.**
  Django's dictConfig runs inside the gunicorn worker AFTER gunicorn
  configured its own loggers; `True` silently disables `gunicorn.access`,
  so `--access-logfile -` produces NOTHING and you debug production
  blind (found 2026-08-31 on Panotxa, mid-incident, with zero request
  visibility — the cookiecutter's production.py shipped `True`).
- 🔴 **Never list `gunicorn.access` / `gunicorn.error` under `LOGGING["loggers"]`.**
  dictConfig REPLACES a listed logger's handlers with the ones you list; an
  entry "to pin the level" with no handlers strips the handler gunicorn gave
  it (`--access-logfile -`) and silences the access log even with
  `disable_existing_loggers: False` — the second way to lose it (BikeCRM,
  2026-09-12, caught on the first prod scrape). Leave gunicorn's loggers alone.
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

**Never keep durable work in the cache's Redis** (EnaCast, Codex review 2026-10-02): a
queue of pending work (tags to purge, events to flush) put in the default cache's Redis
is erased by the per-release `FLUSHDB`, by `allkeys-lru` eviction and by a restart of a
store without persistence. Pending work goes to the persistent auxiliary Redis
(`generic_tools/redis_clients.get_redis(settings.REDIS_AUXILIARY_DB)`, like EnaCast's
content_events buffer and its Cloudflare purge queue) or a DB outbox; the cache keeps
only what can be recomputed.

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
6. 🔴 **A fail-closed branch written as `except Exception` is dead code on a
   cookiecutter project** (Panotxa, 2026-09-07). The stock production
   `CACHES` is `django_redis` with **`IGNORE_EXCEPTIONS: True`**, whose
   `omit_exception` decorator **swallows** connection errors and returns
   `None`. Nothing raises, so the `except` never runs; the code falls
   through and `None > ceiling` raises TypeError → **500 on every request
   for the length of the Redis outage**, each one an event in the project's
   own error tracker. Any consumer that means to refuse must treat a `None`
   from `add()`/`incr()`/`get()` as "unavailable", not as a value — or read
   the unwrapped `strict` alias from item 2. **Test it against the real
   backend's behaviour**: a test that mocks a *raised* exception passes
   while production returns `None`. Verified with the installed
   `django_redis` against a closed port: `add` → `None`, `incr` → `None`.
   **It recurred and shipped to prod** (H2A LeadHunter, 2026-10-03): a new
   public short-link click limiter compared `cache.incr()` with its limit
   outside the `try`, and its "fails open" test mocked a raised exception —
   every tracked link in outreach mail 500'd while Redis was down; the
   Pulse ingest limiter had the same shape. Fix shape: ONE helper per
   project for fixed-window counters, `add` + `incr` → `int | None`
   (`None` for raised, swallowed `None`, and the `ValueError` of a key
   evicted between the two calls), with the fail-open / fail-closed
   decision at each caller — reference `humans2agents`
   `agents/leadhunter/backend/leadhunterbackend/common/cache_counters.py`
   + `common/tests/test_cache_counters.py` (mocks `return_value=None`).
   Grep a project for `cache.incr(` before adding a new limiter.
7. `?ordering=` goes through a `SafeOrderingFilter` (unknown or
   serializer-only terms ignored, `pk` accepted, full lookup path validated) —
   DRF's stock `OrderingFilter` without `ordering_fields` orders by any
   serializer field and 500s on method-backed ones.

## Startup configuration checks must be executed

Registering a Django system check in `AppConfig.ready()` does not run it.
Verified with Django 4.2: `migrate` requests no system checks; `collectstatic`
requests only checks tagged `staticfiles`; Gunicorn loading WSGI does not run
management-command checks. A required CAPTCHA/provider configuration check can
therefore exist and pass tests while never gating production startup.
Give feature checks a tag and invoke `python manage.py check --tag <feature>`
explicitly in the relevant start script before serving traffic. Feature-disabled
checks should return no errors. Test both the missing-config error and the tag
used by startup; do not infer execution from registration alone.

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

**The web boot refuses models without their migration** (learned 2026-10-01 on Cuentakos: a
commit with explicit paths left the new migration file staged but uncommitted; `migrate`
only *warned* "models have changes not yet reflected in a migration", the container passed
its health check and every query on that table 500'd). Before `migrate`, the web role runs
`python manage.py makemigrations --check --dry-run --noinput`, and `set -e` makes a mismatch
fail the boot, so blue-green keeps the previous container. Pair it with a test that calls the
same command. When committing explicit paths, list new files (migrations) too, or check
`git status` for staged-but-uncommitted files after the commit.

## Local compose — pin the project name (owned here, learned 2026-09-06 on NutriLens)

Every Django repo's local compose lives in a directory called `backend`, so
compose's default project name is `backend` for all of them on one machine:
they share `backend_default`, and each one's `redis` / `postgres` service
name resolves to *whichever* container answers. Symptom: Celery tasks
intermittently "never arrive" — they were published to another project's
broker, whose worker fails them `NotRegistered`; web requests can hit the
wrong database the same way. Rules:

- `docker-compose.local.yml` starts with `name: <project>` (e.g.
  `name: nutrilens`). Container names alone (`container_name:`) do NOT
  isolate the network.
- Renaming an existing project would orphan its data volumes: keep them by
  giving each volume an explicit `name: <oldproject>_<volume>` and
  `external: true`, and document the one-time `docker volume create` for
  fresh machines.
- **Never `docker compose down --remove-orphans` on a machine like this**:
  with a shared project name it removes the other repos' containers (it took
  BudgetBuddy's dev stack down; volumes survived, containers had to be
  recreated with `up -d --no-build`).

## Every `@shared_task` must be discoverable by a real worker (owned here, learned 2026-10-01 on Cuentakos)

`app.autodiscover_tasks([...])` imports only `<app>.tasks` of the apps it is given. A task
defined in any other module (`lab_runner.py`, `emails.py`), or in an app missing from the
list, is **unregistered** on the worker: Celery logs `Received unregistered task … discarded`
and the work silently never happens. Tests run with `CELERY_TASK_ALWAYS_EAGER`, which calls
the function directly, so the whole suite stays green. Rules:

- Register each extra module explicitly:
  `app.autodiscover_tasks(lambda: ["proj.workflows"], related_name="lab_runner")`.
- Ship a test that runs in a **fresh interpreter**: `django.setup()`, import the Celery app,
  `app.loader.import_default_modules()`, print `app.tasks`, and assert that every
  function decorated with `shared_task` (found by an AST scan of the source) is in it.
  Reference: `cuentakos/backend/cuentakos/core/tests.py::test_worker_registers_every_shared_task`.
- After a deploy that adds a task, grep the worker log for `unregistered task`.

## Plain-text email templates turn autoescape off (owned here, learned 2026-10-03 on BikeCRM)

Django autoescapes **every** template, `.txt` included. A subject rendered with
`render_to_string("…_subject.txt", ctx)` turns a shop called «Bike shop girona's workshop» into
`Bike shop girona&#x27;s workshop` (`&amp;` for «&», `&lt;` for «<»), and nothing downstream
un-escapes a subject or a text/plain body. HTML bodies are right to escape; plain text is not.
BikeCRM had it in its password reset and demo-ready subjects in production for months: every
test fixture used plain ASCII names.

- Wrap the WHOLE content of every plain-text template (subjects, text/plain bodies, SMS/WhatsApp
  text if templated): `{% load i18n %}{% autoescape off %}…{% endautoescape %}`. Wrapping outside
  `{% blocktranslate %}` keeps the msgids, so no `.po` work.
- Ship a static test that fails for any `*.txt` under a `templates/` dir without it, plus rendered
  subjects with `O'Brien & <Co> "Bikes"` per language. Reference:
  `bikecrm-backend/tests/test_email_plain_text_escaping.py`.
- Email test fixtures include a name with `'` and `&` — Catalan/Spanish/French names have
  apostrophes («L'Estació»).
- Subjects built in Python (f-string, `%`, `gettext`) are not escaped and need nothing; `mark_safe`
  in the context is the wrong fix (it also disables escaping in the HTML body that shares it).

## Aware datetimes and DST: compare instants, not wall clocks (learned 2026-10-03 on EnaCast)

- **Two aware datetimes with the SAME `tzinfo` compare by wall clock and ignore `fold`** (Python's
  intra-zone rule). On a fall-back night `02:30+02:00` and `02:30+01:00` (`fold=1`, an hour later) compare
  EQUAL, so an hour-long airing in the repeated hour looked empty and was dropped from a schedule grid.
  Compare `.timestamp()` (or convert both to UTC) whenever a value can sit in the repeated hour.
- **`aware + timedelta` is wall-clock arithmetic** and resets `fold` to 0: `02:30 (fold=1) + 60 s` is the
  FIRST `02:31`, an hour earlier in real time. When a duration is real time (a recorder's "start + N
  seconds"), add it in UTC: `(dt.astimezone(UTC) + delta).astimezone(tz)`.
- **freezegun's `FakeDatetime` drops `fold` in `astimezone`**: a DST test under `freeze_time` can pass
  while the bug it targets is live. Run DST cases without freezing the clock (pass the date in), and
  prove the test fails against the old code.

## Query performance — measure first, then these traps (owned here, learned 2026-10-05 on EnaCast)

Context: a request to "rewrite the hottest endpoints in Rust" turned into a day of Django fixes once
measured — the slow requests spent 85–99 % of their time in SQL, so a faster runtime would have changed
nothing. Write-up and numbers: `EnaCast/enacast` `docs/performance.md`. The workflow:

1. **Where the time goes, per route, before anything else.** With traces: `fleet-observability` §5g.
   Without: the reverse proxy's access log (route × count × duration → share of worker time) —
   `make routes-caddy` / `scripts/caddy_route_profile.py` in the EnaCast backend.
2. **Group the hot route by query-string SHAPE** (which params, page depth): one endpoint is usually
   three different problems (deep pages, one filter, one join).
3. **Reproduce on a production-scale copy** (`prod-db-sync`) through the real view with
   `connection.execute_wrapper` timing every statement — total vs SQL vs Python per request, the
   slowest statements, and the query COUNT (an N+1 shows as N identical shapes). `EXPLAIN` the slow ones.
4. **Before claiming a cache win, replay the logged hour against the proposed cache key** (distinct keys,
   hit rate at the TTL). Behind a CDN the backend sees misses: mostly one-off URLs a cache cannot absorb.

The traps, each one found in production code that day:

- **Deep `?page=N` on a wide table**: OFFSET reads every skipped full row. Paginate over pks through a
  covering index, then load the page's rows by pk (`DeferredJoinPagination`, EnaCast
  `api_ng/PaginationConfig.py`; 8.2 s → 0.5 s on page 1438). Not for `.distinct()` querysets.
- **A join that exists only to filter** (`programa__hidden_program=False`, `programa__tags__slug=x`) lets
  MariaDB lead with the small table and sort every match in a temporary table — and an unrelated index
  can flip the plan into that (70 ms → 2.5 s). Resolve the ids first (`list(Model.objects.filter(…)
  .values_list('id', flat=True))`) and filter/exclude `fk_id__in=` on the big table. Re-profile EVERY slow
  shape after adding any index.
- **A filter on a column no index leads with** (a year range on `utcdatetime` while the indexes lead with
  `datetime_to_publish`): a covering index `(tenant, flags…, filtered column, order column, fk)` makes
  the COUNT and the pk page index-only (5 s → 0.3 s).
- **A property that reads a deferred field** (`transcription`, deferred by the manager because it is
  megabytes) is one query PER ROW in a list (200 on a 200-row page). Annotate the derived value on the
  list queryset (`Case(When(...))`) and let the property prefer the annotation.
- **`hasattr(self, '_<fk>_cache')` is Django 1.x.** Since 2.0 a loaded relation lives in
  `self._state.fields_cache['<fk>']`; the old check is silently always False, so a "use the prefetched
  object" fast path never fires (EnaCast: 1,000 cache round-trips, 2.4 s, per 200-row page). Grep for
  `_cache')` in model methods.
- **`.first()` / `.last()` to get a date bound** loads whole rows (`.last()` without the manager's
  `defer` loaded the transcript): `aggregate(Min(...))` / `Max` on an index-leading column answers from
  the index (3.4 s → ms). Do not memoise such values on an instance that gets pickled into the cache.
- **Client cache-busters** (`rnd=`, a per-second `ts=`, `since_ts=<now>`) in the URL defeat a URL-keyed
  response cache and let any anonymous client force uncached queries. Freshness belongs to the
  invalidation (a per-tenant generation bumped on save/purge); strip buster params from the key and do
  not honour them in production (`CACHE_BUSTER_PARAMS`, EnaCast `drf_extension_custom_utils.py`).
- **A side-effecting GET**: serializing an episode whose file is missing hides it (`save()` inside a
  read). Profiling scripts and tests then see 404s on the second request — give fixtures valid state.

## Sentry: drop `manage.py shell` events, keep switched-off pages out of 5xx (owned here, BikeCRM 2026-10-05)

- `before_send` that drops every event raised from an interactive command process
  (`sys.argv[1] in {"shell", "shell_plus", "dbshell"}` with `argv[0]` ending in `manage.py`):
  a typo in a one-off script an agent pipes into `manage.py shell -c` on the server otherwise
  reaches Sentry as a production error and pages someone (3 of 4 BikeCRM issues in one weekend).
  Web, worker and migrate errors stay. Reference: `bikecrm-backend/config/sentry_filters.py` + test.
- A feature that is deliberately OFF answers its branded page with **404**, never 503: Django logs
  every 5xx as a `django.request` ERROR and the 5xx-rate panels/alerts count it — a monitor probing
  the switched-off page every 15 min looked like an incident.
- gunicorn ≥ 25 opens a control socket under `$HOME`; for a `--no-create-home` user pass
  `--control-socket /tmp/gunicorn.ctl` (or `--no-control-socket`) or it logs `Control server error:
  Permission denied` forever.

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
    in the Makefile next to `make logs*`; the `<Project> traces` dashboard (English — the global rule of 2026-09-09).
    After the first deploy and after every later one: `make traces-errors`
    + `make traces-slow SINCE=30m` are part of the verification
    (`fleet-observability` §5g) — an agent that deploys and does not look
    at the traces has not verified the deploy.
