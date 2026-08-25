---
name: cloudflare-deploy
description: Deploy and operate services on Cloudflare — Pages (static Astro sites), custom domains on external-DNS zones, R2 S3-compatible storage, API/wrangler auth. Use when deploying a static site to Cloudflare Pages, when the user says "deploy to cloudflare pages" / "pages not workers", when wiring a custom domain onto a Pages project whose zone is NOT on Cloudflare (CNAME validation), when using the ENACAST_ Cloudflare credentials from homelab/secrets, or when touching R2 via the S3 API. Covers wrangler direct-upload deploys, the Pages-vs-Workers rule for static sites, custom-domain attach + external-DNS CNAME flow, and credential handling.
---

# Cloudflare deployments

House rules and field-tested flow for Cloudflare services. Started 2026-08-25
with the EnaChat comercial Astro site → Cloudflare Pages.

## 0. House rules

- **Static sites go to Cloudflare PAGES, never Workers** (Oriol, explicit).
  Astro sites are built as purely static output (`astro build` → `dist/`) —
  no adapter, no SSR, no `@astrojs/cloudflare`. If a site seems to need SSR,
  ask before reaching for Workers.
- Credentials live in `hq/homelab/secrets/cloudflare-enacast.env`
  (age-encrypted committed copy; `ENACAST_` prefix): API token, account id,
  R2 access-key pair + endpoint. Parse with grep/cut or the ansible
  `env_get` filter — never `source` (values can carry special chars).
  Other accounts get their own `<name>.env` with their own prefix.
- wrangler auth is pure env: `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`
  exported from that file. No `wrangler login`, no OAuth state on disk.

## 1. Pages deploy (direct upload — the default)

No git integration needed; deploy the built `dist/` from wherever the build
ran (dev machine, CI):

```bash
export CLOUDFLARE_API_TOKEN=$(grep '^ENACAST_CLOUDFLARE_API_TOKEN=' $SECRETS | cut -d= -f2)
export CLOUDFLARE_ACCOUNT_ID=$(grep '^ENACAST_CLOUDFLARE_ACCOUNT_ID=' $SECRETS | cut -d= -f2)
pnpm build   # astro → dist/
wrangler pages project create <project> --production-branch=master   # once
wrangler pages deploy dist --project-name=<project> --branch=master --commit-dirty=true
```

- `--branch=master` marks the deployment as PRODUCTION (matches
  `--production-branch`); any other branch value = preview deployment with
  its own `<hash>.<project>.pages.dev` URL — useful for betas.
- `--commit-dirty=true` skips the dirty-worktree warning; direct upload
  records the commit hash but does not need a clean tree.
- Re-running `project create` on an existing project errors — it's a
  once-per-project step, deploys are just `pages deploy`.
- The project is live at `https://<project>.pages.dev` after the first
  deploy; each deploy also gets an immutable `<hash>.<project>.pages.dev`.
- **Set Astro's `site:` to the real public URL** (e.g.
  `https://chat.enacast.com`) before building — canonical URLs and
  sitemaps bake it in at build time.

## 2. Custom domain when the zone is NOT on Cloudflare

Zones can live elsewhere (enacast.com DNS is at CDmon). A **subdomain**
custom domain still works via CNAME validation; an **apex** requires the
zone to be on Cloudflare — don't promise apex domains for external zones.

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/accounts/$ACCT/pages/projects/<project>/domains" \
  -d '{"name":"sub.example.com"}'
# → status "initializing", validation method "http"
```

Then create `sub CNAME <project>.pages.dev` at the external DNS — for
enacast.com that's the CDmon API (load the `cdmon-dns` skill; its safety
rules apply). Cloudflare validates over HTTP once the CNAME resolves and
issues the cert (CA: Google Trust Services). Until then the domain sits in
"initializing/pending" — that state is normal, not an error. Check status:
`GET .../domains` on the same endpoint, or `wrangler pages project list`.

- wrangler (as of 4.x) has no `pages domain add` — the API call above is
  the way.
- List zones actually in the account first
  (`GET /client/v4/zones`) rather than assuming: e.g. the enacast account
  holds `enacasthq.com` and `radiodesvern.com`, but NOT `enacast.com`.

## 3. Coexistence with app subdomains (the enacast layout)

`chat.enacast.com` (apex of the family) serves the Pages comercial site,
while `*.chat.enacast.com` / `*.xat.enacast.com` are the EnaChat branded
per-town chat hosts on Coolify — two different targets in the same name
family. Django never routes the bare base domain (branded resolution
requires a subdomain label), so there is no collision — but any future
wildcard DNS record must NOT swallow the bare host's CNAME: at the DNS
level, the explicit `chat` record and the `*.chat` wildcard are separate
records and both must exist.

## 4. R2 (S3-compatible)

- Endpoint: `https://<account_id>.r2.cloudflarestorage.com`; auth with the
  access-key pair from the secrets file (any S3 client: rclone, aws-cli,
  boto3/httpx-signed).
- R2 keys are separate credentials from the API token — the token cannot
  talk S3, the keys cannot talk the Cloudflare API.
