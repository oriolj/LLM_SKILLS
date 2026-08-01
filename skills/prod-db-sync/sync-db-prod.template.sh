#!/usr/bin/env bash
# Sync a production Postgres DB into the local Docker Postgres.
#
# SSHes to the Coolify host, runs pg_dump *inside* the prod postgres container
# (so it uses the container's own $POSTGRES_USER/$POSTGRES_DB and we never put
# prod DB credentials on this machine), streams a gzipped plain-SQL dump back,
# then restores into a temp DB and swaps it into place. Invoice PDFs live in
# Backblaze B2, not the DB, so the dump stays small and `eval_model` can read
# them directly with B2_* creds in .env .
#
# Connection details come from backend/.envs/.prod-sync (gitignored); copy
# .envs/.prod-sync.example to start.
#
# Usage:
#   make sync-db-prod              # dump prod + restore into local (asks before wiping)
#   make sync-db-prod YES=1        # skip the confirmation prompt
#   make sync-db-prod PROD_PG_CONTAINER=...   # override any .prod-sync value
set -euo pipefail

# backend/ — this script lives in backend/scripts/
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

cyan()  { echo -e "\033[36m$*\033[0m" >&2; }
green() { echo -e "\033[32m$*\033[0m" >&2; }
yellow(){ echo -e "\033[33m$*\033[0m" >&2; }
red()   { echo -e "\033[31m$*\033[0m" >&2; }

ENV_FILE=".envs/.prod-sync"
if [[ ! -f "$ENV_FILE" ]]; then
  red "Missing $ENV_FILE — copy .envs/.prod-sync.example to .envs/.prod-sync and fill it in."
  exit 1
fi
# Load the env file, but let real env vars (e.g. make sync-db-prod PROD_SSH_HOST=...)
# win by capturing pre-set values and restoring them after the source.
_pre_host="${PROD_SSH_HOST:-}"; _pre_user="${PROD_SSH_USER:-}"
_pre_port="${PROD_SSH_PORT:-}"; _pre_cont="${PROD_PG_CONTAINER:-}"
set -a; source "$ENV_FILE"; set +a
[[ -n "$_pre_host" ]] && PROD_SSH_HOST="$_pre_host"
[[ -n "$_pre_user" ]] && PROD_SSH_USER="$_pre_user"
[[ -n "$_pre_port" ]] && PROD_SSH_PORT="$_pre_port"
[[ -n "$_pre_cont" ]] && PROD_PG_CONTAINER="$_pre_cont"

: "${PROD_SSH_HOST:?Set PROD_SSH_HOST in $ENV_FILE}"
PROD_SSH_USER="${PROD_SSH_USER:-root}"
PROD_SSH_PORT="${PROD_SSH_PORT:-22}"
PROD_PG_CONTAINER="${PROD_PG_CONTAINER:-}"
PROD_DB_NAME="${PROD_DB_NAME:-invoices}"
BACKUPS_DIR="${BACKUPS_DIR:-backups}"
COMPOSE="docker compose -f docker-compose.local.yml"
LDB="invoices"  # local POSTGRES_DB (docker-compose.local.yml)

SSH="ssh -C -o ServerAliveInterval=30 -o ServerAliveCountMax=120 -p ${PROD_SSH_PORT} ${PROD_SSH_USER}@${PROD_SSH_HOST}"

# ── locate the prod postgres container ───────────────────────────────────────
# The Coolify host runs several stacks (and POSTGRES_DB leaks into every
# service of ours via compose env), so match BOTH the postgres image AND the
# container's own POSTGRES_DB — a bare `grep -i postgres | head -1` would be
# a lottery here.
if [[ -z "$PROD_PG_CONTAINER" ]]; then
  cyan "Locating postgres container for POSTGRES_DB=${PROD_DB_NAME} on ${PROD_SSH_HOST}…"
  PROD_PG_CONTAINER=$($SSH '
    docker ps --format "{{.Names}} {{.Image}}" | while read -r name image; do
      case "$image" in
        postgres*)
          db=$(docker exec "$name" printenv POSTGRES_DB 2>/dev/null) || true
          [ "$db" = "'"$PROD_DB_NAME"'" ] && echo "$name"
          ;;
      esac
    done
    exit 0')
fi
if [[ -z "$PROD_PG_CONTAINER" ]]; then
  red "Could not find a postgres container with POSTGRES_DB=${PROD_DB_NAME} on prod."
  red "Set PROD_PG_CONTAINER in $ENV_FILE."
  exit 1
fi
if [[ $(echo "$PROD_PG_CONTAINER" | wc -l) -gt 1 ]]; then
  red "Multiple candidate containers — set PROD_PG_CONTAINER in $ENV_FILE:"
  red "$PROD_PG_CONTAINER"
  exit 1
fi
cyan "Prod container: $PROD_PG_CONTAINER"

# ── dump ─────────────────────────────────────────────────────────────────────
mkdir -p "$BACKUPS_DIR"
ts=$(date +%Y%m%d-%H%M%S)
out="${BACKUPS_DIR}/prod-${ts}.sql.gz"
err_log="${out}.stderr"

cyan "Dumping ${PROD_PG_CONTAINER} → ${out}…"
# gzip runs locally (not inside the remote `sh -c`) so the outer `set -o pipefail`
# actually catches a pg_dump failure — a remote `pg_dump | gzip` would always
# return gzip's exit 0 and silently truncate the dump. Remote stderr is captured
# so a pg_dump error isn't lost even if the pipeline still exits 0.
set +e
$SSH "docker exec -i ${PROD_PG_CONTAINER} sh -c 'pg_dump --no-owner --no-privileges -U \$POSTGRES_USER -d \$POSTGRES_DB'" \
  2>"$err_log" | gzip -6 > "$out"
pipestatus=("${PIPESTATUS[@]}")
set -e
ssh_status=${pipestatus[0]:-0}
gzip_status=${pipestatus[1]:-0}

# pg_dump always emits this marker at the end of a complete run. Use `grep -c`
# (reads to EOF), NOT `grep -q` — grep -q's early exit would SIGPIPE gunzip and
# trip pipefail even when the marker is present, giving a false "incomplete".
marker=$(gunzip -c "$out" 2>/dev/null | grep -c "PostgreSQL database dump complete" || true)
if [[ $ssh_status -ne 0 || $gzip_status -ne 0 || $marker -eq 0 ]]; then
  red "✗ Dump is incomplete (ssh=$ssh_status gzip=$gzip_status marker=$marker) — NOT restoring."
  red "  --- last 30 lines of remote stderr ($err_log) ---"
  tail -n 30 "$err_log" >&2 || true
  red "  Keeping $out + $err_log for inspection."
  exit 1
fi
rm -f "$err_log"
echo "$out" > "${BACKUPS_DIR}/.latest"
green "✓ Dumped $out ($(du -h "$out" | cut -f1))"

# ── confirm before wiping local ──────────────────────────────────────────────
if [[ "${YES:-}" != "1" ]]; then
  yellow "⚠  This WIPES the local database and replaces it with production data."
  printf "Continue? [y/N] " >&2; read -r ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { red "Aborted (dump kept at $out)."; exit 1; }
fi

# ── restore into local ───────────────────────────────────────────────────────
cyan "Ensuring local postgres is up…"
$COMPOSE up -d db >/dev/null
ready=""
for _ in $(seq 1 30); do
  if $COMPOSE exec -T db sh -c 'pg_isready -U "$POSTGRES_USER"' >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
# Don't fall through to the destructive restore if postgres never came up — e.g.
# the local data volume was initialised by an older Postgres major and this
# image can't start on it (drop the volume and retry).
if [[ -z "$ready" ]]; then
  red "✗ Local postgres did not become ready in 30s — aborting before touching any data."
  exit 1
fi

cyan "Stopping app services to free DB connections…"
$COMPOSE stop web worker beat >/dev/null 2>&1 || true

# Restore into a temporary database first and only swap it into place once the
# restore fully succeeds. A mid-restore failure (a prod-only extension, a bad
# dump) then leaves the existing local DB untouched instead of dropped-empty.
cyan "Restoring into a temporary database (${LDB}_synctmp)…"
$COMPOSE exec -T db sh -c \
  'dropdb --if-exists --force -U "$POSTGRES_USER" "${POSTGRES_DB}_synctmp" && createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "${POSTGRES_DB}_synctmp"'

# ON_ERROR_STOP=1 fails the restore on the first real error. `if !` keeps `set -e`
# from aborting before we can clean up the temp DB and report.
if ! gunzip -c "$out" | $COMPOSE exec -T db sh -c 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "${POSTGRES_DB}_synctmp"' >/dev/null; then
  red "✗ Restore failed — your existing local DB '$LDB' is untouched."
  red "  Dump kept at $out for inspection; dropping the partial temp copy."
  $COMPOSE exec -T db sh -c 'dropdb --if-exists --force -U "$POSTGRES_USER" "${POSTGRES_DB}_synctmp"' >/dev/null 2>&1 || true
  exit 1
fi

cyan "Swapping the restored copy into place…"
$COMPOSE exec -T db sh -c \
  'dropdb --if-exists --force -U "$POSTGRES_USER" "$POSTGRES_DB" && psql -q -U "$POSTGRES_USER" -d postgres -c "ALTER DATABASE ${POSTGRES_DB}_synctmp RENAME TO ${POSTGRES_DB};"'

# ── bring schema up to the local code's migration level ──────────────────────
cyan "Running migrations (local code may be ahead of prod)…"
$COMPOSE run --rm -T web python manage.py migrate --no-input >/dev/null

green "✓ Local DB now mirrors production."
yellow "  App services were stopped — run 'make start' (or 'make start-d') to bring them back."
yellow "⚠  The local DB now contains PRODUCTION data, including real Holded/Quipu"
yellow "   API keys. Evals only READ from Holded, but 'make upload', collectors or"
yellow "   contact-merge run locally would write to real accounting platforms."
yellow "   Invoice PDFs stream from Backblaze B2 (needs B2_* creds in .env)."
yellow ""
yellow "   Next: make eval-model MODEL=openai/gpt-5.6-luna ARGS=\"--months 1\""
