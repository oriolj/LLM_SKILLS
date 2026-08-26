---
name: cloudflare-deploy
description: Deploy and operate services on Cloudflare — Pages (static Astro sites), custom domains on external-DNS zones, R2 S3-compatible storage, API/wrangler auth. Use when deploying a static site to Cloudflare Pages, when the user says "deploy to cloudflare pages" / "pages not workers", when wiring a custom domain onto a Pages project whose zone is NOT on Cloudflare (CNAME validation), when using the ENACAST_ Cloudflare credentials from homelab/secrets, or when touching R2 via the S3 API. Also use when a deployed static site shows localhost/dev URLs in production, or when visitors report a browser prompt like "<site> wants to access devices on your local network" (build-time PUBLIC_*/VITE_*/NEXT_PUBLIC_* fallback leaked into the artifact — section 1b). Covers wrangler direct-upload deploys, the Pages-vs-Workers rule for static sites, pre-deploy artifact gating + post-deploy smoke tests, custom-domain attach + external-DNS CNAME flow, and credential handling.
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

## 1b. Gate the dist BEFORE uploading, smoke-test the live URL AFTER

Direct upload means the artifact is whatever the operator's shell happened to
produce. Build-time env vars (`PUBLIC_*` in Astro/Vite, `NEXT_PUBLIC_*`,
`VITE_*`) are **baked into the static output**, so a var that is unset at
build time silently ships its dev fallback to the public — and nothing in the
Pages pipeline will ever tell you.

**This has already shipped once** (chat.enacast.com, 2026-08-25): the site
went live with `<script src="http://localhost:8304/v1.js">` because
`PUBLIC_APP_URL` was never set for the build. It was not a cosmetic bug —
Chrome's Local Network Access check treats a public page reaching the
loopback address space as a permission request, so **every visitor got a
prompt saying "chat.enacast.com wants to access devices on your local
network"**. On a phone that reads like the site is trying to scan the
network. The console line to recognise:

```
Access to script at 'http://localhost:8304/v1.js' from origin
'https://chat.enacast.com' has been blocked by CORS policy: Permission was
denied for this request to access the `loopback` address space.
```

Rules, in order of how much they save you:

1. **Never write an unconditional dev fallback.** Gate it on the dev flag, so
   a production build cannot inherit it:
   ```ts
   const DEV = import.meta.env.DEV;
   export const APP_URL = import.meta.env.PUBLIC_APP_URL ||
     (DEV ? "http://localhost:8304" : "https://app.example.com");
   ```
   For anything with no sane production default (an API key, a demo tenant
   key), leave it empty and have the UI *drop the feature* rather than render
   a broken promise.
2. **Gate the artifact.** A ~60-line script that greps `dist/` for
   `localhost`, `127.0.0.1`, `0.0.0.0`, `[::1]`, `192.168.*` and
   `src|href="http://`, plus "every HTML page has an https canonical".
   Reference implementation: `enachat/comercial-website/scripts/check-dist.mjs`
   in the enasuite monorepo.
3. **Make deploy depend on the gate** so it cannot be skipped under time
   pressure — `make website-deploy` = build → check → upload → verify.
4. **Smoke-test the live URL after every deploy**, not the local build:
   ```bash
   curl -fsS https://site.example | grep -qiE 'localhost|127\.0\.0\.1|src="http://' \
     && echo "LEAK" || echo "clean"
   ```
5. To reproduce a visitor-side prompt without a phone, headless Chromium
   prints the permission denial to the console:
   ```bash
   chromium --headless --disable-gpu --user-data-dir=/tmp/probe \
     --enable-logging=stderr --virtual-time-budget=8000 --dump-dom https://site.example
   ```

This is not an Astro problem or a Cloudflare problem — it is a property of
every "build locally, upload the folder" deploy. The same gate belongs in
front of Netlify/Vercel/S3 static uploads.

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

## 2b. The enacast.chat zone (main domain since 2026-08-26)

`enacast.chat` is registered at CDmon but **its DNS is on Cloudflare** (zone
`78798ebd9e4d55ea03c5ac24e3d4537d`) — the first zone in this account that is
also a product's main domain. It was moved here on purpose: the apex has to
serve Pages (impossible from CDmon, §2 rule), and Traefik needs DNS-01 for the
tenant wildcard certs (no lego provider for CDmon). Because the domain was one
day old and empty, the "migrate 150 live records" risk that blocked moving
enacast.com simply did not exist.

| Host | Serves | How |
|---|---|---|
| `enacast.chat` (apex) | comercial website | Pages `enachat-website`, CNAME→`enachat-website.pages.dev`, **proxied** (CNAME flattening) |
| `docs.enacast.chat` | public docs (Starlight) | Pages `enachat-docs`, CNAME, proxied |
| `app.enacast.chat` | Django app + panel | A → `141.95.29.64` (Coolify), **DNS-only** |
| `*.xat.enacast.chat`, `*.chat.enacast.chat` | per-town branded chats | A → `141.95.29.64` (Coolify), **DNS-only** |

- **Records for the Coolify box must be grey-cloud (`"proxied": false`)** —
  Traefik does its own LE certs and HTTP-01 fails behind the CF proxy. The
  dashboard and the API both default to proxied; set it explicitly.
- A Pages custom domain added while the zone is still `pending` (nameservers
  not yet switched) sits at `initializing` and no DNS record is auto-created —
  add the CNAME yourself; validation completes once the zone goes `active`.
- Adding the zone (`POST /zones`) is safe and inert; the nameserver switch at
  the registrar is the only step that changes what resolves, and at CDmon that
  step is human-only.

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
