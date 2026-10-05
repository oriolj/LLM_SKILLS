---
name: django-db-migration
description: Move a production Django project from MariaDB/MySQL to PostgreSQL (or TimescaleDB) with proof that no data and no API answer changed - the staged plan, the dual-engine code period, fingerprint/copy/snapshot tooling, the local rehearsal gate, backfill, cutover and rollback, and every trap the EnaStats move (145 M rows, 2026-10) hit. Use when migrating any Django app between database engines, replacing MySQL partitioning, moving a big table to a TimescaleDB hypertable, planning a database cutover with a rollback, or proving before = after for a data migration.
---

# Django: MariaDB/MySQL → PostgreSQL / TimescaleDB, proven

Field-tested on EnaStats (2026-10-04/05):
- 145 M rows, 262 GB MariaDB → 13 GB TimescaleDB.
- Python 3.8/Django 4.2 → 3.13/5.2, compose → Coolify Dockerfile resources.
- ~13 min collector pause, no API downtime, data and API answers proven identical.

Everything below is generic. The reference implementation is the EnaStats repo (map at the end); copy its tools
rather than rewriting them.

**Oriol's bar for any data migration** (memory `data-migrations-prove-before-equals-after`):
1. A verified backup before anything else, and a local copy of it.
2. A JSON fingerprint of the data taken before and after, then diffed.
3. The whole migration rehearsed locally on a restored copy of production before production is touched.

Plan for all three from the start.

## The staged plan (each step deployable and reversible alone)

| Step | What | Gate |
|---|---|---|
| 0 | Read-only facts from production (below), verify the newest backup, write the living plan doc in the repo (`docs/<db>-migration.md` with a status table) | facts recorded |
| 1 | Remove engine-specific libraries that block upgrades (EnaStats: `architect` partitioning) while still on the old engine | suites green on the old engine |
| 2 | Upgrade Python/Django on the old engine | same |
| 3 | Make the code run on **both** engines + build the tooling (fingerprint, copy, API snapshot) + new image/role layout | suites green on sqlite, MariaDB **and** Postgres, plus cross-engine tool tests |
| 4 | **Local rehearsal** on the restored production dump: copy, fingerprints, API snapshots, cutover delta, rollback | zero diffs (or each one explained and accepted in writing) |
| 5 | Production resources (database resource, Redis, apps) built empty; workers created **stopped** | apps healthy, nothing serving |
| 6 | Production backfill + parity on closed periods (old store stays primary) | closed-period fingerprints identical |
| 7 | Fresh backup → pause writers → delta of the live periods → fingerprint → switch | live fingerprints identical = go |
| 8 | Soak 2–4 weeks, restore drill, remove the old engine's code paths, delete the old store (owner's call) | restore drill matches live |

Do not merge steps. Steps 1–3 kept production on MariaDB until the very end. Turning **auto-deploy OFF on the old
resource before the first push** meant production never ran the new code on the old database at all: the switch
is a cutover, not a series of risky deploys.

## Step 0: facts that change the design

- **Collation.** Run `SHOW CREATE TABLE` and `information_schema.COLUMNS.COLLATION_NAME`.
  - `utf8mb3_general_ci` / `utf8mb4_*_ci` make `DISTINCT`, `GROUP BY` and `=` case-insensitive and blind to
    trailing spaces. Postgres compares bytes.
  - Any "unique visitors" style count changes unless you emulate it: `Lower(RTrim(col))` on the Postgres branch
    only.
  - EnaStats had to emulate it to keep API answers identical.
- **Sizes per table.** Use `information_schema.TABLES` for estimates, `du` on the datadir for the truth; the two
  don't add up, so never quote their sum as one number.
  - Look for junk: EnaStats' biggest table (662 M rows, 106 GB) was 10 years of alert-error spam.
  - Decide what moves (EnaStats: the last 90 days of the log table) and keep the rest in the dump. Find the cutoff
    id by binary search on the primary key; a `WHERE datetime > …` with no index is a full scan.
- Row counts per month/partition, `MAX(id)`, invalid values the new types will reject (`GenericIPAddressField` is
  `inet` on Postgres; garbage IP strings fail COPY).
- **Free disk and RAM on the target host**, and **where Docker's data root is.** A database resource's default
  volume lands there; on storage-1 that is an HDD RAID5. See below for putting it on fast disk.
- **The backup:** find the newest logical dump, `gzip -t`, compare sha256 on both ends, keep a local copy until
  step 8.

## Step 3: code that runs on both engines

- **Settings:** the engine comes from env (`DB_ENGINE`), with per-engine options:
  - MySQL `read_timeout` ↔ Postgres `options: -c statement_timeout=…`
  - `CONN_HEALTH_CHECKS=True`
  - an optional second alias (`legacy`, from `LEGACY_DB_*`) only when set, for the copy and verify tools
- **Raw SQL → ORM wherever possible.** Backticks, `COUNT(DISTINCT a, b)` (MySQL-only: use
  `.values(a, b).distinct().count()`) and date-string `BETWEEN 'Y-m-d' AND …` padding all need translating.
  Reproduce the padding's exact bounds in Python: it is part of what the query counts.
- **Custom `Func`s with `as_mysql` need `as_postgresql`.** `TIMESTAMPDIFF` → `FLOOR(EXTRACT(EPOCH FROM x))`;
  `MICROSECOND(x)` → `MOD(EXTRACT(MICROSECONDS FROM x)::bigint, 1000000)`. Avoid `%` in templates: psycopg treats
  it as a placeholder.
- **AVG:** MariaDB returns a DECIMAL rounded half-up to 4 places; Postgres returns full precision. For identical
  output, compute sum/count and quantize in Python for both engines.
- **`SET STATEMENT max_statement_time=… FOR`** (MariaDB) → `SET statement_timeout` … `RESET statement_timeout`
  around the block.
- **`bulk_create(update_conflicts=True)`:** pass `unique_fields` where `supports_update_conflicts_with_target`
  (Postgres yes, MySQL no).
- **Reconnect logic keyed on mysqlclient codes (2006/2013)** needs a psycopg branch: `InterfaceError`, or the raw
  connection `.closed` / `.broken`.
- **`information_schema` growth/partition metrics** → `pg_stat_database`, `hypertable_detailed_size()`,
  `approximate_row_count()`.
- **Metrics/dependency labels** follow the engine (`postgres` vs `mariadb`). Dashboards use
  `(old expr) or (new expr)` so history stays visible.
- **Data migrations (`RunPython`) must write through `schema_editor.connection.alias`.** Plain `Model.objects`
  writes to `default` and seeds it twice once a second alias exists. EnaStats' 0002/0004 crashed the cross-engine
  test setup this way.
- **Engine-specific DDL** (hypertable, PK change, compression) goes in a `RunPython` that returns early unless
  `connection.vendor == "postgresql"`, so it can ship while production is still on MySQL.
- **Tests:** the suite runs on sqlite, a MariaDB container and a Postgres/Timescale container (`make test`,
  `test-mariadb`, `test-pg`), plus `test-cross` (both aliases) for the tools. Pin the rewritten readers to the
  **old raw SQL kept verbatim in the test**, running on MariaDB, and to a Python reference on every engine.

## The tooling (copy from EnaStats `stats/store_migration.py` + three commands)

- **`fingerprint take|diff`:** per period (month of the time column) and per small table: count, id
  min/max/sum, value sums, per-tenant counts, and a **content hash of every column of every row**.
  - Values are canonicalised so the same rows hash the same on both engines: naive datetimes are UTC, booleans
    0/1, IPs via `ipaddress`, binary as sha256.
  - Aggregates and hashes only, so the files are safe to commit as evidence.
  - `diff` ignores timing fields and takes `--closed-before` for live periods.
- **`copy --source <alias> --target <alias>`:** either direction, so it is also the rollback tool.
  - The big table goes one period per target transaction (Postgres `COPY`, ids preserved), verified by count +
    id-sum, resumable through a state file.
  - Rows the target refuses are skipped, counted and listed by id, never silently.
  - At the end, reset sequences (`connection.ops.sequence_reset_sql`).
- **API snapshot `take|diff`:** run the endpoints' functions in-process for fixed **closed** windows (pinned
  anchor date, a fixed radio/tenant list), then diff. This is the user-facing half of the proof.

## Traps the rehearsal caught (all were fixed before production)

- **Rollback deleting referenced rows.** "DELETE all, INSERT all" of `auth_user` violates MariaDB's FK from
  `django_admin_log`, which is not copied. Small tables: delete only the rows the source lacks (reverse dependency
  order), then upsert by pk (`ON CONFLICT … DO UPDATE` / `ON DUPLICATE KEY UPDATE`), in one transaction.
- **Rollback wiping history the forward copy skipped.** A partially copied table (recent logs only) must replace
  only the copied id range on the target, never the whole table. Otherwise the rollback deletes the old store's
  full history.
- **Do not copy `django_content_type`, `auth_permission`, `django_migrations`, `django_session`,
  `django_admin_log`.** `migrate` rebuilds the first three, with different ids. Sessions only force a re-login.
  The admin log points at content-type ids, so it needs a natural-key mapping if anyone wants it.
- **mysqlclient splits `executemany` into INSERTs of ≤ 64 KB** (`Cursor.max_stmt_length`), so
  `max_allowed_packet` is not a risk for the rollback direction. A test pins it.
- **A copy run killed mid-way** never reaches its `finally`. Anything it paused (the TimescaleDB compression
  policy) stays paused. Check it on every exit.

## TimescaleDB specifics

- The hypertable's PK and unique indexes must include the time column: `PRIMARY KEY (id, time)`. Django still uses
  `id`.
- **`INTERVAL '1 month'` chunks are 30-day ranges, not calendar months** (2.30 has no calendar alignment), so a
  per-month statement reads one or two chunks.
- **Compress after more than the longest window in which rows still get UPDATEd.** EnaStats compresses after 60
  days because the collector re-matches rows up to 35 days old. DML on compressed chunks works, just more slowly.
- **`CALL run_job(<compression job>)`** over years of data needs `SET statement_timeout = 0`.
- **Resource and restore mechanics:** `coolify-deploy` §5a1 (Coolify Postgres resource with the Timescale image,
  `limits_memory` sizing, `ALTER SYSTEM SET shared_preload_libraries = 'timescaledb', 'pg_stat_statements'` with
  two literals, restore with `timescaledb_pre_restore()`/`post_restore()`).
- **Expected numbers:** 133 GB uncompressed → 13 GB compressed (`segmentby` tenant). API aggregates got faster
  (72 s → 40 s for the snapshot). Reading every column of every row (a fingerprint) is ~3× slower than InnoDB.

## Step 4: the rehearsal

- **Restore the dump fast:**
  - stream it through `awk` to drop junk rows
  - create the big table with its **PK only** and add the secondary indexes afterwards in one `ALTER`
  - use a no-CoW directory on btrfs, a big buffer pool, `innodb_flush_log_at_trx_commit=0`, doublewrite off
  - EnaStats: the load took 41 min; the indexes were added afterwards in one ALTER.
- **Run long jobs with `setsid nohup … &`,** not as the agent's background task: a session restart killed the
  first copy. The state file is what made the relaunch a resume.
- **The full sequence:**
  1. fingerprint A + snapshot A
  2. copy
  3. **compress like production**
  4. fingerprint B + snapshot B, then diff
  5. re-copy the newest periods over compressed chunks (the cutover delta)
  6. copy back into the old engine (the rollback)
  7. fingerprint again
- **Delete the restored databases afterwards** (personal data). Keep the dump and the JSON evidence.

## Steps 5–7: production

- **Put the database's data on the fast disk** when Docker's root is slow: create the database resource with
  `instant_deploy: false`, then `docker volume create --driver local --opt type=none --opt o=bind --opt
  device=<fast path> <volume-name-coolify-will-use>` (chown to the image's uid) before the first start
  (`coolify-deploy` §5a2).
- **The old compose stack may already be reachable** from the new apps on the `coolify` network by service name
  (`mariadb`). That makes the `legacy` alias free.
- **Run the backfill inside the new web container,** detached. **Copy every state file and JSON out of the
  container's `/tmp` right after each step**: a redeploy replaces the container (EnaStats lost the live-month
  fingerprint files this way).
- **Fingerprint the closed periods on both sides before the pause.** During the pause only the live periods
  remain.
- **Pre-build the workers** (deploy, check one pass, stop) so the cutover only starts containers. Then the pause
  is:
  1. stop the old writers
  2. delta copy of the live periods. With a re-match window, take the window plus one period: EnaStats re-copied
     3 months.
  3. fingerprint the live periods on both sides and diff
  4. flush any new Redis that holds session state from the pre-run, verifying `DBSIZE 0`
  5. start the new workers
  6. move the domains (`force_domain_override`, re-apply `oj.*` labels, deploy)
  7. stop the old web
- **If the web reads live state from the new Redis, move the domains only after the new writers run.** Otherwise
  users see zeros.
- **Afterwards:**
  - expect one "writer stale" page during the pause
  - point the monitoring hub's scrape at the new origin
  - run an API snapshot on live production against the pre-cutover one
  - push one watched-path commit to prove `is_webhook` and blue-green under a request loop
  - verify the first nightly backup that holds the data, in the bucket listing itself
- **Keep the old database running with no writers as the rollback,** auto-deploy OFF. Write "never press
  Start/Deploy on the old resource" in DEPLOY.md and USER_TODO: a manual start resurrects the old writers, which
  means split brain.

## Reference implementation map (EnaStats repo)

| Piece | File |
|---|---|
| Plan, status, production facts | `docs/timescaledb-migration.md` |
| Commands for steps 5–7, rollback | `docs/timescaledb-cutover-runbook.md` |
| Rehearsal and cutover records + evidence | `operations_history/2026-10-04-timescaledb-rehearsal/`, `…/2026-10-05-timescaledb-cutover/` |
| Shared tool code | `stats/store_migration.py` |
| Commands | `icecast_tools/management/commands/enastats_{fingerprint,copy_stats,api_snapshot}.py` |
| Dual-engine settings | `EnaStats/settings.py` (`_database`, `legacy` alias), `settings_test_{mariadb,pg,cross}.py` |
| Dialect branches | `stats/api.py` (`EpochSecondsFloor`, `HasFractionalSecond`, `_bucket_avg`, `count_distinct_listeners`), `stats/rollup.py` (`bounded_statements`) |
| Hypertable migration | `stats/migrations/0007_timescale_hypertable.py` |
| Tests | `tests/test_store_migration.py` (cross-engine copy/rollback/fingerprint), `tests/test_api_readers.py` (old raw SQL vs ORM) |
| Restore script with deferred indexes | `operations_history/2026-10-04-timescaledb-rehearsal/README.md` (commands), `~/rehearsal/enastats/restore.sh` on minisforum |

Related skills: `coolify-deploy` (resources, §5a1 and §5a2), `django-house-setup` (the Django index),
`fleet-observability` (scrape and labels), `prod-db-sync`.
