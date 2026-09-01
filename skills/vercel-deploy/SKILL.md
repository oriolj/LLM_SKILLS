---
name: vercel-deploy
description: Deploy Next.js apps to Vercel from a monorepo — the house rule (Next.js → Vercel, never a Coolify resource), CLI-in-monorepo mechanics, tenant custom domains + DNS, git-connection prerequisites. Use when deploying or updating any Next.js app (EnaArchive tenant sites and future ones), when `vercel` CLI errors with "Personal Account", "Login Connection", or creates a stray project, when attaching a tenant host to a Vercel project, or when wiring the CNAME for a Vercel-hosted host at CDmon/Cloudflare. Field notes from the EnaArchive cut-over (2026-08-29); grows with each deploy.
---

# Vercel deployments (Next.js)

**House rule (Oriol, 2026-08-29): Next.js apps deploy on Vercel** —
never as a Coolify resource. Static Astro/Starlight → Cloudflare Pages
(`cloudflare-deploy`); Django/Go backends → Coolify (`coolify-deploy`).
The Vercel app calls the backend at `app.<product>.<zone>`.

## Auth
- The `vercel` CLI on Oriol's machines is logged in as **`enacast`**
  (`vercel whoami`). No token file in `homelab/secrets` yet.
- `--scope enacast` errors with "Personal Account" — the login IS the
  scope; don't pass it.
- **Personal (oriolj) projects**: token in hq
  `homelab/secrets/vercel-oriolj.env` (`ORIOLJ_VERCEL_TOKEN`), team
  `oriolj-personal-team` (`team_Jrf8KYobc7KbxS4njYtxB8zz`, Pro, owner
  `oriolj` = oriolj@gmail.com). Agent deploy lane (verified 2026-09-01 on
  oriolj.com): `vercel link --yes --project <name> --scope
  oriolj-personal-team --token "$T"` (writes `.vercel/` and gitignores it),
  then `vercel deploy --prod --yes --token "$T"` from the repo root.

## Monorepo mechanics (verified)
- **Deploy from the repo root**, not from the app folder: Root Directory
  is resolved against the upload root. Use a `.vercel/project.json`
  (`{"projectId","orgId"}`) at the repo root (temporary, gitignored) and
  `vercel deploy --prod`.
- An unlinked `vercel git connect --yes` **creates a stray project named
  after the cwd** — link first (`vercel link`), then connect.
- **Git-connecting via API/CLI needs a GitHub "Login Connection"** on the
  Vercel account (`You need to add a Login Connection to your GitHub
  account first`) — a dashboard step for the account owner. Until it is
  done, push-to-deploy does NOT exist for that project: deploys are
  manual `vercel deploy --prod`. Say so in the product's first-deploy.md;
  do not claim push-to-deploy without a proven webhook deploy.
- Envs: `vercel env add <NAME> production` (build-time `NEXT_PUBLIC_*`
  included — they are baked at build).

## Tenant hosts
- One explicit host per tenant (`girona.enaarchive.enacast.com`), added
  with `vercel domains add <host>`; Vercel answers with the CNAME target
  (a `*.vercel-dns-016.com` name, or `cname.vercel-dns.com`) — create
  that CNAME at the zone's provider AFTER the project exists (the target
  is unknown before). A wildcard tenant host needs the zone on a DNS-01
  capable provider; CDmon cannot.
- Next.js i18n sites answer **307 → `/<locale>/`** at the root; a smoke
  test must follow redirects (`curl -L`) — a bare 307 is not "down".

## Git deploys BLOCKED — `TEAM_ACCESS_REQUIRED` (personal team, 2026-08-15 →)

Every push-triggered deployment in the personal team has shown
`readyState: BLOCKED` since 2026-08-15 (10 of 15 git projects on
2026-09-01: oriolj-com, nutrilens-capacitor, humans2agents, h2a-*,
docs.leadhunter.com, time-tracker-*, spine-guard-*). Diagnose with the
API, not the dashboard — the dashboard only says "request access":

```sh
# which deployments are blocked, and who Vercel thinks authored them
GET /v6/deployments?teamId=$TEAM&projectId=<name>&state=BLOCKED&limit=3
# the reason lives in `seatBlock` on the deployment detail
GET /v13/deployments/<dpl_id>?teamId=$TEAM
#  -> "seatBlock": {"blockCode":"TEAM_ACCESS_REQUIRED","userId":"<vercel uid>",
#                   "gitUserId":960734,"gitProvider":"github"}
# map that userId to a member record; note `confirmed` and `joinedFrom`
GET /v2/teams/$TEAM/members
GET /v2/user            # `githubLogin` of the token's own account
```

Mechanism: Vercel resolves the commit author's **GitHub login → the
Vercel account it is connected to**, and that account must be a
*confirmed* team member. Found 2026-09-01: GitHub `oriolj` (id 960734) is
connected to the Vercel account **`bikecrm`** (oriol@bikecrm.com,
created 2026-08-31 — a SmartupSoft identity), which sits in the personal
team as an unconfirmed developer (`joinedFrom.origin:
nsnb-request-access`, auto-raised when a blocked push lands); the owner
account `oriolj` has **no GitHub login connected at all**. So every
commit by `oriolj` is "a non-member".

Fixes, both Oriol's: (a) free and correct — disconnect GitHub from
`bikecrm` (Settings → Authentication), connect it to `oriolj`;
(b) `PATCH /v1/teams/$TEAM/members/<uid>` `{"confirmed": true}` — one
call an agent can make, but it **adds a paid Pro seat** and blesses a
company identity in the personal team, so never do it unprompted.
Until then, personal frontends ship only by the token lane above; a push
alone deploys nothing, whatever the deploy doc says.

## Verify
- `curl -sL` each tenant host: 200 + tenant title + the media host in the
  HTML (B2/R2 keys resolving).
- Old hosts: leave DNS alone unless links were distributed; retire the
  old Vercel project only after the new one is proven.
