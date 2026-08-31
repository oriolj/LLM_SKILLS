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
  below).
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
(Project-creation and keys endpoints follow the Sentry API shape but were
not yet exercised here — verify the first run and update this file.)

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
