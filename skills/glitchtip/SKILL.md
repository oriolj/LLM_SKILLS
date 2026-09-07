---
name: glitchtip
description: Operate the estate's GlitchTip (self-hosted Sentry-compatible error tracking on infra-monitoring) — orgs per realm, the API token, self-serving projects/DSNs via the Sentry API, the org-creation-is-closed workaround, and the built-in MCP server (flag, auth, Claude Code wiring, the CSRF-403 symptom). Use when a project needs a DSN, when creating a GlitchTip org/project, when wiring sentry_sdk in any app, when adding GlitchTip as an MCP server to Claude Code, or when the user mentions GlitchTip, error tracking, or Sentry DSNs.
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
  leadhunter, enacast24h, encasago}`, `oriolj/{talaia, h2a-leadhunter, licita-radar, llm-index-watcher, backupmaker}` (backupmaker = id 11, created 2026-09-06 by API for the two backup loops on mlrtx2 — crashes only, per-job failures stay in metrics; the DSN keeps the MagicDNS host because mlrtx2's containers resolve `infra-monitoring`) (licita-radar = id 8 and llm-index-watcher = id 9, both created 2026-09-02 by API, DSNs on their Coolify apps with the MagicDNS host — oriolj-nc-1 is on the EnaCast tailnet and its containers resolve `infra-monitoring`).
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
