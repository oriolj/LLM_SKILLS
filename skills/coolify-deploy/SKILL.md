---
name: coolify-deploy
description: Deploy, configure and operate applications on Coolify (self-hosted PaaS) without repeating known outages. Use when creating or reviewing ANY Coolify resource (Dockerfile app, Compose stack, static site), writing a docker-compose meant for Coolify, choosing between Dockerfile and Compose resource types, wiring Coolify env vars / magic variables (SERVICE_PASSWORD_*, SERVICE_FQDN_*, SOURCE_COMMIT), setting up Persistent Storage / volumes, or when the user reports "502 Bad Gateway", "504 intermittent", "data disappeared after redeploy", "deploy takes forever / containers take 30s to stop", "unable to open database file", "env var not applying", "rolled back on first deploy", "deploy does nothing / already queued for this commit", "the app is stuck on an old commit", or asks "how do I deploy this to Coolify", "set up the Coolify resource", "why did the volume reset". Covers the Dockerfile-over-Compose blue-green rule, Traefik/networking traps (no ports, no custom labels, no networks: block), env var syntax + the empty-string default-wipe trap, anonymous-volume data loss + recovery, nonroot bind-mount chown, healthcheck design, PID-1 signal handling, and prod-host operating rules (no repo checkout, container-name instability, detached one-offs).
---

# Coolify deployments

Field-tested rules for deploying to Coolify. Every rule here has caused a real outage, data loss, or wasted debugging session at least once. Cross-references: Celery task-loss on deploys lives in the `celery-deploy-safety` skill; SQLite blue-green specifics in `sqlite-production`; prod DB container detection in `prod-db-sync`.

## 0. Which Coolify account? Scope first (house rule, 2026-08-28)

**Coolify accounts are per scope, and so are their tokens, deploy keys and
GitHub Apps.** Before any write (`POST /servers`, `POST /projects`,
`POST /applications/*`), establish the scope of the server AND the app
from hq `docs/projects.md` / `docs/servers/` and use that scope's account:

| Scope | Coolify account | API token | Deploy key file (shared/ansible) |
|---|---|---|---|
| enantena / enacast | Enantena's Coolify Cloud team | `homelab/secrets/coolify.env` (`COOLIFY_API_TOKEN`) | `coolify/coolify-enantena.pub` |
| oriolj (personal) | Oriol's personal Coolify (manages jluv-apps-1) | `homelab/secrets/coolify-oriolj.env` (`COOLIFY_ORIOLJ_API_TOKEN`, `COOLIFY_ORIOLJ_API_URL` if self-hosted) — to be created | `coolify/coolify-oriolj.pub` — to be created |
| smartupsoft | its own | not in hq yet | — |

- A personal server or a personal project **never** goes into the Enantena
  team, and vice-versa. The token at hand is not the token to use.
- If the scope's credentials are not in `homelab/secrets/`, **stop and add
  the ask to the project's `USER_TODO.md`** — do not "just use" another
  scope's account to make progress.
- Read-only `GET`s against any account, to learn what exists, are fine.
- The GitHub Apps in §1c (`coolify-enacast`, `coolify-enantena-3`,
  `coolify-ena-oriolj`) are all installed in the **Enantena** team; a
  personal-account deploy needs the App installed there too.
- Personal team facts (2026-08-28): server `oriolj-apps-1` (= hq
  jluv-apps-1) `fso0kwogs0k4ggog4k8ccwkg` and `oriolj-nc-1`
  `q2xtgyscjn56fja6zsz0xkqg`; Coolify key `coolify-jluv`
  `m08wosks0ko88kockoc88gw8` (deployed to personal boxes as
  `coolify-oriolj.pub`); GitHub Apps `oriolj-coolify` (personal repos,
  `bogg84o0g0ow4swk8048s0ww`) and `jluv-smallbets-gh-coolify`.
- Near-miss that wrote this rule: 2026-08-28, oriolj-nc-1 (personal netcup
  box) was one `POST /servers` away from the Enantena team because that was
  the only token hq held, and the ansible baseline had already put
  Enantena's Coolify key on it (fixed: per-scope keys).

## 1. Resource type: Dockerfile first (house rule)

**Default to the "Application → Dockerfile" resource type for single-service backends — NOT Docker Compose.** If the project seems to need Compose, ask the user before choosing it.

- Dockerfile mode supports **blue-green deployments**: build new container, health-check it, swap Traefik traffic, then stop the old one. Zero downtime, automatic rollback (failed healthcheck = traffic stays on the old container).
- The Compose application buildpack does **NOT** do blue-green: it stops the running stack, then starts the new one — every deploy has a 502 window and SIGTERMs all workers.
- Pick Compose only for genuinely coupled multi-service stacks (sidecar, init container). Plausible / Grafana / Sentry / Postgres each get their **own Coolify resource**, so the app stays Dockerfile and keeps blue-green.
- Migration is asymmetric: Dockerfile → Compose later is trivial (point at the compose file, redeploy). Compose → Dockerfile means **re-creating the resource and losing its deployment history**. Start Dockerfile.
- Dockerfile-mode cost: `stop_grace_period`, restart policy, healthcheck, env defaults move to the Coolify UI or Dockerfile directives (`HEALTHCHECK`, `STOPSIGNAL`). The UI has its own "Stop Grace Period" field — that one IS honored.
- Local dev may still use Compose while prod is a Dockerfile resource — they don't have to match.
- **Static Astro/SPA/docs sites do NOT go on Coolify at all** — they go to **Cloudflare Pages** (`cloudflare-deploy` skill; house rule, Oriol 2026-08-28, superseding the earlier "Coolify static resource" advice). Coolify is for things that run a process: backends, workers, databases, exporters.

Rolling/blue-green preconditions (official): passing health check, default container names, **no host port mappings**, not available for Compose resources. Attached volumes do NOT disable it — both containers mount the volume during the overlap.

**Write-overlap hazard**: during the swap, old and new containers share the volume and both may write. For SQLite: WAL + `busy_timeout` makes it safe. Migrations must be **additive-only and idempotent** (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN`; never rename/drop in the same release that stops using a column) because the old binary runs against the new schema during overlap.

**Migrate-on-boot is a blue-green feature**: run migrations at container start, before opening the listener, gated by `pg_advisory_lock(<constant>)`. A failed migration fails the boot → healthcheck never passes → traffic stays on the old container. Exactly what you want.

## 1b. Push-to-deploy is mandatory (house rule)

**Every Coolify app gets working push-to-deploy at creation time — verify it, never assume it.** `git push` deploying is the contract; "click Deploy in the UI" is never an acceptable steady state (Oriol, 2026-08-25, after enachat shipped days of pushes nobody deployed).

- **Default source for every NEW app: the GitHub App** (§1c) — push-to-deploy comes wired, no manual webhook, PR previews. Deploy keys are the fallback, not the default.
- GitHub-App-sourced apps have it out of the box. **Deploy-key apps do NOT** — wire the per-app repo webhook the moment the app is created (mechanics + diagnostics in §5c item 7: `manual_webhook_secret_github`, one webhook per app, the `/hooks/<id>/tests` synthetic-push trigger).
- **Acceptance test before calling the setup done**: push (or fire the hook's `/tests` endpoint) and confirm a deployment row with `is_webhook: true` appears in `GET /deployments/applications/{uuid}`.

## 1c. Source the app from the GitHub App, not a deploy key (house rule, 2026-08-28)

Coolify can pull a private repo two ways. They are not equivalent, and the
difference is the whole push-to-deploy story:

| | GitHub App source | Deploy-key source |
|---|---|---|
| Push-to-deploy | wired automatically by Coolify | **you** register a repo webhook per app, by hand (§5c item 7) |
| Repo/branch pickers in the UI | yes | no (paste the ssh URL) |
| PR preview deployments | yes | no |
| Per-app secret to manage | none | `manual_webhook_secret_github` |
| Fully headless creation | needs the App installed once on the org (interactive) | yes |

**Rule: new apps are sourced from the GitHub App.** Deploy keys only for a
repo where installing the App is undesirable, or for a truly headless
onboarding — and then you own the webhook wiring at creation time.

Creation is one API call, same fields as the deploy-key variant except the
source: `POST /applications/private-github-app` with `github_app_uuid`
instead of `private_key_uuid`. Find the App first:

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "User-Agent: $UA" "$API/github-apps"
# -> uuid, name, organization, installation_id per registered App.
# Estate (2026-08-28): coolify-enacast (EnaCast org, all repos),
#   coolify-enantena-3 (Enantena), coolify-ena-oriolj (personal).
curl -s ... "$API/github-apps/<uuid>/repositories"            # what it can see
curl -s ... "$API/github-apps/<uuid>/repositories/<owner>/<repo>/branches"
```

Then:

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "User-Agent: $UA" \
  -H "Content-Type: application/json" "$API/applications/private-github-app" -d '{
  "project_uuid": "...", "server_uuid": "...", "environment_name": "production",
  "environment_uuid": "...", "github_app_uuid": "<from /github-apps>",
  "git_repository": "EnaCast/enasuite", "git_branch": "master",
  "build_pack": "dockerfile", "base_directory": "/enainbox",
  "dockerfile_location": "/backend/Dockerfile",
  "ports_exposes": "8000", "instant_deploy": false,
  "is_auto_deploy_enabled": true, "include_source_commit_in_build": true
}'
```

Note `git_repository` is `owner/repo` for the App variant, not the ssh URL.

### Migrating an existing deploy-key app to the App (done live, EnaChat, 2026-08-28)

**It cannot be switched in place.** The OpenAPI spec lists `github_app_uuid`
on `PATCH /applications/{uuid}`, but the validator rejects it:
`{"errors":{"github_app_uuid":["This field is not allowed."]}}`. The spec
lies here — a migration is **recreate + cut over**. Done for EnaChat's web
and worker with **zero failed requests** (30/30 `200` per host during and
after the swap). The playbook, every step verified:

1. **Capture the old resource** — `GET /applications/{uuid}` (build
   settings, `custom_labels`), `GET …/envs` (values + `is_literal` +
   `is_buildtime` flags) **and `GET …/storages`**. Note `environment_uuid`
   (`GET /projects/{uuid}` → `environments[]`) and `destination_uuid`
   (`.destination.uuid` on the app JSON).
   ⚠️ **Storages do not travel with a recreate, and nothing warns you.**
   The EnaChat migration forgot them: the new containers came up healthy,
   every check passed, and the client's uploaded PDFs 404'd for ~45 min
   until a sibling agent noticed `GET …/storages` was empty. Host-path
   binds survive on disk (the old resource's `delete_volumes=true` does
   not touch a host dir), named volumes do NOT — copy them first. Re-add
   with `POST /applications/{new}/storages {"type":"persistent","name":…,
   "host_path":…,"mount_path":…}` BEFORE the first deploy, and make
   "`docker inspect … Mounts` on the new container" part of the cutover
   check, not an afterthought.
2. **Create the new one** with `POST /applications/private-github-app`
   (`github_app_uuid`, `git_repository: "owner/repo"`, same
   `base_directory` / `dockerfile_location` / `ports_exposes`,
   `instant_deploy: false`, `include_source_commit_in_build: true`,
   `stop_grace_period`). Use a temporary name (`<name>-gh`) — names are
   unique; rename after the old one is deleted.
3. **Strip the auto-assigned sslip domain** immediately
   (`PATCH domains: ""`) — a worker must have none, and the web gets its
   real domains at cutover, not now.
4. **Copy envs with `PATCH …/envs/bulk`.** Two traps:
   - **bulk creates every row with `is_buildtime: true`** (secrets into
     build args). `is_buildtime` is NOT in the spec but IS accepted on the
     single and bulk PATCH — send `is_buildtime: false` explicitly, and
     re-send the original `is_literal` (a single PATCH resets it to false).
   - Coolify mirrors each row as a preview row; 18 vars read back as 36.
5. **`custom_labels` is dropped on create** — PATCH it afterwards. Send
   ONLY your own labels (`oj.*`); the Traefik/Caddy labels are generated
   by Coolify from the domains.
6. **First build of the new app with no domains** (`POST /deploy`) so it
   is healthy before any traffic can reach it. For a web app, test it
   directly on the container IP with `Host:` headers per domain.
7. **Cutover**: `PATCH domains: "<full list>", force_domain_override:
   true` on the NEW app. Without the flag Coolify refuses: "Domain
   conflicts detected … already in use by application '<old>'". The
   overlap is deliberate and safe when both run the same commit —
   Traefik round-robins across them for a few seconds.
   - **Regenerating the domains OVERWRITES `custom_labels`** with the
     generated Traefik+Caddy block and **wipes your `oj.*` lines**. Read
     it back, append your labels to the generated block, PATCH it back.
   - The API returns `custom_labels` **either base64 or plain text** —
     decode defensively (try b64, fall back to raw).
   - Redeploy the new app with `&force=true` so its container carries the
     routers (labels apply at container creation). Verify on the host:
     `docker inspect <c> --format '{{json .Config.Labels}}'` — 4 https
     routers + your labels.
   - **TLS needs no reissue**: Traefik's `acme.json` stores certs by host,
     so the moved hosts keep their certificates. `ssl_verify=0`
     throughout.
8. **Delete the old resource**: `DELETE /applications/{uuid}?
   delete_connected_networks=false&delete_volumes=true&docker_cleanup=true`
   — **`delete_connected_networks` defaults to TRUE**; on the shared
   `coolify` network that would be a disaster. Its container stops within
   ~10 s, its routers vanish, the new app is sole server. Then rename the
   new app to the old name.
9. **Chase the uuid.** Recreating means a NEW resource uuid, and things
   key on it: the app's own `COOLIFY_APP_UUID` env (EnaChat's worker
   PATCHes the web's domains by uuid — it pointed at a deleted resource
   until repointed + restarted), Traefik's stable service name
   `https-0-<uuid>@docker` in any file-provider config, runbook lines
   like `docker ps --filter name=<uuid>`. Grep every repo for the old
   uuid. The old sslip hostname survives as a plain domain string.
10. **Remove the deploy-key era manual webhooks** from the repo
    (`gh api -X DELETE repos/<o>/<r>/hooks/<id>`) once no deploy-key app
    sources it — otherwise every push fires them into the void.
11. **Prove it**: push a commit; every App-sourced app on that repo shows
    a row `status=finished, is_webhook=true` within seconds (EnaChat: the
    deployment row appeared **5 s** after the push, for all resources).

API notes learned on the way:
- `GET /deployments/applications/{uuid}` returns **`{"count", "deployments": [...]}`** — not a bare list, not `data`. Parsing the wrong key
  reads as "no deployments" while the deploy has already finished.
- `is_auto_deploy_enabled` reads back `null` for every app, including the
  ones that demonstrably auto-deploy — the field is not serialised; don't
  diagnose from it.
- `GET /github-apps/{uuid}/repositories` and `…/branches` return **500**
  for every App while 12 apps deploy fine from them — the listing
  endpoint is broken, not the integration. Check the GitHub side
  (`gh api orgs/<org>/installations`) instead.
- Coolify reports `running:healthy` for an app the moment its container
  exists, even before its first deployment row — the status comes from
  the container, not the deploy history.

The acceptance test in §1b still applies — the App wiring is automatic, but
"automatic" is a claim until a push shows `is_webhook: true`.

### Monorepo + GitHub App: every push deploys EVERY app — set `watch_paths`

A GitHub-App-sourced app deploys on every push to its branch, with no
path filter by default. On a monorepo that means one commit to
`enapost/docs/` rebuilds enachat, enajoin, enainbox and their workers too
(six builds, serialised by the server's `concurrent_builds: 2`) — and it
starts **the moment the resource exists**, before you have deployed it
yourself: four brand-new apps collected failed webhook builds from other
agents' pushes within minutes of creation, on build settings that were
not finished yet. Two rules:

- **Get build settings, envs, storage and labels right BEFORE the first
  push lands**, or create with the right `base_directory` from the start —
  there is no "not yet" state.
- **Set `watch_paths`** (newline-separated globs, repo-root relative) on
  every app in a monorepo: `enapost/backend/**` for a backend that only
  COPYs its own dir; add `enachat/frontend/**` where the image bundles
  the widget. Then a docs-only commit deploys nothing and a backend
  commit deploys one app. Prove both directions with two pushes.

A long `queued` while siblings build is normal (`concurrent_builds`);
only an `in_progress` row that never finishes is the jam from §6b.

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
- `SOURCE_COMMIT` = full 40-char deployed SHA build arg. Coolify Cloud passes it on **every Dockerfile-resource build** — verified 2026-08-25 (enachat) with `include_source_commit_in_build: false`, so the "Include Source Commit in Build" toggle is NOT required despite what its docs imply. Feed it to Sentry release / version endpoints. **Never pin a derived value like SENTRY_RELEASE in the UI env** — it freezes stale. Keep such ARGs in a **late, cheap Dockerfile layer** or every deploy busts the apt/pip cache.
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

### Django split settings: base.py must be production-safe (2026-08-29)

`production.py` does `from .base import *` and *then* `DEBUG = False`, so
every `x if DEBUG else y` in `base.py` has already resolved with base's
default — on EnaArchive that would have shipped the browsable API (a
`csrftoken` cookie on the API host), `ALLOW_PRIVATE_TARGETS=1` (SSRF guard
off), eager Celery (AI pipeline inline in gunicorn) and the literal
`dev-tenant-proxy-secret`, with no test able to notice. Rules:

- `base.py` holds the production values and `DEBUG = False`;
  `development.py` opts into DEBUG, the browsable renderer, dev secrets,
  private URL targets, eager Celery — *after* its import.
- `production.py` raises `ImproperlyConfigured` when `SECRET_KEY` or any
  shared-secret setting is empty / starts with `dev-` / is the build
  placeholder; the image's `collectstatic` step sets a phase env var
  (`DJANGO_SETTINGS_PHASE=build`) to skip that check.
- One test imports `config.settings.production` with the env patched and
  `sys.modules` cleared and asserts the fail-closed values; another asserts
  `development` still opts in. `grep -n "if DEBUG else" config/settings/base.py`
  must come back empty in review.

### Before the first deploy: inventory, classify, and plan to back up

- **Grep the settings/config for every env name the code reads** and
  classify each: generated (SECRET_KEY, SESSION_SECRET, METRICS_TOKEN,
  admin path), infra (magic DB/Redis vars), **external account** (Resend
  key + verified sending domain, OAuth client id/secret + redirect URIs,
  AI keys, payment provider merchant/test creds, R2 enabled on the
  account), build-time (`PUBLIC_*`). External accounts need a human and a
  deadline — decide what the app does without each one BEFORE boot, not
  when it refuses to start (2026-08-28: console email ×3, payments 501).
- **Generated secrets live only in Coolify's database.** On Coolify Cloud
  that database is not yours. Back them up the same day: hq's
  `homelab/tools/coolify-env-backup.sh` dumps every resource's runtime
  envs + DB credentials into an age-encrypted file; re-run on every env
  change. Without it, losing the instance means dead sessions/signed
  tokens and DB volumes you cannot open.

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

⚠️ **Adding a NEW bind-mounted config file wedges the next deploy** even
with Preserve Repository ON: `compose up` runs BEFORE the end-of-deploy repo
copy, so Docker auto-creates the not-yet-copied source as a directory stub —
the mounting container breaks, and the final `docker cp` then fails forever
with `cannot overwrite directory "<file>" with non-directory` (every retry
hits the same stub, and the failed stop-start can leave services down).
Unwedge on the server: `rm -rf` the stub under
`/data/coolify/applications/<uuid>/`, `scp` the real file(s) in, redeploy.
Files that existed before Preserve Repository's first copy are unaffected.

⚠️ **The preserve-repository copy is ADDITIVE** — it is a `docker cp` with
no `--delete`, so a file REMOVED from the repo lives on under
`/data/coolify/applications/<uuid>/` forever. Anything that scans a mounted
directory (Grafana provisioning, conf.d includes) keeps loading the deleted
file on every restart. Removing a config file from git therefore needs a
manual `rm` on the server plus a service restart. And the copy runs AFTER
`compose up`, so a newly added file in a directory mount takes effect one
restart LATER than the deploy that introduced it.

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
- **Distroless / no-shell images: turn the UI healthcheck OFF**
  (`PATCH {health_check_enabled: false}`) and rely on the image's own
  `HEALTHCHECK`. With it on, Coolify reported `custom_healthcheck_found:
  false` even though the Dockerfile declared one, injected its curl/wget
  probe (absent in distroless) and rolled back three consecutive deploys
  with "New container is not healthy" (EnaInbox, 2026-08-28). The image
  HEALTHCHECK gates blue-green on its own.
- **But the END GOAL is Coolify's check ON for every resource** (house
  rule, Oriol 2026-08-28): OFF is a documented, temporary exception, never
  the default for workers/schedulers. Each product's deploy doc lists the
  resources with the UI check off and how to turn it on (probe binary or
  a tiny HTTP `/healthz` in the worker image on an exposed port; a
  sidecar; for distroless, a static-linked `healthcheck` binary Coolify
  can exec). Track it as an open item until the list is empty.

## 5b. Field notes from a full API-only onboarding (server -> app, 2026-08-25)

- **Adding a server by API**: `POST /servers` (name, ip, port, user,
  `private_key_uuid`, `instant_validate`) after installing that key's pubkey
  on the box (the team's public key is readable: `GET /security/keys/{uuid}`
  → `public_key`). Plain `POST /servers/{uuid}/validate` (GET 405s) does
  NOT install prerequisites — it stops at "Docker Engine is not installed.
  Please install Docker manually". **The install variant is
  `POST /servers/{uuid}/validate` with body `{"install": true}`**
  ("Validation and installation started.") — it installs jq/curl/git/…
  and Docker itself; `settings.is_usable` flips to true in ~40 s while
  `validation_logs` keeps the stale text for a while (verified 2026-08-28,
  oriolj-nc-1, Debian 13). That is the Coolify-owns-Docker path — never
  install Docker yourself on a Coolify box.
- `GET /github-apps/{uuid}/repositories` is **not an API route** on Coolify
  Cloud (returns the dashboard HTML). Don't probe repo visibility that way:
  just `POST /applications/private-github-app`; it errors if the App
  cannot see the repo.
- `/servers/{uuid}/cloudflare-tunnel`, `…/enable`, `…/disable` only store the
  flag / restore `ip_previous`; they deploy and remove nothing. The tunnel
  itself is created on the Cloudflare side (`cloudflare-deploy` skill).
- **Tokens**: Coolify Cloud API tokens are `<id>|<48 chars>` (the tail is a
  checksum). A token that answers 401 "Unauthenticated" on every route with
  the right prefix is almost always a **mangled paste** (47 chars) — count
  before debugging anything else. Tokens can be issued with a 30-day expiry
  (Oriol's personal team does: renew monthly, see hq secrets registry).
- **App from a private repo without a GitHub App** (the fallback — §1c
  is the default):
  `POST /applications/private-deploy-key` with `private_key_uuid` (add that
  key read-only via `gh repo deploy-key add`), `build_pack: dockerfile`,
  `base_directory: /<subdir>`, and `dockerfile_location` **relative to the
  base directory** (`/backend/Dockerfile`, not `/<subdir>/backend/…`).
  Monorepos: one app per service, all pointing at subdirectories.
- **Django's ALLOWED_HOSTS breaks blue-green invisibly**: the image
  HEALTHCHECK probes `http://127.0.0.1:8000/healthz`; with ALLOWED_HOSTS set
  to only the public domain, Django answers **400 DisallowedHost**, the
  container never goes healthy, and every deploy "rolls back" with no app
  error in the deploy log. Always append `127.0.0.1`/`localhost` in settings
  (the healthcheck is infrastructure, not a spoofable public Host).
- **Persistent storage by API**: `POST /applications/{uuid}/storages` with
  `type` ∈ **`persistent`** (volume/bind; add `host_path` for a bind mount)
  or **`file`** (inline `content` + `fs_path`). The enum is in no doc —
  when the API rejects guesses, read Coolify's own
  `raw.githubusercontent.com/coollabsio/coolify/main/openapi.json` (grep
  the path's requestBody schema): the source is the spec. Related dead end:
  `custom_docker_run_options` accepts and STORES `-v host:container` but
  silently never applies it — volumes go through the storages API/UI only.
- **Coolify auto-assigns an sslip domain to EVERY application** — including
  workers, where `ports_exposes` is a required API field even though nothing
  listens. A Celery worker then gets a public hostname routed at a dead
  port: zero function, nonzero surface. After creating any non-web app,
  `PATCH {domains: ""}` + redeploy to remove the router.
- **One image, web + worker**: entrypoint switches on `ROLE` (web: migrate +
  gunicorn; worker: `exec celery … --concurrency=2`), and the HEALTHCHECK
  must be role-aware too — a worker can never answer `/healthz`, so it uses
  the free celery check (`grep -q celery /proc/1/cmdline`). Two Coolify
  applications share the repo/Dockerfile; the worker just adds `ROLE=worker`.
- **App-side https guards vs Coolify defaults**: Coolify assigns the sslip
  domain as `http://`; an app that enforces `https://` origins in production
  (good!) fails boot until you `PATCH /applications/{uuid}`
  `{domains: "https://<sslip>"}` — LE issues fine on sslip.
- **pgvector**: create the DB resource with `image: pgvector/pgvector:pg17`,
  not plain postgres — the extension cannot be added to the stock image at
  runtime. PATCH image + restart works while the DB is empty.
- DB/Redis resources created by API return `internal_db_url` with the
  resource **uuid as hostname** — Dockerfile apps on the same destination
  network reach it directly; use those hostnames in app env.

## 5c. Migrating a live Compose resource to Dockerfile (zero-downtime cutover, 2026-08-25)

Compose → Dockerfile cannot convert in place (different buildpack) — you create a NEW
application and cut the domains over. Done live on the EnaCast homepage with zero
downtime; the sequence and traps:

1. **Recon the old resource first**: `GET /applications/{uuid}` — for compose apps the
   top-level `fqdn` is null; the real domains live in `docker_compose_domains` (JSON
   keyed by service, values may carry a `:port` suffix = port-in-domain routing).
   Check `envs` (only `SERVICE_*` magic vars? then all real config is hardcoded in the
   compose `environment:` and must be re-created as UI env vars on the new app) and
   whether the compose mounts volumes (none = image is immutable, easiest case).
2. **GitHub deploy keys are globally unique**: a key already installed as a deploy key
   on repo A cannot be added to repo B (`gh repo deploy-key add` → 422 "key is already
   in use"). Reusing an existing Coolify key across repos is therefore impossible —
   generate a fresh keypair per repo, register it with `POST /security/keys`
   (`{name, private_key}` → uuid), then `gh repo deploy-key add` the pubkey read-only.
3. Create the new app (`POST /applications/private-deploy-key`, `instant_deploy: false`),
   POST its env vars, THEN deploy. Put **every** future hostname into things like
   `HOMEPAGE_ALLOWED_HOSTS` up front (sslip + prod domains) so the cutover needs no
   env change + redeploy.
4. **Verify on the auto-assigned sslip domain before touching the prod domain.**
5. Cutover, zero-downtime order: PATCH new app's `domains` (comma-separated, keep
   sslip) + redeploy new (rolling — see below) → verify prod Host serves → clear the
   old app's domains → `POST /applications/{old}/stop`. **Never redeploy the old
   compose resource to drop its Traefik labels** — a compose redeploy is stop-then-
   start (a 502 window) for nothing: stopping the resource removes the container and
   its router instantly. The overlap window where both resources claim the same Host
   rule is harmless (both serve the app).
6. Keep the old resource **stopped, not deleted** — it is the rollback (start it,
   restore its domains, stop the new one). And **disable its auto-deploy**
   (`PATCH {is_auto_deploy_enabled: false}`): a stopped GitHub-App resource with
   auto-deploy on is RESURRECTED by the next push to the repo — it came back
   `running:healthy` minutes after being stopped, redeployed by the migration's own
   docs commit. (It redeployed with the already-cleared domains, so it never stole
   traffic — clearing domains BEFORE stopping is what made this benign.)
7. **Deploy-key apps have no source webhook — push-to-deploy dies with the migration**
   unless you rewire it. Every app pre-generates `manual_webhook_secret_github` (visible
   in `GET /applications/{uuid}`) and defaults `is_auto_deploy_enabled: true`; add a
   repo webhook and parity is restored (verified: push → delivery 200 → rolling deploy):
   `gh api repos/<org>/<repo>/hooks -f name=web -F active=true -f 'events[]=push'
   -f 'config[url]=https://app.coolify.io/webhooks/source/github/events/manual'
   -f 'config[content_type]=json' -f 'config[secret]=<manual_webhook_secret_github>'`

   Learned again on enachat (2026-08-25) — this bites EVERY deploy-key app from
   day one, not just migrations. Extra field notes:
   - **Diagnostic**: `GET /deployments/applications/{uuid}` — if every row has
     `is_webhook: false`, all deploys were manual/API and pushes are going
     nowhere. Days of "deploys" can silently be someone clicking the button.
   - **One webhook per APP, not per repo**: the secret is per-application, so a
     monorepo serving N Coolify apps (web + worker) needs N webhooks on the
     same repo, same URL, each with that app's `manual_webhook_secret_github`.
     GitHub allows duplicate-URL hooks; Coolify matches by secret.
   - **Trigger the backlog without an empty commit**: after wiring, `gh api -X
     POST repos/<org>/<repo>/hooks/<id>/tests` delivers a synthetic push event
     for the latest commit — Coolify accepts it (200) and deploys the pending
     HEAD. Check results with `gh api …/hooks/<id>/deliveries`.
   - **New apps are GitHub-App-sourced by rule (§1c)**: source webhooks come
     wired for every app automatically (plus PR preview deploys), and none of
     this section is needed. Deploy keys remain the right choice only for fully-headless/API
     onboarding or repos where installing the App is undesirable — accept the
     manual webhook wiring as part of that trade, and do it at creation time,
     not after the first "why didn't it deploy".
8. `PATCH docker_compose_domains` is **asymmetric**: GET returns an object keyed by
   service, but PATCH demands an array — `[{"name": "homepage", "domain": ""}]`.

Rolling-update verification: the deploy log literally prints `Rolling update started` /
`New container started` / `Removing old containers` / `Rolling update completed`. An
image HEALTHCHECK **inherited from the base image** gates it fine — even though
`custom_healthcheck_found` stays false (Coolify only scans YOUR Dockerfile text) and
the UI healthcheck is off; `status: running:healthy` confirms Docker sees it.

### Config-driven static-ish sites (gethomepage pattern)

- **Bake the config into the image** (`FROM ghcr.io/gethomepage/homepage:latest` +
  `COPY config/ /app/config/`), no volumes: the image is fully immutable, blue-green
  is trivially safe, and every config change is a git commit + deploy. This beats
  bind-mounting `config/` (which needs Preserve Repository and its stub-wedge traps,
  section 4).
- **`FROM x:latest` resolves fresh on every Dockerfile-resource build** (buildkit
  re-pulls the metadata), while the old compose resource had months-stale cache — so
  the migration silently upgraded gethomepage several versions. Expect this on any
  `:latest` base when moving between resources; pin the tag if the app version matters.
- **Verify with the app's API, not the HTML**: gethomepage ≥ v1.7 stopped SSR-ing
  services into the initial page — `curl /` returns a default-looking "Homepage"
  title even when the config is loaded and fine. `/api/services`, `/api/widgets`,
  `/api/healthcheck` tell the truth; a headless-chromium screenshot
  (`chromium --headless=new --screenshot --virtual-time-budget=15000 <url>`) proves
  client-side widgets (custom.js) actually render. Almost shipped a "broken" rollback
  over what was a rendering-strategy change.
- gethomepage specifics: listens on 3000 (`ports_exposes: 3000`), image HEALTHCHECK
  hits `/api/healthcheck` (wget, start-period 20s) — no UI healthcheck needed; every
  Host it's served under (sslip included) must be in `HOMEPAGE_ALLOWED_HOSTS` or it
  400s "Host validation failed".

## 5c. Per-tenant domains (SaaS custom domains/subdomains) on Coolify

Verified 2026-08-25 (empirically on coolify-ovh-vps-1 + Coolify's own docs).
Three mechanisms, layered by tenant need:

- **Wildcard subdomains (`<tenant>.app.example.com`) — instant, zero API
  calls.** Coolify officially supports Traefik wildcard certs via DNS-01
  (docs: knowledge-base/traefik/wildcard-certificates): add a certresolver
  with `dnsChallenge` + a Cloudflare API token (Zone/DNS/Edit +
  Zone/Zone/Read) to the server's proxy configuration, wildcard DNS record,
  and either leave the app's Domain field EMPTY with a wildcard domain (the
  documented multi-tenant pattern) or add a file-provider router. The app
  resolves the tenant from the Host header. Tenant creates themselves in
  the product's own UI — infra never changes.
- **File-provider dynamic configs — the extension point.** Coolify's Traefik
  loads `/data/coolify/proxy/dynamic/` (`providers.file.directory`,
  watch=true, enabled by default). Two EMPIRICAL facts that make it usable:
  the generated docker-provider service names are **stable across deploys**
  (`http-0-<app-uuid>` / `https-0-<app-uuid>` — keyed by app uuid, not the
  changing container name), so a file-provider router can reference
  `https-0-<app-uuid>@docker` safely; and file changes hot-reload without
  touching the app. ⚠️ If an app GENERATES these files from user-entered
  domains, sanitize hard — a hostile "domain" string is arbitrary Traefik
  config injection.
- **Full custom domains (client's own `xat.client.tld`) — via the API.** The
  app (or an operator) `PATCH /applications/{uuid}` appending to the
  comma-separated `domains` + triggers a deploy: blue-green makes it
  zero-downtime, LE HTTP-01 issues on the new host, ALLOWED_HOSTS/CSRF must
  be updated in the same change. Cost: a rebuild-deploy per domain change —
  fine at tens-of-tenants scale, wrong at hundreds (then: file-provider
  generation above, or Cloudflare for SaaS — 100 custom hostnames free —
  with the origin routing a catch-all). Fetch-then-append mechanics: GET the
  app first — the current comma-separated domains are in `fqdn` (Dockerfile
  resources) — and PATCH `domains` with old+new joined; PATCH replaces, so
  a bare new value silently drops the live sslip/prod domains.
- **Django behind this: dynamic ALLOWED_HOSTS with no env churn (verified
  in prod, EnaChat 2026-08-25).** Django's `request.get_host()` validates by
  ITERATING `settings.ALLOWED_HOSTS` (`django.http.request.validate_host`)
  on every call — the setting only needs to be an iterable of patterns. A
  `list` subclass whose `__iter__` also yields the currently-active custom
  domains from the DB (short-TTL cached, `()` on any DB error = fail closed)
  lets client domains pass strict host validation with zero env edits and
  zero redeploys, while unknown Hosts still 400. Wildcard-subdomain tiers
  stay static: `.{base}` suffix entries (Django matches base + any
  subdomain). CSRF usually needs nothing if the tenant hosts serve only
  GET pages + csrf-exempt keyed APIs. Two traps: define the class where
  settings can import it without loading models (query lazily inside
  `__iter__`), and Django's `setup_test_environment()` replaces
  ALLOWED_HOSTS with a plain list — tests must `override_settings` with a
  fresh instance of the dynamic class.
- **Wildcard-cert DNS reality check**: DNS-01 needs API control of the zone
  holding `_acme-challenge.<base>`. Cloudflare cannot host a subdomain-only
  zone except on Enterprise ("subdomain setup") — so if the apex zone lives
  at an API-less registrar (CDmon…), either migrate the whole zone to
  Cloudflare or NS-delegate just the base subdomains to any lego-supported
  DNS host that accepts arbitrary zone names (DigitalOcean DNS, deSEC,
  Route53) and point the certresolver's provider there.
- **The cheapest resolution is often a NEW domain (EnaChat, 2026-08-26).**
  The dilemma above assumes you must move the zone you already depend on —
  for enacast.com that meant recreating ~150 live records (every radio
  client's site, company MX, DKIM) with no undo, which is why the wildcard
  tier sat unactivated for weeks. Registering `enacast.chat` and putting
  *that* zone on Cloudflare cost nothing to migrate (SOA + NS only) and
  unlocked DNS-01 wildcards, an apex on Pages, and a cleaner product name in
  one move. When a wildcard-TLS plan stalls on "we can't move the zone",
  price a second domain before designing around the constraint.

### Coolify hosts behind a Cloudflare-hosted zone

- **Every A record pointing at the Coolify box must be DNS-only (grey
  cloud).** Traefik terminates TLS itself with Let's Encrypt; an orange-cloud
  record makes Cloudflare terminate instead, and HTTP-01 validation for the
  new host fails behind the proxy (you get 525/526 or a permanently pending
  cert). Set `"proxied": false` when creating them by API — the dashboard
  defaults to proxied. Pages custom domains are the opposite: those are
  proxied, and Cloudflare manages the record itself.
- **Never retire the old app hostname when moving domains.** Installed
  one-script embeds on client websites hardcode the origin they were pasted
  with (`<script src="https://<old-host>/v1.js" data-backend="https://<old-host>">`),
  and the portfolio rule is that a town pastes the tag once and never touches
  its site again. Keep the old FQDN attached to the resource (Coolify
  `domains` is a comma-separated list — append, never replace) for as long as
  any embed can exist, i.e. indefinitely. A 301 does not save you: the widget
  also makes API calls to `data-backend`.

## 6. Deploy speed and signal handling

- **Compose buildpack stops containers sequentially with `docker stop -t 30` and IGNORES `stop_grace_period`** (upstream coolify#5975). Still set `stop_grace_period` (honored elsewhere), but the real lever is making SIGTERM work:
  - `command: sh -c "exec python …"` — the `exec` is mandatory; a bare shell as PID 1 swallows SIGTERM (30 s timeout every stop). Entrypoint scripts end with `exec "$@"`.
  - `init: true` on Python services running plain loops — PID 1 ignores signals without an explicit handler, so `while True: time.sleep()` management commands never die; tini fixes it. (gunicorn/celery register handlers, they're fine.)
- Dockerfile resources: set the UI "Stop Grace Period" field (that one applies).
- **Coolify ≥ v4.0.0-beta.450 for Docker layer caching** — older versions injected per-build args that busted the cache every deploy.
- Coolify reports "deployed" when containers **start**, not when healthy — do collectstatic at build time, keep the entrypoint fast, tune `start_period`.
- Big Compose stacks: split into a `web` resource and a `workers` resource so web deploys don't cycle every worker container.
- **Base Directory IS the build context, period**: Coolify runs
  `cd <base_directory> && docker build -f <base_directory><dockerfile_location> <base_directory>`.
  The EnaChat shape (`/enachat` + `/backend/Dockerfile`) only works because
  that Dockerfile COPYs `backend/` and `frontend/` as siblings. A flat Go
  backend whose Dockerfile does `COPY go.mod go.sum ./` needs
  `base_directory: /<product>/backend` + `dockerfile_location: /Dockerfile`
  or every build dies with `"/go.mod": not found` (EnaJoin, EnaInbox,
  2026-08-28 — copied the EnaChat values blindly). Also: PATCHing
  `base_directory`/`dockerfile_location` **regenerates `custom_labels`**
  and drops your `oj.*` lines — re-append them as the LAST patch before
  deploying, and verify on the container, never from the API alone.
- Base Directory vs Dockerfile Location are separate fields: the **build context must contain everything the Dockerfile COPYs** (migrations dir, sibling frontend/). A too-narrow base dir often still builds — with the COPY silently empty. Huge image → check the repo-root `.dockerignore`.

## 6b. Deploys: one per push, and the mixed-version failure mode

**A `git push` to a connected repo ALREADY deploys.** Calling
`POST /deploy?uuid=…` on top just queues a second, redundant build of the
same commit. Push *or* trigger — never both.

**Blue-green means both versions serve at once during the swap.** The old
and new containers both carry `traefik.enable=true`, so Traefik
round-robins across them until the old one is stopped. Normally that window
is seconds. The symptom when it is not: **the same URL returns old content
and new content on alternate requests** (a page title, a template string, a
feature flag — flapping request to request). Do not chase this as a caching
bug; check how many app containers are running.

**Wedged deploy = permanent mixed-version serving.** Coolify Cloud drives
the deploy over SSH into a per-deployment `coollabsio/coolify-helper`
container. If that connection drops mid-run (a flaky tunnel will do it),
the deploy stalls at ~95%: new container healthy and serving, **old
container never stopped**, deployment stuck `in_progress` forever.

```bash
# diagnose — two app containers + an idle helper is the signature
docker ps --filter "name=<app-uuid>" --format "{{.Names}} {{.Status}}"
docker ps --format "{{.Names}}\t{{.Image}}" | grep coolify-helper
docker top <helper>       # only tini + "tail -f /dev/null" => idle, not working
docker inspect <c> --format '{{.Config.Image}}'   # which build each one is
```

Remedy, in order: `docker stop -t 30 <old-container>` — that ends the mixed
serving immediately and is exactly what the deploy would have done — then
`docker rm -f <helper>` to clear the orphan — **but removing the helper does
NOT clear Coolify's record.** The deployment stays `in_progress` forever on
the control-plane side, and that is the part that actually hurts.

### A stuck deployment head-of-line blocks every later one

This is the failure that cost the most time, so recognise it fast. A wedged
`in_progress` deployment does not just fail itself — **the queue is
serial**, so every subsequent deploy of that resource stacks up behind it
and never runs. Symptoms:

- `POST /deploy` keeps answering **"Deployment already queued for this
  commit."** and nothing happens. Pushing a NEW commit does not help: when
  the resource's `git_commit_sha` is `HEAD`, "this commit" always matches.
- No `coolify-helper` container ever appears on the host — the control
  plane never dispatches.
- The app keeps serving an old build for hours while its siblings (a worker
  resource on the same repo and webhook) deploy normally. **That asymmetry
  is the tell**: the pipeline is fine, one resource's queue is jammed.

Diagnose with the PER-APPLICATION listing, not the global one — the global
`GET /api/v1/deployments` showed an empty queue while 13 deploys were
stacked up:

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "User-Agent: $UA" \
  "$API/deployments/applications/<app-uuid>?take=20"
# find the oldest entry still `in_progress` — that is the blocker
```

Then cancel it:

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "User-Agent: $UA" \
  "$API/deployments/<deployment-uuid>/cancel"
# -> {"message":"Deployment cancelled successfully.","status":"cancelled-by-user"}
```

Cancelling the single blocker drains the whole backlog and the newest build
runs immediately. No UI needed.

API notes:
- **`POST /deployments/{uuid}/cancel` is the cancel endpoint.** (`DELETE
  /deployments/{uuid}` 404s — do not conclude from that that cancelling is
  unsupported, as this skill previously did.)
- `GET /deployments/applications/{uuid}` is the per-resource queue and the
  one to trust; `GET /deployments` (global) can read empty while a resource
  is jammed.
- **`GET /deployments/{uuid}` is unreliable on Coolify Cloud: it 404s
  ("Deployment not found.") for a deployment that exists and is RUNNING**,
  and has also returned an empty body. Never treat that 404 as "the deploy
  failed" — code that polls a deployment to completion must fall back to
  the per-application queue and keep polling on 404/empty. (EnaChat's
  provisioning task did treat it as fatal and stamped `error` on a live
  client domain; fixed in enasuite `db154f2`.)
- **The published spec is the source of truth**: `app.coolify.io/openapi.json`
  302s, but the real file is
  `raw.githubusercontent.com/coollabsio/coolify/main/openapi.json`. Grep it
  before assuming an endpoint does not exist.
- Statuses seen: `queued`, `in_progress`, `finished`, `failed`, `cancelled`,
  `cancelled-by-user`.

### While a resource is jammed, watch for code/schema skew

Sibling resources keep deploying, so a worker can end up running code whose
migrations the (jammed) web resource never applied — the first task touching
a new column then dies on `ProgrammingError`. Migrations that are
**additive-only** (AddField with defaults, no rename/drop) are safe to apply
out-of-band from the sibling's image, and become a no-op when the jammed
resource finally deploys:

```bash
docker exec -w /app <worker-container> python manage.py showmigrations <app>
docker exec -w /app <worker-container> python manage.py migrate <app>
```

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
  (production + preview rows) — not a bug, dedupe by key. **`is_preview`
  tells them apart**: `false` is the production row, `true` is the
  preview-deployment row, and the two often hold different values (on
  enachat-web, prod `PUBLIC_BASE_URL=https://chatapp.enacast.com` vs preview
  `http://<uuid>.<ip>.sslip.io`). Reading the pair as duplicates and taking
  whichever came first means a 50% chance of reporting — or overwriting —
  the wrong environment's value.
- `POST /deploy?uuid={app}` — trigger a deploy (GET returns 405). **Add
  `&force=true` after any domain or env change.** Without it the API answers
  `{"message": "Deployment already queued for this commit."}` and does
  nothing — the commit is unchanged, so Coolify dedupes it. The app stays
  `running:healthy` with its OLD Traefik labels, so a freshly added domain
  answers 404 on HTTP with no certificate and looks like a DNS or ACME
  problem. Verified on enachat-web, 2026-08-26.
- **`is_literal: true` single-quotes the stored value**: `real_value` comes
  back WITH the quotes (`'fcU…y'`), but compose's `.env` parsing strips them,
  so the container sees the inner value. Anything reading `real_value`
  (scripts, copy-paste from the UI) must strip the quotes or auth fails with
  the "same" password.
- **`custom_labels` is base64 BOTH ways on Coolify Cloud** (re-verified
  2026-08-28 on docker-image resources): GET returns the base64 blob, and
  PATCH with plaintext answers 422 `The custom_labels should be base64
  encoded`. Recipe: GET → decode → append `oj.*` lines → encode → PATCH →
  redeploy (labels apply at container create). A regenerated label set
  (after `PATCH {domains: ""}`) REPLACES yours — re-append after domain
  changes. If a value ever fails to decode to `traefik…` lines, it was
  double-encoded by a previous mistake: decode repeatedly until plaintext.
  Deployment rows carry `commit` and `is_webhook`.
- **Coolify UI health check on worker/beat containers**: expose a tiny
  in-process HTTP `/healthz` (python `ThreadingHTTPServer` thread started
  from Celery's `worker_ready` / `beat_init` signals, port 9000, never
  published), set `ports_exposes: "9000"` + `health_check_path: /healthz`,
  and ship `curl` in the image (the probe Coolify injects needs it —
  `python:slim` has neither curl nor wget, the deploy rolls back with "New
  container is not healthy"). Verified 2026-08-28, llm-index-watcher: all
  three resources `running:healthy` with the UI check ON.
- `POST /s3-storages` `description` is validated like `POST /projects` —
  ASCII punctuation only (a `:` or `*` fails with "format is invalid").
- **`PATCH /applications/{uuid}/envs` (and `/envs/bulk`) can 500 for a
  given key even with the value unchanged** (hq-monitoring `LOKI_WRITERS`,
  2026-08-28). Workaround that works: `DELETE /applications/{uuid}/envs/{env_uuid}`
  then `POST /applications/{uuid}/envs` with the full new value — prove
  POST first with a throwaway key, keep the old value in hand to restore.
  Field names on write are `is_buildtime` / `is_literal` / `is_preview`
  (`is_build_time` → "This field is not allowed"). A response that is the
  dashboard HTML instead of JSON = send `Accept: application/json`.
- A multi-line env value does not survive Coolify's `.env` round-trip —
  design secrets-from-env files to accept one-line separators (the
  loki-gateway takes comma-separated `user:password` since `6d0c380`).
- App settings like `is_preserve_repository_enabled` PATCH directly on
  `/applications/{uuid}` even though GET nests them under `settings`.
- **Replacing Coolify's tunnel connector, zero-downtime**: Coolify Cloud's
  automated Cloudflare-tunnel setup runs a docker container named
  `coolify-cloudflared` (`cloudflare/cloudflared:latest`). A Cloudflare
  tunnel accepts **multiple connectors on the same token**, so the swap to a
  managed native install is: start the new connector with the same token
  (both serve the tunnel; dashboard shows 2), verify the new one's
  `/ready`, `docker rm -f coolify-cloudflared`, then prove it with a
  deploy. Never remove first — the tunnel is Coolify's only way in. On
  strict-egress/netcup hosts force `TUNNEL_TRANSPORT_PROTOCOL=http2` (see
  the exit-255 row below). Note `pkg.cloudflare.com` can lag new Debian
  releases (no trixie dist while the host ran Debian 13) — pin the previous
  codename; cloudflared is a static Go binary, any dist works.
- The server's `ip` field must resolve **from Coolify Cloud** (public DNS).
  Setting a not-yet-published hostname breaks the connection ("dial tcp:
  lookup … no such host"), blocks all deploys, and flips the server
  unreachable; `ip_previous` keeps the old value. Create the DNS record
  first, then change the field.

### More API facts, verified 2026-08-28 (four products in one afternoon)

- `POST /databases/redis` **`redis_conf` must be base64** (plain text →
  "The redis_conf should be base64 encoded"). It becomes
  `/usr/local/etc/redis/redis.conf`; `appendonly yes\nappendfsync everysec`
  there is how a Coolify Redis resource gets AOF (verify: `config get`).
- **Named persistent storage cannot be shared between two resources** —
  Coolify prefixes the volume with the resource uuid, so a web and a
  worker each get a private volume. For media written by the worker and
  served by the web, use a `host_path` bind on BOTH (`POST …/storages
  {"type":"persistent","name":…,"host_path":…,"mount_path":…}`) and chown
  the dir to the image uid first. `PATCH …/storages {uuid, host_path}`
  converts an existing named entry.
- Named volume + nonroot needs **no host chown** if the Dockerfile
  pre-creates and `--chown=65532:65532`s the mount dir into the distroless
  image — the volume initialises with that ownership (EnaJoin). Bind
  mounts remain the chown case.
- `POST /projects` `description` rejects an em dash — ASCII punctuation
  only (`- _ . , ! ? ( ) ' " + = * / @ &`).
- The Cloud API **intermittently returns 200 with an empty body** (seen
  on `GET /deployments/applications/{uuid}` for minutes while builds ran).
  Retry on empty; never read empty as "no deployments".
- `stop_grace_period` reads back `null` after a 200 PATCH; app `status`
  shows `running:healthy` while its deployment row is still `queued`.
- gunicorn ≥ 26 opens a control socket under `$HOME/.gunicorn/`; with a
  `--no-create-home` system user it logs `Control server error:
  Permission denied` every boot — pass `--control-socket /tmp/gunicorn.ctl`.
- `curl -I` on a `@require_GET` health view returns 405 — probe with GET.
- Distroless one-offs: `docker exec <c> /<binary> <subcommand>` inherits
  the container env, so bake onboarding into the binary
  (`create-staff`, …) — there is no shell and no repo checkout in prod.
- R2: a TLS **handshake failure** on `<account>.r2.cloudflarestorage.com`
  means R2 is not enabled on the Cloudflare account — don't debug the keys.

## 7c. Docker-image apps by API (exporters etc. — EnaChat monitoring, 2026-08-25)

Public-image sidecars (postgres-exporter, redis_exporter, …) as their own
resources: `POST /applications/dockerimage` with `project_uuid`,
`server_uuid`, `environment_name` **and** `environment_uuid` (both
required), `docker_registry_image_name`/`_tag` (verify the tag against the
registry — never `latest`), `ports_exposes`, `connect_to_docker_network:
true` (to reach DB resources by their uuid hostname), `instant_deploy:
false`; then envs → storages → `PATCH {domains: ""}` (sslip is
auto-assigned even here) → `POST /deploy`.

- **`ports_mappings` via API is digits-only** — the rule is
  `regex:/^(\d+:\d+)(,\d+:\d+)*$/` (bootstrap/helpers/api.php), so an
  IP-qualified bind (`100.x.y.z:9187:9187`) 422s even though the UI field
  accepts it and docker supports it. Consequence: an API-created port
  publish is always **0.0.0.0, which bypasses ufw**. Fix on the host with
  DOCKER-USER rules (the supported Docker hook), persisted via a oneshot
  systemd unit after docker.service:
  `iptables -I DOCKER-USER ! -i tailscale0 -p tcp -m conntrack
  --ctorigdstport <port> --ctdir ORIGINAL -j DROP` (+ ip6tables). Install
  the rules BEFORE the first deploy so there is no exposure window, and
  document them in the server's hq doc — Coolify knows nothing about them.
- **Envs field is `is_buildtime`** — `is_build_time` 422s ("field not
  allowed"). Storage of `type: "file"` on an APPLICATION works like on
  services (inline `content` + `fs_path`; the server file lands under
  `/data/coolify/applications/<uuid>/…`) — but do NOT send `name` for
  type file (422). This is how postgres-exporter gets its
  `PG_EXPORTER_EXTEND_QUERY_PATH` custom-queries yaml with zero repo.
- `GET /deployments/applications/{uuid}` returns
  `{"deployments": [...]}` (a wrapper object, newest first) — not a bare
  array.
- **Switching an app's domain from `http://` to `https://<x>.sslip.io` is a
  real TLS path**: Coolify regenerates the router labels with
  `tls.certresolver=letsencrypt` and Traefik gets a Let's Encrypt cert for
  the sslip name (~1 min). The RUNNING container keeps the old labels until
  a `POST /deploy?…&force=true` — until then https answers with
  `TRAEFIK DEFAULT CERT`. Use this to scrape `/metrics` over TLS when no
  real domain exists yet (Licita Radar, 2026-08-28).
- **Coolify UI health check for a scheduler/worker**: give the process an
  HTTP listener it already has (supercronic `-prometheus-listen-address`,
  celery-exporter, …), PATCH `health_check_enabled/path/port` to it and
  redeploy — no more "UI check OFF" exceptions for non-web resources.
- The DOCKER-USER tailnet-only guard is now on TWO hosts by hand
  (coolify-ovh-vps-1, oriolj-nc-1: `/usr/local/sbin/docker-user-tailnet-only.sh`
  + oneshot unit, ports listed inside the script) — folding it into a
  shared/ansible role with a per-host port list is overdue.
- postgres-exporter (quay.io/prometheuscommunity/postgres-exporter) wants
  `DATA_SOURCE_NAME=postgres://…@<db-uuid>:5432/<db>?sslmode=disable`
  (from the DB resource's `internal_db_url`); redis_exporter
  (oliver006/redis_exporter) wants `REDIS_ADDR=redis://<db-uuid>:6379` +
  `REDIS_PASSWORD` split out — it does NOT parse creds from the URL.

## 7d. Migrating resources between Coolify INSTANCES (Cloud ↔ self-hosted) — UNTESTED

⚠️ **Not yet exercised. Everything here is inferred from the verified
same-instance recreate playbook (§1c) and from how Coolify stores state.
Before trusting it: take backups of every database and volume, and run it
end-to-end on a NON-critical project first.** Near-term TODO: script it
(check whether the community has an export/import tool first — as of
2026-08 Coolify has no official one; look before writing).

What lives where (the reason a migration is possible at all):
- **Coolify's own DB** holds only configuration: projects, resources,
  envs, storages definitions, domains, deploy history. That is what an
  instance migration moves.
- **The data lives on the SERVER**: docker volumes (`<resource-uuid>-<name>`
  for named storage, or the `host_path` you chose), the database
  containers' volumes, Traefik's `acme.json`. A new Coolify instance that
  adopts the same server sees the same disk.

Plan, resource by resource:
1. **Export** from the old instance via API: `GET /applications/{uuid}`,
   `…/envs`, `…/storages`; for DBs `GET /databases/{uuid}` (image, version,
   the volume name); the project/environment structure.
2. **Add the server** to the new instance (same host — it keeps Docker,
   containers and volumes; Coolify's agent install is idempotent). Do NOT
   let both instances manage the same server for long: both write
   Traefik config.
3. **Recreate each resource** on the new instance with the §1c playbook
   (GitHub App source, same build settings, envs runtime-only, labels).
4. **Re-attach data, not recreate it**: the new resource gets a NEW uuid,
   so a named storage becomes `<new-uuid>-media` — an EMPTY volume. Either
   use `host_path` binds (uuid-independent; the file tree is just there)
   or, before the first deploy, `docker volume create <new-uuid>-media`
   and copy `/var/lib/docker/volumes/<old>/_data/.` into it. Databases:
   safest is `pg_dump` → restore into the new DB resource; the shortcut
   of pointing a new Postgres resource at the old volume name is
   plausible but untested.
5. **Domains + certs**: attach the same domains; `acme.json` on the host
   keeps the certificates, so no reissue — but the router names change
   with the uuid (file-provider configs referencing
   `https-0-<uuid>@docker` must be updated).
6. **Cut over** with `force_domain_override` overlap as in §1c, verify,
   then delete the old resources on the old instance with
   `delete_volumes=false` (the volumes are now the new instance's data)
   and `delete_connected_networks=false`.
7. Chase the uuid everywhere (§1c step 9) and re-prove push-to-deploy.

Backups are not optional here: a wrong `delete_volumes` default on step 6
is unrecoverable.

## 8. Failure → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| 404 on a domain that RESOLVES to the server | Traefik has no router for that Host — the domain isn't on the resource (or it was added without a redeploy) | PATCH `domains` (comma-separated — ADD, keep the sslip one) + update ALLOWED_HOSTS/CSRF/PUBLIC_BASE_URL in the same change + redeploy. 404-vs-502 is the diagnostic: 404 = DNS fine, routing unclaimed; 502 = routed but app dead |
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
| Deploys on a tunnel-connected server fail intermittently, exit 255 mid-command (`mkdir -p` "fails" with no output) | **First check `journalctl -u ssh | grep -i maxstartups` on the server.** Coolify Cloud opens a FRESH SSH connection per deploy command (no ControlMaster through the cloudflared ProxyCommand) — 1,300–2,200 logins/min during a deploy — and OpenSSH's stock `MaxStartups 10:30:100` drops the 11th+ pre-auth connection: `drop connection #11 from [::1] … Maxstartups`, `additional 209 connections dropped`. A dropped pre-auth connection is exit 255 with no output, at a random step (clone, env write, `docker cp`, `mkdir`). Seen 2026-08-28 on monitor-1-nc, 5 deploys in a row. The other cause, when sshd is silent: cloudflared on QUIC over DEGRADED UDP (strict egress fw, netcup UDP filtering) — connects, then drops mid-transfer | `MaxStartups 100:30:200` in the sshd drop-in (hq `shared/ansible` baseline sets it fleet-wide, `ssh_max_startups`), reload sshd, redeploy. For the QUIC case force `TUNNEL_TRANSPORT_PROTOCOL=http2` (TCP) on the connector. Also: a failed deploy may have ALREADY stopped the old stack (Compose buildpack stops before it starts) — check `docker ps` before assuming the app is still serving |

## 9. Secrets, domains, scheduling

- Secrets: every credential is a Coolify magic var or UI env var — never committed, not even encrypted, in repos Coolify pulls. Strictest pattern: compose `secrets:` sourced from env so containers read `/run/secrets/*` files (`__FILE` vars) instead of container env (docker inspect exposes `Config.Env`; needs compose ≥ 2.23.1). Private repos deploy via Coolify's read-only deploy key.
- DNS: create records **grey-cloud/DNS-only first** so Traefik completes the Let's Encrypt HTTP-01 challenge; enable the Cloudflare proxy per-record afterwards. **Add domains, don't replace** — keep the default `<uuid>.<ip>.sslip.io` FQDN alongside custom domains (links already shipped). Behind Traefik, Django needs `SECURE_PROXY_SSL_HEADER` (trust `X-Forwarded-Proto`), `SECURE_SSL_REDIRECT = False`, and `CSRF_TRUSTED_ORIGINS`.
- Scheduling: Coolify has per-resource **scheduled tasks** (good for periodic management commands) and UI-configured DB backups with retention/S3. In-container cron without Celery = **supercronic**, never crond. With Celery, celery-beat — and apply the `celery-deploy-safety` skill in full, plus the sizing rules (`--concurrency=2`, gunicorn max-requests, no Flower in prod).

## Replacing a live resource (compose → Dockerfile, repo move, product merge): the DATABASE moves too

Learned 2026-08-29 (EnaArchive: HistoricalArchives' compose stack replaced by Dockerfile resources; an adversarial review caught that the runbook only moved the media bucket). A new Postgres resource starts **empty** — a cut-over that only re-points DNS strands the live data in the retired stack. Always:

1. **Rehearse on a copy**: `pg_dump -Fc` the old DB → restore into a scratch container of the target image (pgvector etc.) → run the new code's `migrate` + `check` → compare row counts per model (and any data-migration side effects — e.g. a tenant backfill that had scoped the superuser) → spot-check that stored media keys resolve on the target bucket.
2. **Freeze writes** on the old stack (worker to 0, announce the window).
3. Copy media (`rclone copy`), then **dump → restore** into the new DB and repeat the count comparison; smoke the new stack on its own hosts (`/healthz`, admin login, a tenant page with a `Host` override, the permanent-URL redirects) **before** DNS.
4. **Reversible DNS cut-over** (low TTL beforehand); rollback = point back, the old stack is untouched as of the freeze.
5. **Keep the old DB stopped-not-deleted** for a backup cycle; verify the first scheduled R2 backup execution of the new DB.

Write these steps into the product's `docs/first-deploy.md` and put the rehearsal as the FIRST cut-over item in `USER_TODO.md` — the resource creation must not come before it.
