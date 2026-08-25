---
name: coolify-deploy
description: Deploy, configure and operate applications on Coolify (self-hosted PaaS) without repeating known outages. Use when creating or reviewing ANY Coolify resource (Dockerfile app, Compose stack, static site), writing a docker-compose meant for Coolify, choosing between Dockerfile and Compose resource types, wiring Coolify env vars / magic variables (SERVICE_PASSWORD_*, SERVICE_FQDN_*, SOURCE_COMMIT), setting up Persistent Storage / volumes, or when the user reports "502 Bad Gateway", "504 intermittent", "data disappeared after redeploy", "deploy takes forever / containers take 30s to stop", "unable to open database file", "env var not applying", "rolled back on first deploy", or asks "how do I deploy this to Coolify", "set up the Coolify resource", "why did the volume reset". Covers the Dockerfile-over-Compose blue-green rule, Traefik/networking traps (no ports, no custom labels, no networks: block), env var syntax + the empty-string default-wipe trap, anonymous-volume data loss + recovery, nonroot bind-mount chown, healthcheck design, PID-1 signal handling, and prod-host operating rules (no repo checkout, container-name instability, detached one-offs).
---

# Coolify deployments

Field-tested rules for deploying to Coolify. Every rule here has caused a real outage, data loss, or wasted debugging session at least once. Cross-references: Celery task-loss on deploys lives in the `celery-deploy-safety` skill; SQLite blue-green specifics in `sqlite-production`; prod DB container detection in `prod-db-sync`.

## 1. Resource type: Dockerfile first (house rule)

**Default to the "Application → Dockerfile" resource type for single-service backends — NOT Docker Compose.** If the project seems to need Compose, ask the user before choosing it.

- Dockerfile mode supports **blue-green deployments**: build new container, health-check it, swap Traefik traffic, then stop the old one. Zero downtime, automatic rollback (failed healthcheck = traffic stays on the old container).
- The Compose application buildpack does **NOT** do blue-green: it stops the running stack, then starts the new one — every deploy has a 502 window and SIGTERMs all workers.
- Pick Compose only for genuinely coupled multi-service stacks (sidecar, init container). Plausible / Grafana / Sentry / Postgres each get their **own Coolify resource**, so the app stays Dockerfile and keeps blue-green.
- Migration is asymmetric: Dockerfile → Compose later is trivial (point at the compose file, redeploy). Compose → Dockerfile means **re-creating the resource and losing its deployment history**. Start Dockerfile.
- Dockerfile-mode cost: `stop_grace_period`, restart policy, healthcheck, env defaults move to the Coolify UI or Dockerfile directives (`HEALTHCHECK`, `STOPSIGNAL`). The UI has its own "Stop Grace Period" field — that one IS honored.
- Local dev may still use Compose while prod is a Dockerfile resource — they don't have to match.
- Static Astro/SPA sites: use Coolify's **static resource** (base directory + publish `dist/`), no Dockerfile needed.

Rolling/blue-green preconditions (official): passing health check, default container names, **no host port mappings**, not available for Compose resources. Attached volumes do NOT disable it — both containers mount the volume during the overlap.

**Write-overlap hazard**: during the swap, old and new containers share the volume and both may write. For SQLite: WAL + `busy_timeout` makes it safe. Migrations must be **additive-only and idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN`; never rename/drop in the same release that stops using a column) because the old binary runs against the new schema during overlap.

**Migrate-on-boot is a blue-green feature**: run migrations at container start, before opening the listener, gated by `pg_advisory_lock(<constant>)`. A failed migration fails the boot → healthcheck never passes → traffic stays on the old container. Exactly what you want.

## 2. Networking / Traefik

- **Never add `ports:` or `expose:` for the web interface.** Coolify's Traefik routes over the internal Docker network; host port mappings interfere with routing (and disable blue-green). Set the internal port in the UI's **"Port Exposes"** field instead.
- Port-map ONLY services needing direct host access (streaming 8000, SFTP 2022). Published ports **bypass ufw** — bind to a specific IP (`"${TAILNET_IP:?}:9090:9090"`), never `0.0.0.0`.
- **Traefik labels depend on resource type:**
  - Dockerfile app / Compose application buildpack: Coolify auto-generates labels. **Custom `traefik.*` labels conflict** with the auto-generated `loadbalancer.server.port` → Bad Gateway. Remove them all.
  - Raw Compose *Resource* (service stack): Coolify does NOT generate routing labels — you must add `traefik.enable=true`, the `Host()` router rule, and `entryPoints` yourself.
- **Never define a `networks:` block** in the compose. Two networks → Traefik flips container IPs non-deterministically → intermittent 504 Gateway Timeout.
- Cross-stack: services in different resources can't resolve each other by service name. Enable **"Connect to Predefined Network"**; hostname becomes `<service>-<resource_uuid>`.
- App must listen on **0.0.0.0**, not localhost.
- **502 on a small VPS is usually missing swap, not config.** `free -m` first; add a swapfile + `vm.swappiness=10`, persist in fstab/sysctl.d.

## 3. Env vars

Compose substitution syntax (what the UI does with each):

| Syntax | Behavior |
|---|---|
| `${VAR}` | Editable in UI; deploy fails if unset |
| `${VAR:-default}` | Optional, falls back to default |
| `${VAR:?hint}` | Required; "hint" shows in UI; deploy refuses to start if cleared |
| `${VAR:?}` | Required, no hint |

Magic variables (auto-generated, persisted across deploys; needs v4.0.0-beta.411+ in compose):
`SERVICE_PASSWORD_<NAME>` (and `SERVICE_PASSWORD_64_<NAME>`), `SERVICE_USER_<NAME>`, `SERVICE_FQDN_<NAME>` (and `SERVICE_FQDN_<NAME>_<PORT>` for port routing), `SERVICE_URL_<NAME>`, `SERVICE_BASE64_<NAME>` / `_64` / `_128`.

- **Identifier gotcha**: names containing `_` can't take a port suffix — use hyphens: `SERVICE_URL_BACKEND-API_8080` works, `SERVICE_URL_BACKEND_API_8080` doesn't.
- Assigning a domain in the UI auto-sets `SERVICE_FQDN_<NAME>` in the container — don't set it manually.
- Shared vars across a stack: `{{team.X}}`, `{{project.X}}`, `{{environment.X}}`.
- `SOURCE_COMMIT` = full 40-char deployed SHA, available as a build arg only when "Include Source Commit in Build" is ON. Feed it to Sentry release / version endpoints. **Never pin a derived value like SENTRY_RELEASE in the UI env** — it freezes stale. Keep such ARGs in a **late, cheap Dockerfile layer** or every deploy busts the apt/pip cache.
- **Build vs Runtime flags**: mark everything the build doesn't need (API keys, DSNs, JWT secrets) **Runtime-only** — keeps secrets out of `/artifacts/build-time.env` and the build context. For build-time-only secrets (private package tokens), enable "Use Docker Build Secrets" + `# syntax=docker/dockerfile:1`; Coolify rewrites `RUN` with `--mount=type=secret`.
- **A var not threaded through the compose file cannot be set from the UI at all.** Audit that every runtime setting appears in the compose `environment:`.

### Auto-seeding traps (verified on Coolify Cloud, compose_parsing_version 5)

When Coolify first parses a compose file it creates UI env rows for every
referenced variable — and the seeded VALUES are traps:

- `${VAR:?hint}` → the row is created **with the hint text as its literal
  value** ("where alerts go, e.g. …" became the actual alert recipient).
  The `:?` guard then passes with garbage. Audit every `:?` var after the
  first parse.
- `${VAR}` / `${VAR:?}` → seeded as **empty string** (fails `:?`, silently
  satisfies a bare `${VAR}`).
- `${VAR:-default}` → the default is seeded as the value — **including any
  nested `${OTHER}` unexpanded**, and compose does NOT re-interpolate env
  values, so `GRAFANA_ROOT_URL=http://${TAILNET_IP}:3000` ships literally.
  Avoid nested variables in defaults, or overwrite the seeded value.
- **Magic vars referenced only in a top-level `secrets:` block are NOT
  auto-generated** — the scanner reads service `environment:`, not
  `secrets.*.environment`. A `SERVICE_PASSWORD_X` used solely as a secret
  source must be created by hand (UI or API).
- **Compose-buildpack interpolation runs against `/artifacts/build-time.env`**
  (`docker compose --env-file …`). Any var used in `${...}` interpolation —
  port binds, image tags, secret sources — must be **buildtime**; a
  runtime-only var is invisible to interpolation and fails the deploy with
  "required variable X is missing a value".

### The empty-string trap (bites every Django project)

**Coolify injects declared-but-unset vars as empty strings**, and `python-decouple` / `django-environ` `default=` only applies when the var is **absent**, not empty. This silently wipes `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, Sentry env, S3 config. Same trap from the compose side: `${VAR:-}` sets an empty string. Defenses:

```python
# `or` falls through on empty string; config default alone does not
FRONTEND_URL = config("FRONTEND_URL", default="") or "https://app.example.com"
# or: always-present required hosts merged with env-provided extras, deduped
ALLOWED_HOSTS = list(dict.fromkeys(REQUIRED_HOSTS + env_hosts))
```

## 4. Persistent storage — the data-loss chapter

**Rule zero: every path that must survive a redeploy needs an explicit Persistent Storage entry in the Coolify UI.** A Dockerfile `VOLUME ["/data"]` does NOT save you — Docker creates a fresh **anonymous** volume (64-char hash name) on every container create; the old one orphans and the app boots empty.

Diagnose:
```bash
docker inspect $CID --format '{{json .Mounts}}'
# Name = 64-char hash → anonymous (BROKEN). Human-readable name → OK.
```

Fix: Storage tab → Add Persistent Storage → Name (Coolify prepends the resource UUID → stable `name-<uuid>` volume) → Source Path blank (named volume) or a host path (bind mount) → Destination Path → redeploy.

Recover lost data (Coolify never deletes orphans):
```bash
for v in $(docker volume ls -q --filter dangling=true); do
  f="/var/lib/docker/volumes/$v/_data/app.db"
  [ -f "$f" ] && stat -c "%y  %s bytes  $v" "$f"
done | sort
docker stop <container>
cp -a /var/lib/docker/volumes/<orphan>/_data/. /var/lib/docker/volumes/<named>/_data/
docker start <container>
```

Other silent-loss mechanisms: renaming the volume or changing its destination path (treated as new, old orphans); switching resource type (volume linkage is per-resource); pointing the app's data path outside the mount. After a major Coolify upgrade, verify `docker volume inspect` shows an unchanged `CreatedAt` across deploys.

Named volume vs bind mount: named survives redeploys but orphans on resource deletion and is awkward to reach from the host; bind mount survives everything, is directly inspectable, and lets backups live on a different disk than the data.

**Volume names (`<name>-<resource_uuid>`) are stable across redeploys and safe to reference in backup tooling; container names are NOT** (timestamp suffix changes every deploy).

### Relative bind mounts (config files from the repo) need Preserve Repository

The compose buildpack **rewrites every relative `./path` bind to
`/data/coolify/applications/<uuid>/path`** (absolute paths pass through
untouched) — and by default the repo is NOT there: the clone lives in a
transient `/artifacts/<deploy-uuid>` dir. Docker then creates the source as
an empty **directory**, and a file mount fails with `OCI runtime create
failed: … not a directory` (or the service starts with an empty config dir,
which is worse: silent).

Fix: enable **Preserve Repository During Deployment**
(`settings.is_preserve_repository_enabled`, PATCHable via API) — Coolify then
copies the cloned repo into `/data/coolify/applications/<uuid>/` on every
deploy, so the rewritten paths land on real files. Required for ANY compose
that bind-mounts configs out of the repo (`./prometheus/prometheus.yml:…`).
Verified live 2026-08-25 on the hq-monitoring stack.

### Nonroot images + bind mounts = first-deploy failure

Coolify creates a bind-mount host dir as `root:root`. A nonroot container (distroless `:nonroot` = uid 65532) can't write → SQLite `unable to open database file (14)` → healthcheck fails → every deploy "rolls back" (that message prints even on a first deploy with no old container). Fixes:

- Bind mount: immediately `chown -R <uid>:<uid> <host-dir>` on the server (UI → Server → Terminal). Verify with the actual image: `docker run --rm -v /srv/app/data:/data <image> <db-touching-subcommand>`.
- Named volume: Docker copies ownership from the image dir on first init — `RUN mkdir -p /data && chown 65532:65532 /data` in the Dockerfile.
- Restored-by-hand DB files need the same chown or SQLite fails identically.
- Multi-service stacks: zero-manual-prep via an `init-perms` service — `user: "0:0"`, chowns each data dir to the uid **read from the pinned image** (Prometheus 65534, Loki 10001, Grafana 472 — never guess), `touch /tmp/perms-ok && exec sleep infinity`, healthcheck on the marker file, data services `depends_on: condition: service_healthy`. It must `sleep infinity`, not exit: **Coolify counts exited containers against stack health**, and `exclude_from_hc: true` (Coolify extension) breaks local `docker compose config` validation.

## 5. Healthchecks

- Distroless/minimal images have no curl/wget: bake a `HEALTHCHECK` that execs the app's own binary (`/app healthcheck` hitting `/healthz`). Coolify's "healthcheck needs curl/wget" warning is noise then. **Re-verify the healthcheck binary exists on every image bump** — a check calling a missing binary fails the container forever.
- Depth is a trade-off, state it: shallow `/healthz` keeps blue-green from failing on a transiently-unreachable external DB; a DB-touching check is right when the app is useless without its DB and you want the deploy gate to catch bad DB config.
- **Exempt `/healthz` from any auth** you add, or both the blue-green gate and Docker HEALTHCHECK break.
- Celery: never `celery -A config inspect ping` as a healthcheck (boots all of Django, ~265 MB + 100% CPU, thousands of times/day). Use `grep -q celery /proc/1/cmdline` (requires `exec` so celery is PID 1), or for threads-pool wedge detection the Django-free broker-only form: `celery -b $REDIS_URL inspect ping -d celery@$(hostname)`.
- UI healthcheck for Dockerfile resources: GET /healthz, expected 200, initial delay 10–15 s (5 s causes false Bad Gateway right after deploy), interval 30 s, retries 3.

## 6. Deploy speed and signal handling

- **Compose buildpack stops containers sequentially with `docker stop -t 30` and IGNORES `stop_grace_period`** (upstream coolify#5975). Still set `stop_grace_period` (honored elsewhere), but the real lever is making SIGTERM work:
  - `command: sh -c "exec python …"` — the `exec` is mandatory; a bare shell as PID 1 swallows SIGTERM (30 s timeout every stop). Entrypoint scripts end with `exec "$@"`.
  - `init: true` on Python services running plain loops — PID 1 ignores signals without an explicit handler, so `while True: time.sleep()` management commands never die; tini fixes it. (gunicorn/celery register handlers, they're fine.)
- Dockerfile resources: set the UI "Stop Grace Period" field (that one applies).
- **Coolify ≥ v4.0.0-beta.450 for Docker layer caching** — older versions injected per-build args that busted the cache every deploy.
- Coolify reports "deployed" when containers **start**, not when healthy — do collectstatic at build time, keep the entrypoint fast, tune `start_period`.
- Big Compose stacks: split into a `web` resource and a `workers` resource so web deploys don't cycle every worker container.
- Base Directory vs Dockerfile Location are separate fields: the **build context must contain everything the Dockerfile COPYs** (migrations dir, sibling frontend/). A too-narrow base dir often still builds — with the COPY silently empty. Huge image → check the repo-root `.dockerignore`.

## 7. Operating the prod host

- **Coolify keeps NO repo checkout on the server** — the clone is discarded after build. One-off commands needing repo files: `scp` to host, then `docker cp` into the container. Never write runbooks assuming `$REPO` exists on prod.
- **Never hardcode container names** (suffix changes every deploy): `WEB=$(docker ps --filter "name=web" --format "{{.Names}}" | head -1)`. On multi-stack hosts, filter by the resource UUID embedded in the name, and for DBs match image AND the container's own `POSTGRES_DB` via `docker inspect` (env leaks into every service of a stack; a host had 6 postgres containers — see `prod-db-sync`).
- Nonroot app containers: `docker cp` in works (root), but the app can only write to `/tmp` — point command output there, `docker cp` it out **before the next redeploy** (copied-in files die with the container).
- Long one-offs: `docker exec -d "$WEB" sh -c "cmd > /tmp/x.log 2>&1"` — an exec tied to your SSH session dies with it. Bound batches (≤1000), babysit the first minutes with `docker stats`.
- Every Coolify VPS gets swap (+ optionally zswap via tmpfiles.d/modules-load.d, no GRUB edits) and `vm.swappiness=10`.
- Per-service log rotation in the compose (`json-file`, `max-size: 10m`, `max-file: 3`) — on a Coolify-owned host no daemon-level cap exists unless you set one.
- `coolify-sentinel` eating CPU on a busy host can be throttled/disabled in Coolify settings.
- Prod commands not matching the repo = stale deploy or a **UI command override** on the resource — check there before debugging code.
- After changing env vars in the UI, you must **redeploy** for them to apply.

## 7b. Coolify Cloud API (debugging deploys without the UI)

Base `https://app.coolify.io/api/v1`, `Authorization: Bearer <token>`.
**Cloudflare fronts it and 403s (error 1010) default tool UAs** — python
urllib/httpx must send a real browser User-Agent (same finding as
api.resend.com; curl's default UA happens to pass).

- `GET /applications/{uuid}` — resource + its **server** object, including
  `validation_logs` (connection errors) and `ip_previous`.
- `GET /deployments/applications/{uuid}` — deployment history; `logs` is a
  JSON array of `{command, output}` steps, including the real compose error.
- `GET/POST/PATCH /applications/{uuid}/envs` — PATCH updates by `key`
  (`{key, value, is_buildtime, is_literal}`); GET returns each var TWICE
  (production + preview rows) — not a bug, dedupe by key.
- `POST /deploy?uuid={app}` — trigger a deploy (GET returns 405).
- **`is_literal: true` single-quotes the stored value**: `real_value` comes
  back WITH the quotes (`'fcU…y'`), but compose's `.env` parsing strips them,
  so the container sees the inner value. Anything reading `real_value`
  (scripts, copy-paste from the UI) must strip the quotes or auth fails with
  the "same" password.
- App settings like `is_preserve_repository_enabled` PATCH directly on
  `/applications/{uuid}` even though GET nests them under `settings`.
- The server's `ip` field must resolve **from Coolify Cloud** (public DNS).
  Setting a not-yet-published hostname breaks the connection ("dial tcp:
  lookup … no such host"), blocks all deploys, and flips the server
  unreachable; `ip_previous` keeps the old value. Create the DNS record
  first, then change the field.

## 8. Failure → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| 502 after deploy | No swap, OOM during build | `free -m`; add swapfile, persist |
| 502, no OOM in dmesg | Custom traefik.* labels conflict | Remove all custom labels |
| 504 intermittent | Container on two networks | Delete the `networks:` block |
| Bad Gateway right after deploy | Healthcheck initial delay too short | 10–15 s delay |
| Restart loop | Startup panic, usually missing env var | Logs; make config errors name the var |
| Data gone after redeploy | Anonymous volume (no Persistent Storage entry) | Section 4; data is recoverable from orphans |
| "unable to open database file" / first deploy "rolls back" | root-owned bind-mount dir vs nonroot uid | chown host dir, or named volume + Dockerfile chown |
| 30 s to stop every container | Shell-as-PID-1 / no SIGTERM handler | `exec`, `init: true` |
| Env var change has no effect | Not redeployed, or var not threaded through compose | Redeploy; declare it in `environment:` |
| Fresh deploy: DB "uninitialized and password option is not specified" | MariaDB/MySQL service without a root password setting | `MARIADB_RANDOM_ROOT_PASSWORD=yes` — invisible until the volume is empty (disaster recovery) |
| Deploys on a tunnel-connected server fail intermittently, exit 255 mid-command (`mkdir -p` "fails" with no output) | SSH transport drop: cloudflared on QUIC over DEGRADED UDP (strict egress fw, netcup UDP filtering) — connects, then drops mid-transfer | Force `TUNNEL_TRANSPORT_PROTOCOL=http2` (TCP) on the connector; retry the deploy meanwhile — the failure is transient |

## 9. Secrets, domains, scheduling

- Secrets: every credential is a Coolify magic var or UI env var — never committed, not even encrypted, in repos Coolify pulls. Strictest pattern: compose `secrets:` sourced from env so containers read `/run/secrets/*` files (`__FILE` vars) instead of container env (docker inspect exposes `Config.Env`; needs compose ≥ 2.23.1). Private repos deploy via Coolify's read-only deploy key.
- DNS: create records **grey-cloud/DNS-only first** so Traefik completes the Let's Encrypt HTTP-01 challenge; enable the Cloudflare proxy per-record afterwards. **Add domains, don't replace** — keep the default `<uuid>.<ip>.sslip.io` FQDN alongside custom domains (links already shipped). Behind Traefik, Django needs `SECURE_PROXY_SSL_HEADER` (trust `X-Forwarded-Proto`), `SECURE_SSL_REDIRECT = False`, and `CSRF_TRUSTED_ORIGINS`.
- Scheduling: Coolify has per-resource **scheduled tasks** (good for periodic management commands) and UI-configured DB backups with retention/S3. In-container cron without Celery = **supercronic**, never crond. With Celery, celery-beat — and apply the `celery-deploy-safety` skill in full, plus the sizing rules (`--concurrency=2`, gunicorn max-requests, no Flower in prod).
