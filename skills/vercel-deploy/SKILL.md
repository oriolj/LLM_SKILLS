---
name: vercel-deploy
description: Deploy Next.js apps to Vercel from a monorepo — the house rule (Next.js → Vercel, never a Coolify resource), CLI-in-monorepo mechanics, tenant custom domains + DNS, git-connection prerequisites. Use when deploying or updating any Next.js app (EnaArchive tenant sites and future ones), when `vercel` CLI errors with "Personal Account", "Login Connection", or creates a stray project, when attaching a tenant host to a Vercel project, or when wiring the CNAME for a Vercel-hosted host at CDmon/Cloudflare. Also: pinning the function REGION next to the backend (vercel.json `regions`, the `x-vercel-id` edge::function header), why `vercel logs` / the runtime-logs API cannot show past errors, and the server-side `fetch failed` trap (undici hides the cause in `error.cause.code`; narrow retry policy). Field notes from the EnaArchive cut-over (2026-08-29) and the Ramen login incident (2026-09-03); grows with each deploy. Also when caching SSR/API responses at Vercel's CDN with long TTLs and purging them on content change (Vercel-Cache-Tag, invalidateByTag, "edit does not show", "how do I purge the Vercel cache").
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

**A token CLI deploy from a git checkout is blocked too** (verified
2026-09-14, SpineGuard): `vercel deploy --prod` run inside a checkout sends
`githubCommitAuthor*` meta and Vercel applies the same seat check
(`readyStateReason: commit author doesn't have permission`). Deploy a
git-less export instead:
`D=$(mktemp -d) && git archive HEAD | tar -x -C "$D"`, then `vercel link`
+ `vercel deploy --prod` inside `$D`. (Deploys from a detached worktree also
carry the meta — use the export.) **The estate lane (2026-09-18): every Vercel project's repo has `make
deploy-prod`** (plus `deploy-app` / `deploy-landing` / `deploy-frontend` /
`deploy-docs` where a repo has several surfaces), which calls hq
`homelab/tools/vercel-deploy.sh --project <name> [--scope <team>] [--root
<app subdir>] [--alias <host>] [--check-path <path>] [--ref <commit>]`: export,
link, `vercel deploy --prod`, curl the alias, dirty-tree warning. Tokens,
per scope, in hq `homelab/secrets/`: `vercel-oriolj.env`
(`ORIOLJ_VERCEL_TOKEN`, personal team, the tool's default for `--scope
oriolj-personal-team`); EnaCast has no token, the CLI login `enacast` is the
account (pass no `--scope`); BikeCRM / SmartupSoft tokens do not exist yet
(`vercel-bikecrm.env` / `vercel-smartupsoft.env`, asked in those repos'
USER_TODO). A new Vercel project gets the target and a CLAUDE.md line on day
one (project name from `vercel project ls --scope <team>`). Also: `output: "standalone"` in
`next.config` fails on Vercel's Next 16.3 adapter
(`ENOENT .next/next-server.js.nft.json`); only set it for a Docker image.

## Verify
- `curl -sL` each tenant host: 200 + tenant title + the media host in the
  HTML (B2/R2 keys resolving).
- Old hosts: leave DNS alone unless links were distributed; retire the
  old Vercel project only after the new one is proven.

## Function region: pin it next to the backend (Ramen, 2026-09-03)

Vercel runs serverless functions in **`iad1` (US East) by default**, whatever
the edge PoP that received the request. A Next.js API proxy in `iad1` talking
to a backend in Europe crosses the Atlantic with a fresh TLS handshake per
request (~90 ms each way) — Ramen's login path failed intermittently at the
socket level on that hop while the backend was healthy.

- **Pin it in the repo, not the dashboard**: `vercel.json` →
  `{"regions": ["cdg1"]}` (Paris; `fra1` Frankfurt, `arn1` Stockholm,
  `lhr1` London). One region on Pro; multi-region is Enterprise.
- **Verify with the `x-vercel-id` response header**: `<edge>::<function>::id`.
  `cdg1::iad1::…` = Paris edge, US function (the default);
  `cdg1::cdg1::…` after the pin. Read it off a real function route
  (`curl -s -D - -o /dev/null <api route>`), not a static page.
- Pick the region by where the **backend** is (OVH Dunkirk/Gravelines →
  `cdg1`; Hetzner FSN/NBG → `fra1`), not by where the users are — the edge
  already serves them locally.

## Runtime logs are live-only from the CLI/API

`vercel logs <deployment>` (CLI 48) and
`GET /v1/projects/{id}/deployments/{dpl}/runtime-logs` both **stream lines
from the moment you connect** — neither returns what happened ten minutes
ago. Historical logs live only in the dashboard Logs tab (retention by
plan) or in a Log Drain. Consequences:

- An app must **record its own causes**: a `catch` that `console.error`s
  and returns a bare 500 leaves nothing findable after the fact. Report to
  Sentry/GlitchTip with a tag you can group on, and put the error code in
  the response body so a user-side screenshot already carries it.
- For a post-mortem, open the dashboard (browser) rather than looping on the
  CLI.

## Server-side `fetch` to your backend: "fetch failed" hides the cause

Node/undici throws `TypeError: fetch failed` for every network-level
failure; the real reason is `error.cause.code` (`ECONNRESET`, `EPIPE`,
`UND_ERR_SOCKET` = stale keep-alive socket the server already closed;
`ECONNREFUSED`, `EAI_AGAIN`, `ENOTFOUND`, `UND_ERR_CONNECT_TIMEOUT` =
connect-phase, nothing reached the server). On Vercel's warm instances a
stale kept-alive socket is a classic first-request-after-idle failure —
i.e. the login.

Pattern shipped in Ramen (`src/lib/server/upstreamFetch.ts`, reusable):
- unwrap `cause` (it may be an `AggregateError` with `errors[]`);
- **retry once**, narrowly: connect-phase codes → any method;
  stale-socket codes → only `GET/HEAD/OPTIONS` plus an allow-list of
  idempotent POSTs (login). Never retry other writes — a duplicated record
  is worse than a manual retry;
- never retry an HTTP response (a 502 from the reverse proxy is a
  response, and the backend may have processed it);
- answer **502** with `{code, message, attempts}` and `Sentry.captureException`
  with a tag (`proxy_upstream_code`) — that tag is what tells you whether to
  tune keep-alive (socket codes), pin the region (timeouts/resets), or do
  nothing (DNS).

Testing gotcha: undici refuses "bad ports" (9, 25, 6000, …) with
`fetch failed: bad port` **before** connecting — a dead-backend test must use
a closed high port (`127.0.0.1:65123` → `ECONNREFUSED`), or it exercises the
wrong branch.

## CDN cache: long TTLs + purge by tag (verified in production, EnaCast astro, 2026-09-18)

Works for ANY response of a Vercel Function (Astro/Next/other SSR pages and API
routes), not only ISR. Reference run and numbers:
`EnaCast/enacast-astro/docs/cdn-purge.md` (+ the probe route
`src/pages/api/cache-probe/index.ts`, copy it to test another project).

- **Cache:** `CDN-Cache-Control: public, s-maxage=<s>` (or `Vercel-CDN-Cache-Control`).
  **Tag:** `Vercel-Cache-Tag: a,b` on the same response (128 tags, 256 bytes each, no
  commas, case-sensitive; stripped before the browser). A tag on an uncached response
  does nothing.
- **Purge from inside the project**, no token, not billed: `@vercel/functions`
  `invalidateByTag(tag)` (next request gets the OLD copy, re-render in background:
  measured two `STALE` responses, ~1 s) or `dangerouslyDeleteByTag(tag)` (next request
  waits and gets the NEW content: `REVALIDATED`). Delete for narrow tags an editor is
  watching, invalidate for broad ones (stampede). Operator lever:
  `vercel cache invalidate --tag <t> --yes`. REST API needs a token, 16 tags per call.
- **Tags are per project + environment, not per host.** The cache KEY includes the host,
  so a multitenant site has one entry per tenant domain, and one tag purges them all.
- **The deployment id is in the cache key.** Every deploy starts with an empty CDN cache
  (refills lazily), and "I redeployed and it was fresh" is NOT a purge test. Test by
  changing the data behind the page: `MISS` → `HIT` → change → still `HIT` old → purge →
  new. Put a per-render random id in the body; it is the proof, more than the header.
- **Purge LAST.** Whatever renders right after the purge is cached for the whole TTL, so
  every cache under the page (backend caches, app Redis, and any IN-PROCESS memo that a
  purge on one instance cannot reach on another) must already be fresh or purge-coherent.
- **Browsers cannot be purged:** HTML that relies on purging sends
  `Cache-Control: public, max-age=0, must-revalidate` and lets the CDN cache.
- **Clock-driven content** (scheduled publish, expiry) fires no save, so no purge: short
  TTL on that route or a scheduled purge.
- **Running it for real (EnaCast, live since 2026-09-18, 3600 s TTL):** one policy module
  maps route families to tags AND purge scopes to tags, used by both the middleware that
  tags and the endpoint that purges, so they cannot drift (`cdnCachePolicy.ts` + unit test).
  Purge order inside the endpoint: bump a per-tenant **purge epoch** in Redis (each warm
  instance reads it once per request and drops its in-process copies of that tenant),
  delete the app-cache keys, delete the CDN tags, then a soft `invalidateByTag` ~20 s later
  via `waitUntil` for renders that started before the purge. Measured: create / edit /
  unpublish visible on the first request, ~1 s after the save.
- **Throttle the sender.** Background pipelines that save rows constantly turn into a purge
  storm (measured 30-70 a minute before, 2-9 after). Leading + trailing edge per
  (tenant, scope): first purge at once, a burst folded into ONE trailing purge; two cache
  keys and one delayed task (`enacast_backend/cache_purge/tasks.py` `send_purge`).
- **Watch the chain, or a long TTL fails silently.** With 300 s a broken purge heals itself;
  with 3600 s a rotated secret or a dead worker leaves every tenant an hour stale and nothing
  says so. What EnaCast runs: the sender records every purge outcome, a beat **canary** purges
  a reserved tenant name every 5 min through the whole path (scope chosen so the receiver
  does exact DELs, no SCAN), and a public, secret-free health view answers 503 on N
  consecutive failures / no success for 15 min / purging disabled; Gatus probes it. Treat a
  200 whose body reports a failed step as a failure. (`enacast_backend/cache_purge/health.py`)
- **Get an adversarial review BEFORE raising the TTL, not after** (we did it after). What it
  found that tests and a green end-to-end check did not: tags derived from the URL path miss
  real dependencies (an article embedding an episode, a footer linking pages), models with
  no purge strategy (theme config, streams, child rows like gallery pictures), writes that
  bypass `post_save` (M2M `.set()`, `QuerySet.update()`), a cache fill already in flight
  when the purge lands, and a purge endpoint answering 200 on a partial failure.
- **A long TTL is a bug detector:** with 300 s a missing invalidation heals before anyone
  reports it; with 3600 s it gets reported. Choose it on purpose, and keep clock-driven
  routes short.

