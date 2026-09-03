---
name: glitchtip
description: Operate the estate's GlitchTip (self-hosted Sentry-compatible error tracking on infra-monitoring) — orgs per realm, the API token, self-serving projects/DSNs via the Sentry API, and the org-creation-is-closed workaround. Use when a project needs a DSN, when creating a GlitchTip org/project, when wiring sentry_sdk in any app, or when the user mentions GlitchTip, error tracking, or Sentry DSNs.
---

# GlitchTip — the estate's error tracking

## Instance + account model

- **ONE self-hosted instance for all realms**: `http://infra-monitoring:8000`
  (tailnet-only UI/API), Coolify containers `web-/worker-ecsgwgsccsgwk40ss0og4gsc`
  on the `infra-monitoring` host.
- **Orgs partition it per realm**: `enacast` (pre-existing) and `oriolj`
  (created 2026-08-31). smartupsoft: create when first needed (recipe
  below). Projects (2026-09-02): `enacast/{enacast-backend, enacast-ai,
  leadhunter, enacast24h, encasago}`, `oriolj/{talaia, h2a-leadhunter, licita-radar, llm-index-watcher}` (licita-radar = id 8 and llm-index-watcher = id 9, both created 2026-09-02 by API, DSNs on their Coolify apps with the MagicDNS host — oriolj-nc-1 is on the EnaCast tailnet and its containers resolve `infra-monitoring`).
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

## Wiring apps (pointers)

SDK setup, `environment` = `oj.env`, `release` = git SHA, DSN as a
runtime-only Coolify env: `fleet-observability` §5b owns it. DSNs travel
as `SENTRY_DSN`; official Sentry SDKs work as-is against GlitchTip.
Reachability: app servers reach the DSN host over the tailnet — confirm a
new host is on the tailnet before wiring, or events vanish silently.
