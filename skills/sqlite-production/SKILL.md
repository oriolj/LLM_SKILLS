---
name: sqlite-production
description: Run SQLite safely in production - Docker, blue-green deploys, backups. Use when the user asks "can I use SQLite in production", puts SQLite on a Docker volume, shares a database file between containers, deploys SQLite apps on Coolify (rolling updates / zero-downtime), hits SQLITE_BUSY or "database is locked", asks about WAL mode, busy_timeout, Litestream, SQLite backups, or chooses between SQLite and Postgres for a small self-hosted service. Covers required pragmas, the -wal/-shm file trio, single-writer discipline (BEGIN IMMEDIATE), same-host multi-container safety, additive-only migrations for deploy overlap, Go and Django connection setup, and backup strategies that don't corrupt data.
---

# SQLite in production

SQLite is a production-grade choice for single-host services with moderate write volume (form backends, internal tools, edge apps, read-heavy sites). One file, no DB server to run, backups are trivial. The rules below are what make it safe; most "SQLite corrupted my data" stories are a violation of one of them.

## When SQLite is the wrong choice

Hard disqualifiers - use Postgres instead:

- **Multiple hosts** accessing one database (horizontal scaling, multi-server Coolify/Swarm/K8s).
- **Networked filesystems** (NFS, SMB, most "persistent volume" abstractions in managed K8s). File locking is broken or lying there; corruption is a matter of time.
- **Many concurrent writers with long transactions** - SQLite has one writer at a time; sustained write contention means queueing, not parallelism.

Same-host concurrency (multiple processes/containers on one machine, local disk) is NOT a disqualifier - see below.

## Non-negotiable connection settings

Set on every connection, in every process that opens the DB:

```sql
PRAGMA journal_mode=WAL;      -- persistent, but set it anyway; enables concurrent readers + 1 writer
PRAGMA busy_timeout=5000;     -- wait for locks instead of instantly failing with SQLITE_BUSY
PRAGMA synchronous=NORMAL;    -- safe with WAL, much faster than FULL
PRAGMA foreign_keys=ON;       -- OFF by default (per-connection!)
```

- WAL mode is stored in the database file, but `busy_timeout`, `synchronous` and `foreign_keys` are **per-connection** - configure them in the driver DSN or an init hook, not manually once.
- "Database is locked" errors in an otherwise sane app almost always mean a missing `busy_timeout`.

## The file trio

A live WAL database is **three files**: `app.db`, `app.db-wal`, `app.db-shm`. Treat them as one unit:

- Never copy/rsync/snapshot a live `app.db` alone - you get a torn, possibly corrupt copy missing recent writes. Use a real backup method (below).
- Never delete `-wal`/`-shm` while any process has the DB open.
- The volume/bind mount must contain the directory, not just the db file, so the sidecar files land on the volume too.

## Write discipline

- SQLite allows many concurrent readers and exactly **one writer**. Keep write transactions short (single INSERT/UPDATE, no network calls inside a transaction).
- Start write transactions with `BEGIN IMMEDIATE`, not plain `BEGIN`. A deferred transaction that starts reading and later upgrades to a write can deadlock-abort with `SQLITE_BUSY` **without respecting busy_timeout** in some paths; IMMEDIATE takes the write lock up front and queues politely.
- Append-mostly workloads (event logs, form submissions, queues) are the ideal case.

## Docker: containers sharing one database

Verified safe (Simon Willison's Apr 2026 research, https://simonwillison.net/2026/Apr/7/sqlite-wal-docker-containers/) **when all conditions hold**:

1. All containers run on the **same host** (shared kernel -> `fcntl()` locks and the mmap'd `-shm` file work correctly across containers).
2. The DB lives on a **local named volume or bind mount** - never NFS or other network storage.
3. WAL mode + `busy_timeout` everywhere (above).

Under these conditions, writes from one container are immediately visible in the other and locking is correct. Cross-host sharing is never safe.

## Blue-green / rolling deploys (Coolify)

Old and new containers overlap for a few seconds, both holding the DB open. This works if:

- All connection rules above are followed (both containers wait on locks correctly).
- **Migrations are additive-only and idempotent**, run at container startup: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN`. During the overlap the *old* binary runs against the *new* schema - never rename/drop/repurpose columns in the same release that stops using them (two-phase: release N stops using, release N+1 drops).
- Write transactions are short, so lock handover during the swap is milliseconds.

Coolify specifics (https://coolify.io/docs/knowledge-base/rolling-updates): rolling updates require a passing **health check** (make it open the DB, not just return 200), **default container names**, **no host port mappings**, and are **not available for Docker Compose resources** - use the Dockerfile application resource type. Attached volumes do not disable rolling updates; the volume is mounted into both containers during overlap, which is exactly the same-host scenario above.

## Backups

Never `cp`/rsync a live database. Options, best first:

1. **Litestream** (https://litestream.io) - streams WAL frames to S3-compatible storage continuously; restore to any point in time. Run as a sidecar process, or embedded in-process in Go apps (litestream as a library) to keep a single-container deploy. This should be the default for any production SQLite.
2. **`VACUUM INTO '/backup/app-$(date).db'`** - produces a consistent, compacted single-file snapshot while live; ideal for cron-based backups.
3. **`sqlite3 app.db ".backup /backup/app.db"`** - the online backup API; consistent, works while live.

Test restores. A `-wal`-aware restore from Litestream or a `VACUUM INTO` file is a plain single file - trivial to verify by opening it.

## Driver setup cheatsheet

**Go** - prefer `modernc.org/sqlite` (pure Go, no cgo, easy cross-compilation/distroless):

```go
dsn := "file:/data/app.db?_txlock=immediate" +
    "&_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)" +
    "&_pragma=synchronous(NORMAL)&_pragma=foreign_keys(ON)"
db, err := sql.Open("sqlite", dsn)
// Optional but robust: two pools - a read pool (many conns, no _txlock)
// and a write pool with db.SetMaxOpenConns(1) to serialize writers in-app.
```

**Django** (5.1+ has first-class support for the important bits):

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "app.db",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",   # Django 5.1+; BEGIN IMMEDIATE for writes
            "timeout": 5,                      # busy_timeout in seconds
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
            ),
        },
    }
}
```

## Ops notes

- WAL auto-checkpoints around 1000 pages by default; under constant read pressure the `-wal` file can grow - monitor its size, and if needed run `PRAGMA wal_checkpoint(TRUNCATE);` from a periodic job.
- `PRAGMA optimize;` on connection close (or nightly) keeps the query planner statistics fresh.
- Litestream replication lag and last-successful-sync are the two backup metrics worth alerting on.
- Store the DB in a subdirectory of the volume (e.g. `/data/app.db`) so file permissions and sidecar files are simple to manage.
