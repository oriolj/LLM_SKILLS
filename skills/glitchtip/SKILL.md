---
name: glitchtip
description: Operate the estate's GlitchTip (self-hosted Sentry-compatible error tracking on infra-monitoring) — orgs per realm, the API token, self-serving projects/DSNs via the Sentry API, the org-creation-is-closed workaround, the built-in MCP server (flag, auth, Claude Code wiring, the CSRF-403 symptom), and the same-origin tunnel that lets BROWSER SDKs reach the tailnet-only ingest without exposing it. Use when a project needs a DSN, when creating a GlitchTip org/project, when wiring sentry_sdk in any app, when adding error tracking to a frontend (@sentry/browser, @sentry/react, the client half of @sentry/nextjs or @sentry/astro) or asking whether to use Sentry SaaS for it instead, when adding GlitchTip as an MCP server to Claude Code, or when the user mentions GlitchTip, error tracking, or Sentry DSNs.
---

# GlitchTip — the estate's error tracking

## Instance + account model

- **ONE self-hosted instance for all realms**: UI + MCP at
  `https://infra-monitoring.armadillo-tawny.ts.net` (Tailscale Serve, since
  2026-09-07); API + ingest also on `http://infra-monitoring:8000`
  (tailnet-only both), Coolify containers `web-/worker-ecsgwgsccsgwk40ss0og4gsc`
  on the `infra-monitoring` host.
- **Orgs partition it per realm**: `enacast` (pre-existing) and `oriolj`
  (created 2026-08-31). smartupsoft: create when first needed (recipe
  below). Projects (2026-09-02): `enacast/{enacast-backend, enacast-ai,
  leadhunter, enacast24h, encasago}`, `oriolj/{talaia, h2a-leadhunter, licita-radar, llm-index-watcher, backupmaker, panotxa}` (panotxa = id 12, created 2026-09-07 by API; takes BOTH the Django backend — migrated off sentry.io SaaS the same day, `SENTRY_DSN` on web+worker+beat — and the PWA's browser events through the tunnel below) (backupmaker = id 11, created 2026-09-06 by API for the two backup loops on mlrtx2 — crashes only, per-job failures stay in metrics; the DSN keeps the MagicDNS host because mlrtx2's containers resolve `infra-monitoring`) (licita-radar = id 8 and llm-index-watcher = id 9, both created 2026-09-02 by API, DSNs on their Coolify apps with the MagicDNS host — oriolj-nc-1 is on the EnaCast tailnet and its containers resolve `infra-monitoring`).
  `enacast/leadhunter` (id 3) is a wrong-realm leftover (H2A-LeadHunter
  is personal) — 0 events ever; deletion is queued as Oriol's decision
  in hq `USER_TODO.md`. **A personal app's project goes in `oriolj`** —
  check the org before reusing a DSN found on a resource.
- **One user**: `oriol@smartupsoft.com` (NOT a superuser) — owner of both
  orgs.
- **Org-level API token**: `hq/homelab/secrets/glitchtip.env`
  (`GLITCHTIP_URL`, `GLITCHTIP_API_TOKEN`). With it, agents self-serve
  projects and DSNs — do NOT ask Oriol for UI clicks any more (the older
  guidance in `fleet-observability` §5b predates the token).

## API (Sentry-compatible, /api/0/, Bearer auth — verified pieces)

```bash
T=$(grep '^GLITCHTIP_API_TOKEN=' hq/homelab/secrets/glitchtip.env | cut -d= -f2)
curl -H "Authorization: Bearer $T" http://infra-monitoring:8000/api/0/organizations/
# projects of an org:    GET  /api/0/organizations/<org>/projects/
# create (team-scoped):  POST /api/0/teams/<org>/<team>/projects/  {"name": "..."}
# a project's DSNs:      GET  /api/0/projects/<org>/<project>/keys/
```
Verified 2026-09-02 (EnaCast 24H): `POST /api/0/teams/enacast/enacast/projects/`
with `{"name": "enacast24h", "platform": "python-django"}` → 201 with
`slug`/`id`; `GET /api/0/projects/enacast/enacast24h/keys/` → `[{"dsn":
{"public": "http://<key>@infra-monitoring:8000/<id>", ...}}]`. The DSN's host
is the MagicDNS name: an app container on a host without MagicDNS (or
whose resolver is not tailscaled's) cannot resolve it — **rewrite the host
to the hub's tailnet IP** before storing it as the app's `SENTRY_DSN`.
**The IP depends on which tailnet the app host is on**: `100.83.245.69`
on the EnaCast tailnet (`armadillo-tawny.ts.net`), `100.82.104.98` on the
personal tailnet (`ainu-universe.ts.net`, where infra-monitoring is a
*shared* node — jluv-apps-1 lives there). Test from the host's `tailscale
status --json`, and prefer the name when the container resolves it:
on jluv-apps-1 (2026-09-02) `docker exec <app> getent hosts
infra-monitoring.armadillo-tawny.ts.net` works, so the DSN keeps the
MagicDNS host. Verify delivery, don't assume: send a probe
(`docker exec <app> python -c 'import sentry_sdk; sentry_sdk.init(dsn=...);
sentry_sdk.capture_message("probe"); sentry_sdk.flush()'` — or, when the app
initialises the SDK in settings, `django.setup()` and skip `init`, so the
probe carries the app's own `release`/`environment`; llm-index-watcher
2026-09-02) and read
`GET /api/0/projects/<org>/<project>/issues/` — the probe shows up within
seconds. **Reading issues (verified 2026-09-02 on the enacast org):**
`GET /api/0/projects/<org>/<project>/issues/?sort=-last_seen&limit=15`
(the Sentry value `sort=date` is REJECTED — allowed: `last_seen`,
`first_seen`, `count`, `priority`, with `-` for descending; a wrong value
returns a pydantic `literal_error` JSON, not a list — parse the response
before indexing), `GET /api/0/issues/<id>/events/latest/` gives the full
event (`entries[type=exception]` frames with `inApp`, `entries[type=breadcrumbs]`
with the SQL `category: query` lines that pinpointed django-silk's GC
deadlock, `tags`, `culprit`). `GET /api/0/organizations/<org>/projects/`
lists projects with ids/slugs. Last resort only: GlitchTip's `:8000` is ALSO bound on
infra-monitoring's public IP (`159.69.48.55`, plain HTTP, no TLS) — an
ingest path for a host with no tailnet at all, at the price of events in
clear; hq flags it for closing.

## 🔴 Org creation via API is CLOSED

`POST /api/0/organizations/` answers `{"detail": "Organization creation is
not open"}` (instance setting; the sole user is not a superuser). The
working recipe (verified 2026-08-31, created `oriolj`):

```bash
ssh -p 1922 root@infra-monitoring 'docker exec web-ecsgwgsccsgwk40ss0og4gsc \
  python manage.py shell -c "
from apps.organizations_ext.models import Organization, OrganizationUserRole
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(email=\"oriol@smartupsoft.com\")
org = Organization.objects.filter(slug=\"<slug>\").first() or Organization.objects.create(name=\"<slug>\")
if not org.organization_users.filter(user=u).exists():
    org.add_user(u, role=OrganizationUserRole.OWNER)
"'
```

## MCP server — LIVE since 2026-09-07

**URL: `https://infra-monitoring.armadillo-tawny.ts.net/mcp`** (tailnet-only,
Streamable HTTP, GlitchTip 6.1.8 `apps.mcp`, MCP server version 1.27.0).
Installed at **user scope in all three Claude profiles on minisforum**
(`claude`, `claude-smartup`, `claude-enacast`; `claude mcp list` → Connected,
2026-09-07). On another workstation, once per profile:

```bash
T=$(grep '^GLITCHTIP_API_TOKEN=' hq/homelab/secrets/glitchtip.env | cut -d= -f2)
for d in ~/.claude ~/.claude-smartup ~/.claude-enacast; do
  CLAUDE_CONFIG_DIR=$d claude mcp add -s user --transport http glitchtip \
    https://infra-monitoring.armadillo-tawny.ts.net/mcp --header "Authorization: Bearer $T"
done
```
The header is the API token as Bearer (`apps/mcp/auth.py` validates plain
`APIToken`s; the token's scopes gate the tools) — headless, no OAuth click,
lands in the profile's `.claude.json`, never in a repo `.mcp.json`. OAuth 2.0
+ dynamic client registration also works (URL only, then `/mcp` →
authenticate → consent at `/oauth/authorize/`; metadata at
`/.well-known/oauth-authorization-server`, endpoints `/mcp/{authorize,token,
register,revoke}`) but needs a browser per profile.

**Tools** (`apps/mcp/server.py`): `list_organizations`, `list_projects`,
`list_issues`, `get_issue`, `get_latest_event`, `get_event`, `update_issue`,
`list_alerts`, `list_monitors`, the transaction/span family (empty here —
traces go to Tempo), `list_logs` / `get_log`. Third-party servers
(`adfdev/glitchtip-mcp`, `coffebar/mcp-glitchtip`) are not needed.

**Probe** (run before blaming a client):
```bash
curl -s -o /dev/stderr -w '\nHTTP %{http_code}\n' -X POST https://infra-monitoring.armadillo-tawny.ts.net/mcp \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
# 200 + serverInfo = on · 404 HTML = GLITCHTIP_ENABLE_MCP unset · 401 = token · 000 = Serve/tailnet
```
Further calls need the `Mcp-Session-Id` response header from `initialize`.

### How it is wired, and the two traps (learned 2026-09-07)

- **The server side is three compose env lines** on the Coolify service
  (`ecsgwgsccsgwk40ss0og4gsc`, Enantena team; `x-environment`, `web` and
  `worker`): `GLITCHTIP_DOMAIN: 'https://infra-monitoring.armadillo-tawny.ts.net'`,
  `CSRF_TRUSTED_ORIGINS:` same origin, `GLITCHTIP_ENABLE_MCP: 'true'`.
  Coolify API: `PATCH /api/v1/services/<uuid>` with `docker_compose_raw`
  **base64** (the `GET` returns it plain — sending plain fails validation),
  then `POST …/restart`.
- **Trap 1 — the flag alone takes GlitchTip DOWN when `GLITCHTIP_DOMAIN` is
  http.** The MCP SDK's `validate_issuer_url` raises `Issuer URL must be
  HTTPS` for any non-`localhost` http issuer; the issuer is `GLITCHTIP_URL`
  + `/mcp` and `asgi.py` builds the MCP app at import, so every granian
  worker dies and `web` restart-loops (~10 min outage before the revert).
  No override env, same on master. Hence Tailscale Serve on the box:
  `tailscale serve --bg --https=443 http://127.0.0.1:8000` (status:
  `tailscale serve status`; off: `tailscale serve --https=443 off`).
  **Serve needs "HTTPS Certificates" enabled on the tailnet** (admin console
  → DNS) — off, `tailscale cert` says *"your Tailscale account does not
  support getting TLS certs"* and `serve --bg` hangs. Oriol enabled it on
  the EnaCast tailnet 2026-09-07; no Tailscale API key exists in hq.
- **Trap 2 — CSRF behind Serve.** GlitchTip defaults `CSRF_TRUSTED_ORIGINS`
  to `[]` and sets no `SECURE_PROXY_SSL_HEADER`, so an https `Origin` on UI
  logins would fail Django's CSRF check without the explicit origin. API
  bearer calls and MCP are exempt.
- **Symptom when the flag is unset** (Claude Code `/mcp`): "MCP endpoint
  not found" + "Dynamic Client Registration rejected (HTTP 403) … CSRF
  verification failed" — `/mcp` is the SPA's 404, so the SDK's registration
  fallback POSTs to root `/register`, GlitchTip's own signup route.
- **What did NOT change**: the ingest DSNs (`http://…@infra-monitoring:8000/<id>`)
  and `GLITCHTIP_URL` in `glitchtip.env` — the container still listens on
  8000, the Sentry API answers with the token on both hosts. Only the UI
  origin moved: **log in at the https URL** (cookies are Secure now; the
  http origin fails CSRF on login).

## Wiring apps (pointers)

SDK setup, `environment` = `oj.env`, `release` = git SHA, DSN as a
runtime-only Coolify env: `fleet-observability` §5b owns it. DSNs travel
as `SENTRY_DSN`; official Sentry SDKs work as-is against GlitchTip.
Reachability: app servers reach the DSN host over the tailnet — confirm a
new host is on the tailnet before wiring, or events vanish silently.

**Performance tracing does NOT go here** (Oriol, 2026-09-05):
`traces_sample_rate` / `profiles_sample_rate` stay 0 in every
`sentry_sdk.init`. Request/query profiling is OpenTelemetry → the host's
Alloy → Tempo on the hub (`fleet-observability` §5f) — GlitchTip's box
(2 vCPU, 76 GB, no logical backup) cannot carry transactions, and it would
split the signal off the Grafana stack. An app found with a non-zero rate
(H2A-Accountant had 0.1 hardcoded) is a finding to fix, not a precedent.

## Browser SDKs — the same-origin tunnel (decided 2026-09-07; built in Panotxa)

**The constraint**: a browser SDK posts envelopes from the *user's*
machine. `http://…@infra-monitoring:8000/<id>` resolves on the tailnet
only, so `@sentry/browser`, `@sentry/react` and the CLIENT half of
`@sentry/nextjs` / `@sentry/astro` would silently drop every event (SDKs
swallow transport errors by design). The server half is unaffected — it
runs on a tailnet host.

**The decision (Oriol, 2026-09-07): frontends stay on GlitchTip too,
behind a same-origin relay** — not a public ingest endpoint, and not
Sentry SaaS. The Sentry SDKs' `tunnel` option exists for exactly this:

```js
Sentry.init({
  dsn: "https://public@errors.invalid/1",   // placeholder, see below
  tunnel: "https://api.<project>.com/api/e/", // a URL we own
})
```

The browser POSTs the envelope to a URL we own; our server rewrites it and
forwards it to GlitchTip over the tailnet.

**Nothing internal ships in the bundle.** The client DSN is a
*placeholder* — it only has to parse (`<scheme>://<key>@<host>/<id>`). The
relay replaces the `dsn` field of the envelope's first line with the real
value from its own server-side env, so the bundle carries no MagicDNS
name, no tailnet IP, no project key and no project id. That is the
difference from Sentry's own documented tunnel example, which forwards to
whatever DSN the client sent (and therefore publishes it): **pin the DSN
server-side, never trust the client's.**

**Where the relay lives — the Vercel trap.** It must sit on a host that is
ON the tailnet. Next.js frontends deploy to Vercel and static Astro sites
to Cloudflare Pages (house rule) — **neither can reach
`infra-monitoring`**, so a route handler there is not a relay, it is a
502. Put the endpoint on the project's own Django/Go backend (Coolify,
tailnet) and give `tunnel` its absolute URL; that makes the call
cross-origin, so the relay must answer the CORS preflight
(`Access-Control-Allow-Origin: <the site origin>`, `POST`,
`content-type`). A framework route handler is a valid relay only when the
app itself runs on a tailnet host.

**Name the endpoint for the ad blockers, not for the reader.** uBlock, Brave
and Privacy Badger match `/monitoring`, `/telemetry`, `/analytics` and
anything containing "sentry" — naming the relay after what it does hands
back the events tunnelling was meant to recover. Panotxa uses **`/api/e/`**.
It also has to live under whatever prefix the project's CORS config covers
(`CORS_URLS_REGEX = r"^/api/.*$"` there), or the cross-origin preflight from
the app's own domain fails.

**Relay contract** (whatever the language):

1. `POST` only, body read as bytes and capped (~200 KB); anything else → 4xx.
2. Parse line 1 as JSON, replace `dsn` with the server-side value, re-join
   the envelope unchanged.
3. Forward to `<dsn-origin>/api/<project-id>/envelope/`, building the
   upstream headers **from scratch** — the global proxy-header rules apply
   (never copy the incoming set) — and **authenticate with the DSN's key**:
   ```
   X-Sentry-Auth: Sentry sentry_version=7, sentry_key=<key>, sentry_client=<name>/1
   ```
   🔴 **This is the step Sentry's own tunnel sample omits, and GlitchTip is
   not forgiving about it.** Sentry SaaS reads the key out of the envelope
   header's `dsn`; GlitchTip does not — it answers
   `403 {"detail": "Denied"}` and the event is gone. Verified against the
   live instance 2026-09-07: header `dsn` alone → 403; `?sentry_key=<key>`
   → 200; `X-Sentry-Auth` → 200. Rewriting the header `dsn` (step 2) is
   still right — it is what a Sentry-compatible upstream stores — but it
   authenticates nothing.
4. Per-IP rate limit. This is an unauthenticated write path into the error
   tracker; the public key never was a secret, but the relay is now the
   only thing between the internet and the project's issue stream.
5. **No auth, no session lookup** — errors happen on logged-out pages, and
   a relay that 401s loses exactly the events worth having.
6. Answer 200/204 with an empty body; never echo GlitchTip's response back
   to the browser. The exception is **shedding** (rate limit, capacity,
   breaker open): answer **429**, which the Sentry SDKs treat as a rate
   limit and back off on — the client behaviour you want while struggling.
7. 🔴 **Bound the CONCURRENCY, not just the rate** — the finding that made
   the first Panotxa build unshippable. The forward is synchronous, so an
   accepted envelope parks a request thread until the upstream answers,
   and a per-minute ceiling bounds nothing about threads in flight: at
   600/min against a 3 s stall, ~30 threads sit on monitoring while
   `/health/` queues behind them. A slow error tracker must never be able
   to take the app down.
   - a **non-blocking semaphore** (3 slots) per process — `acquire(blocking=False)`,
     shed on failure, `release()` in a `finally` or the relay wedges shut;
   - a **circuit breaker** (5 consecutive transport failures → 30 s of not
     even trying), so an outage costs one timeout per cooldown, not one per
     event;
   - both **in memory, per process**: they must hold when Redis is down,
     which is exactly when the cache-backed limits stop counting;
   - **never trip the breaker on a 4xx.** A wrong key answers instantly and
     needs to stay loud — hiding it behind a cooldown buries the
     misconfiguration this skill exists to prevent.
   The alternative (hand the envelope to a task queue) decouples fully but
   buys a broker round-trip and a backlog failure mode per browser error;
   the two guards above are the cheaper answer at this volume.
8. **A "fail-closed" cache path is a lie until you check the backend's
   error mode.** django-redis with `IGNORE_EXCEPTIONS: True` (the
   cookiecutter default in every house project) **swallows** connection
   errors and returns `None` — no exception, so an `except` branch never
   runs and `None > ceiling` raises TypeError → **500 on every relay
   request for the length of the Redis outage**, each one feeding the
   backend's own error tracker. Treat a `None` from `add()`/`incr()` as
   "no counter" and refuse. A test that mocks a *raised* exception passes
   while production does this; write the test against the real backend's
   behaviour.

**The bonus nobody plans for**: uBlock / Brave / Privacy Badger block
requests matching `*/api/*/envelope/` and `sentry-cdn` by pattern. A
same-origin path under our own name is not on those lists, so the tunnel
recovers events that Sentry SaaS would also have lost.

**What it costs**:

- **Native mobile crashes are not covered.** `@sentry/capacitor` (and
  react-native) initialise sentry-android / sentry-cocoa alongside the JS
  layer, and those SDKs have **no `tunnel` option** — with a placeholder DSN
  they would post to a host that does not exist and fail silently. Set
  `enableNative: false` whenever the tunnel is in use, and say so in the
  project's docs; the only way to get native crash reports is a DSN the
  device can actually reach.
- Events are lost while the relay's own backend is down or redeploying —
  the failures you most want to see. Sentry SaaS has that blind spot only
  for network-level outages.
- Source maps and session replay stay weak: GlitchTip's artifact-bundle
  support is thinner than Sentry's and it has no replay at all. **The
  escape hatch is Sentry SaaS for a frontend that genuinely needs them.**
  It is NOT taken today, and taking it means an account/scope decision
  (the three-realm exception in the global `CLAUDE.md`) plus a
  `sentry.env` in `homelab/secrets/`.
- In exchange, a frontend error and the backend 500 behind it stay in the
  same GlitchTip org — the whole reason for not splitting the tools.

### Reference implementation — Panotxa (LIVE 2026-09-07)

Repo `JLUV-smallbets/NutriLens`, commits `1854ed9` (relay) + `dd9d5a3`
(the `X-Sentry-Auth` fix) + `5b76bad` (concurrency + cache hardening). Copy
from here rather than from Sentry's docs sample — the sample is what
produced the 403 above. **Note that two of the three commits are fixes to
the first one**, both found by an adversarial review of code that was
already deployed and looked green: the relay answering 200 while every
event was refused, and the fail-closed branch that could not fire. Budget a
review pass for the next one.

| Piece | Where |
|---|---|
| The relay | `backend/config/error_relay.py` — DSN parse → envelope endpoint, header rewrite, two rate limits, upstream POST with headers built from scratch |
| Its route | `backend/config/urls.py`, `path("api/e/", …)` **before** the `api/` router include |
| Its setting | `GLITCHTIP_RELAY_DSN` in `config/settings/base.py`, empty = accept-and-drop |
| Its tests | `backend/tests/test_error_relay.py` — 14 cases, incl. "the client DSN is replaced, never trusted" and "fails closed when the cache is down" |
| The client | `frontend-capacitor/src/services/error-reporting.ts` (placeholder DSN, tunnel from `environment.apiUrl`, `enableNative` off) |
| The deploy notes | the repo's `DEPLOY.md` §3.4, including the `curl` probe |

**Panotxa is also the worked example of the Vercel trap**: the PWA is served
from Vercel, so the relay had to go on the Django backend at
`api.panotxa.com` (Coolify, oriolj-nc-1, on the tailnet) and the tunnel is
an absolute cross-origin URL. GlitchTip project `oriolj/panotxa` (id 12,
created 2026-09-07 by API).

**Verify the bundle, not the intention** — the point of the placeholder is
that nothing internal ships, so prove it against the DEPLOYED asset, not a
local build:

```bash
curl -sL https://app.panotxa.com/assets/index-<hash>.js -o /tmp/b.js
grep -cE "infra-monitoring|armadillo-tawny|100\.8[0-9]\." /tmp/b.js   # want 0
grep -c "api/e/" /tmp/b.js                                            # want 1
```

**A 200 from the relay is not proof the event landed** — the relay answers
200 whatever the upstream said (by design). The end-to-end check is a probe
followed by a read of the project's issues:

```bash
# POST a well-formed envelope to the relay, then:
curl -s -H "Authorization: Bearer $T" \
  "$GLITCHTIP_URL/api/0/projects/<org>/<project>/issues/?sort=-last_seen&limit=5"
```
Expect a lag of a minute or two (GlitchTip ingests through a worker). If the
issue never appears, `{project="…",service="web"}` in Loki carries the
relay's own warning with the upstream status — that is what turned the 403
into a five-minute find. Also verify the browser's real path, not just
curl's: `OPTIONS` from the site origin must return the CORS headers, since
the tunnel is cross-origin whenever the frontend is on Vercel/Pages.
