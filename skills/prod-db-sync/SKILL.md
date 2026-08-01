---
name: prod-db-sync
description: Pull a production Postgres database from a Coolify/docker host into the local Docker Compose stack, safely. Use when the user asks to "sync the prod db", "copy the production database locally", "make sync-db-prod", "run evals/tests on latest production data", "pg_dump from the server/Coolify", or "restore prod into local docker". Covers the battle-tested script pattern (pg_dump inside the prod container over SSH, dump-completeness verification, temp-DB restore + swap), container auto-detection on multi-stack Coolify hosts, gitignored connection config, post-restore migrations, and the real-API-keys warning for synced data.
---

# Prod DB → local sync (Coolify / Docker Compose)

Pattern for a `make sync-db-prod` target backed by `backend/scripts/sync-db-prod.sh`.
Reference implementations that already follow it: `NutriLens/backend/scripts/sync-db-prod.sh`
(original) and `humans2agents/agents/accountant/backend/scripts/sync-db-prod.sh`
(adds strict container detection). Copy `sync-db-prod.template.sh` from this
skill's directory and adapt names.

## Core design (why each piece exists)

1. **`pg_dump` runs INSIDE the prod postgres container over SSH** — it uses the
   container's own `$POSTGRES_USER`/`$POSTGRES_DB`, so prod DB credentials never
   land on the laptop. Read-only against prod.
2. **gzip runs LOCALLY, not in the remote `sh -c`** — with `set -o pipefail`, a
   remote `pg_dump | gzip` always returns gzip's exit 0 and silently truncates
   the dump. Locally, `PIPESTATUS` exposes the ssh/pg_dump status. Capture
   remote stderr to a file so the pg_dump error isn't lost.
3. **Verify the dump before touching anything local**: check
   `PostgreSQL database dump complete` marker with `grep -c` — NOT `grep -q`,
   whose early exit SIGPIPEs gunzip and trips pipefail with a false "incomplete".
4. **Confirm before wiping local** (`YES=1` env var to skip). Make command-line
   vars are NOT auto-exported to recipe shells — pass explicitly:
   `@YES="$(YES)" ./scripts/sync-db-prod.sh`.
5. **Restore into `${DB}_synctmp`, then swap** (`dropdb` old + `ALTER DATABASE …
   RENAME`). A mid-restore failure (prod-only extension, bad dump) leaves the
   existing local DB untouched instead of dropped-empty. Use
   `psql -v ON_ERROR_STOP=1` so the restore actually fails on the first error.
6. **Stop app services first** (`compose stop web worker beat`) to free DB
   connections; `dropdb --force` handles stragglers.
7. **Wait for `pg_isready` with a timeout** and abort if it never comes up —
   e.g. the local volume was initialised by an older Postgres major.
8. **Run migrations after the swap** — local code is usually ahead of prod.
9. Keep dumps in a gitignored `backups/` dir with a `.latest` pointer file.

## Container auto-detection on Coolify hosts

A Coolify host runs MANY stacks: `docker ps | grep -i postgres | head -1` is a
lottery (a real host had 6 postgres containers from different projects). Two
gotchas:

- Coolify names containers `<service>-<resource_uuid>-<ts>`, so you can't
  hardcode names across redeploys.
- Compose env leaks `POSTGRES_DB` into EVERY service of the stack (web, worker,
  even redis), so checking the env var alone matches non-DB containers.

Detect by **postgres image AND the container's own `POSTGRES_DB`**, and abort
listing candidates if more than one matches:

```sh
docker ps --format "{{.Names}} {{.Image}}" | while read -r name image; do
  case "$image" in postgres*)
    db=$(docker exec "$name" printenv POSTGRES_DB 2>/dev/null) || true
    [ "$db" = "myapp" ] && echo "$name" ;;
  esac
done
```

## Connection config

Gitignored env file `backend/.envs/.prod-sync` + tracked
`.envs/.prod-sync.example` with placeholders (never hardcode the server IP in
the script or a tracked file). Gitignore needs the pair:

```gitignore
backend/.envs/*
!backend/.envs/.prod-sync.example
```

Let real env vars override the file (capture pre-set values before `source`,
restore after) so `make sync-db-prod PROD_PG_CONTAINER=x` works.

SSH flags: `-C` (wire compression), `ServerAliveInterval=30` +
`ServerAliveCountMax=120` (long dumps), and `-o BatchMode=yes -o
ConnectTimeout=10` when scripting/testing so a missing key fails fast instead
of hanging on a password prompt.

## Facts worth knowing

- **Version skew is fine downward-to-upward**: a dump from postgres 16 restores
  into a local 17 without issue. Use plain-SQL format (`pg_dump` default) +
  `--no-owner --no-privileges` for maximum portability.
- **Media on S3/B2 means DB-only sync suffices** — Django `FileField` stores
  names, not bytes; with the bucket credentials in local `.env`, files stream
  from object storage. No rsync of media volumes.
- **Warn loudly after the sync**: the local DB now contains PRODUCTION data,
  often including real third-party API keys (accounting, payment, email
  services). Read-only workflows (evals, debugging) are safe; running local
  upload/sync/merge jobs would write to the real external services.
- Do NOT use Ansible for this: single host, imperative streaming pipe,
  intentionally destructive locally — a bash script called from make matches
  Makefile-driven repos and adds no dependency.

## Makefile targets

```make
sync-db-prod: ## Pull PROD DB into local (config: .envs/.prod-sync; YES=1 skips confirm; read-only on prod, wipes local)
	@YES="$(YES)" PROD_PG_CONTAINER="$(PROD_PG_CONTAINER)" ./scripts/sync-db-prod.sh
```

(plus a root-Makefile pass-through if the repo nests, forwarding `YES` and
`PROD_PG_CONTAINER`).
