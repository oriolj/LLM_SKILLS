---
name: celery-deploy-safety
description: Audit and fix a Django + Celery + Redis project so deploys, restarts, and crashes never silently lose background work. Use when the user asks to "check the Celery setup", "make tasks survive deploys", mentions stuck jobs / tasks lost after a deploy / rows frozen in "processing", or when shipping any new Django+Celery service to production (especially Coolify/Compose deploys without blue-green, where every deploy SIGTERMs the worker). Covers acks_late at-least-once delivery, Redis AOF persistence, orphan-resume sweeps, dispatch dedupe locks, transaction.on_commit dispatch, worker memory bounds, stop_grace_period, and how to verify the whole chain.
---

# Celery deploy-safety audit

A Django + Celery + Redis stack loses work in three independent ways; each needs its own fix, and **all three are required** — any one missing means silent loss. Audit in this order.

## The three failure modes

| # | Failure | Symptom | Fix |
|---|---------|---------|-----|
| 1 | Worker killed mid-task (deploy SIGTERM/SIGKILL) | Task acked-then-lost; row stuck in "processing" | acks_late trio |
| 2 | Redis restarts with queued tasks | Queue silently emptied (RDB snapshot up to 1h old) | AOF persistence |
| 3 | Message lost anyway (broker flushed, chain link dropped, beat dead) | Zombie DB rows in non-terminal states forever | Orphan-resume sweep |

## Audit commands (run these first)

```sh
# 1. acks_late trio configured?
grep -rn "ACKS_LATE\|PREFETCH_MULTIPLIER\|REJECT_ON_WORKER_LOST\|MAX_TASKS_PER_CHILD\|MAX_MEMORY_PER_CHILD" --include="*.py" config/ settings/ 2>/dev/null

# 2. Redis persistence (in compose or on the managed Redis resource)
grep -rn "appendonly" docker-compose*.yml compose/ 2>/dev/null
# On a live instance: redis-cli config get appendonly   → must be "yes"

# 3. Orphan sweep + boot hook + beat schedule
grep -rn "worker_ready" --include="*.py" .
grep -rn "PeriodicTask\|beat_schedule" --include="*.py" . | grep -iv test | head

# 4. Dispatch inside transactions (ATOMIC_REQUESTS makes bare .delay() race the row commit)
grep -rn "ATOMIC_REQUESTS" config/ settings/
grep -rn "\.delay(\|\.apply_async(" --include="*.py" . | grep -v "on_commit\|tasks.py\|test" | head -20

# 5. Graceful shutdown window
grep -rn "stop_grace_period" docker-compose*.yml

# 6. PID-1 signal handling (shell swallowing SIGTERM = 30s timeout every stop)
grep -rn 'sh -c\|bash -c' docker-compose*.yml compose/*/start* 2>/dev/null | grep -v exec
```

Anything missing → apply the corresponding fix below.

## Fix 1 — at-least-once delivery (acks_late trio + memory bounds)

```python
# settings
CELERY_TASK_ACKS_LATE = True               # ack only after success
CELERY_WORKER_PREFETCH_MULTIPLIER = 1      # don't grab batches we'd lose on SIGTERM
CELERY_TASK_REJECT_ON_WORKER_LOST = True   # SIGKILL'd tasks requeue too
# Recycle children between tasks (Python never returns high-watermark heap):
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50     # 50–200 typical
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 1_000_000  # KB! ≈ (RAM/concurrency)×0.75
```

**Precondition: every task must be safe to run twice.** Audit each task: internal tasks scoped to a DB row that records its own state are usually fine (a re-run converges; worst case one duplicate LLM/API call). Tasks that send email, charge cards, or post to external APIs need an idempotency key FIRST — don't flip acks_late on blindly.

Notes:
- Redis broker `visibility_timeout` defaults to 1h — fine while task `time_limit` < 1h; long tasks need it raised or they double-run.
- `MAX_MEMORY_PER_CHILD` is checked **between** tasks; a single 10 GB allocation still OOMs — cap at the call site (streaming reads, size guards).

## Fix 2 — Redis AOF

```yaml
redis:
  image: docker.io/redis:7
  command: ["redis-server", "--appendonly", "yes", "--appendfsync", "everysec"]
  volumes: [redis_data:/data]
```

Default RDB snapshots (`save 3600 1 …`) can be an hour stale under light load — every queued task in that window dies with a restart. AOF loses ≤1s.

**Managed/external Redis (e.g. a separate Coolify resource): the compose file in the app repo can't fix this.** Verify on the instance (`redis-cli config get appendonly`) and record the ops step in the project's launch checklist. This is the most commonly missed piece.

## Fix 3 — orphan-resume sweep

Even with 1+2, rows get stuck in non-terminal states (chain link dropped, beat dead during the window, pre-fix backlog). Write a sweep task that:

- queries every model with a non-terminal status (`processing`, `pending`, `analyzing`…) older than a cutoff (≥ a few × the task hard time limit; 30 min typical) and **re-dispatches the correct workflow per row state** (text vs image path, user-hint re-analysis, etc.);
- **parks rows older than ~24h in a terminal state** (`error`/`failed`) so the UI shows something actionable instead of retrying forever;
- runs **on every worker boot** (`celery.signals.worker_ready` → `.delay()`, wrapped in try/except so a startup hook can never crash the worker) **and hourly via beat** (django-celery-beat: install the `PeriodicTask` in a data migration, not by hand);
- **dedupes dispatch with `cache.add()`** (atomic SETNX) keyed per row, TTL > the task hard time limit — otherwise boot+hourly sweeps across N redeploys queue N copies of every stuck job. Task-side: early-return if the row is already terminal. **Both halves are required.**
- Don't forget the "completed-parent, missing-child" case: e.g. a meal marked finished whose scoring task was lost — sweep for `finished=True, score__isnull=True` within a recent window.

The sweep's cache locks need a **shared cache** — if `CACHES` is unset, Django uses per-process LocMem and the locks (and any DRF throttles) silently don't dedupe across workers:

```python
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL, "KEY_PREFIX": "djcache"}}
# tests: override to LocMemCache
```

## Fix 4 — dispatch correctness and shutdown

- **`ATOMIC_REQUESTS = True` + bare `.delay()` in a view = race**: the worker can pick the task up before the row commits (lock contention, IntegrityError retries, tasks queued for rolled-back requests). Wrap: `transaction.on_commit(lambda: my_task.delay(...))`. In tests, pytest-django's `django_capture_on_commit_callbacks(execute=True)` makes the existing `mock.delay` assertions work.
- **`stop_grace_period: 75s`** on the worker service so a clean shutdown can finish the in-flight task (default 10s usually kills it).
- **`exec` in start scripts** (`command: sh -c "exec celery …"`, entrypoints ending `exec "$@"`) — otherwise the shell is PID 1, swallows SIGTERM, and every stop is a 30s timeout + SIGKILL (which acks_late survives, but cleanly finishing is better).
- Long tasks (> ~10 min) should be **chunked** into per-chunk tasks with coordinator state on the parent row — a 2h monolith can never survive a deploy window.

## Verify (do this, don't assume)

1. Unit-test the sweep: backdate `updated_at` via `queryset.update()` (bypasses `auto_now`), mock the workflow dispatchers, assert: stale row re-dispatched with the right variant, fresh row untouched, 24h row parked terminal, second sweep blocked by the cache lock.
2. Live check: `docker compose exec <redis> redis-cli config get appendonly` → `yes`; boot a worker and confirm the sweep task fires in its log.
3. Staging fire-drill: start a slow task, redeploy mid-run. Expected: worker exits within `stop_grace_period`; the new worker's boot sweep (or broker redelivery) resumes it; the row reaches a terminal state; no duplicate side effects.
4. Settings smoke: `python -c "...django.setup(); print(settings.CELERY_TASK_ACKS_LATE, type(cache).__name__)"` inside the container.
