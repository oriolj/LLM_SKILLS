---
name: umami
description: The personal self-hosted Umami web analytics (stats.oriolj.com, oriolj-nc-1, Coolify service) — add a site and its tag, read stats, operate and back up the instance, and the API quirks of self-hosted Umami v3 (login-JWT auth, no API keys, /api/users GET is 405, password change via POST /api/users/{id}). Use when adding analytics to ANY personal (oriolj-scope) site, filling a deploy doc's analytics row, when the user mentions Umami / stats.oriolj.com / "which sites have analytics", or when choosing an analytics tool for a new site (company scopes have their own instances — check hq first).
---

# Umami — personal web analytics (stats.oriolj.com)

## Account model (Oriol, 2026-09-13)

- **Personal (oriolj) sites → this instance**, self-hosted on
  [oriolj-nc-1](../../../../Syncthing/Syncthing-mobile-docs/hq/docs/servers/oriolj-nc-1.md)
  as a Coolify **service** from the `umami` template (image + Postgres 16),
  service `vkqprndaou89yzkza5tmdzxl`, personal Coolify team. Chosen over
  Plausible CE (needs ClickHouse) and Matomo (PHP + MariaDB, cookies by
  default): one Node container, cookieless, sites added by API.
- **Company scopes do NOT use it**: SmartupSoft has its own Umami on
  external-1, Enantena has Matomo on whalehet-01, Plausible Cloud stays
  parked (`plausible` skill). Accounts follow the scope.
- Instance doc (ids, domain, backups, status table, the tracked-sites table):
  hq `oriolj/docs/umami.md`. Keep that table current when adding a site.
- Credentials: hq `homelab/secrets/umami-oriolj.env` — `UMAMI_URL`,
  `UMAMI_ADMIN_USER/PASSWORD` (Oriol), `UMAMI_AGENT_USER/PASSWORD` (login
  `agent`, role admin, for tools). Parse with grep/cut, never `source`.

## Adding a site (the whole job)

1. `hq/homelab/tools/umami-site.py add <domain>` — creates the website and
   prints the tag. `list` / `tag <domain>` / `stats <domain> --days N` / `rm`.
2. Put the tag in the site's base layout `<head>`. Astro: `is:inline` so it
   is not bundled; `defer`; nothing else.
   ```html
   <script is:inline defer src="https://stats.oriolj.com/script.js" data-website-id="<id>"></script>
   ```
   Remove any other analytics tag in the same commit (2026-09-13: oriolj.com
   carried Plausible Cloud AND `@vercel/analytics`; both went).
3. Build, check `grep -c stats.oriolj.com/script.js dist/index.html`, deploy
   through the site's own lane (Vercel token lane / Pages `make deploy`).
4. Verify live: `curl -sL https://<site>/ | grep -o '<script[^>]*stats.oriolj.com[^>]*>'`.
5. Update: the repo deploy doc's analytics status row, the sites table in
   hq `oriolj/docs/umami.md`. One website per public hostname; apps behind a
   login and docs sites stay untracked unless there is a question to answer.

Hostname is `stats.`, not `analytics.`/`umami.` — ad-blocker lists match
those words in URLs. Umami can also rename `script.js`
(`TRACKER_SCRIPT_NAME`) if blockers start matching the path.

## API — what actually works on self-hosted v3 (verified 2026-09-13, umami 3.0.3)

- **Auth = login JWT**: `POST /api/auth/login {username,password}` →
  `{token}`; send `Authorization: Bearer`. Signed by `APP_SECRET`, no expiry
  — there are **no API keys** on self-hosted (that is a Umami Cloud
  feature). Rotating `APP_SECRET` invalidates every token.
- `GET /api/me` = who am I (`/api/auth/verify` does not exist → HTML 404).
- **`GET /api/users` answers 405**; `POST /api/users {username,password,role}`
  creates one; **change a password with `POST /api/users/{id} {password}`**
  as an admin (`/api/me/password` needs `currentPassword` and is for the
  user themself). Get the admin's id from `GET /api/me` while logged in as
  admin. A wrong id path (`/api/users/`) returns the path as plain text, not
  JSON — check the HTTP code, the first attempt on 2026-09-13 silently
  changed nothing.
- `GET /api/websites` (`{data:[…]}`), `POST /api/websites {name,domain}` →
  `{id}`, `DELETE /api/websites/{id}`.
- Stats: `GET /api/websites/{id}/stats?startAt=<ms>&endAt=<ms>` →
  `{pageviews, visitors, visits, bounces, totaltime, comparison}`.
- Collect: the tag POSTs `/api/send {type:"event", payload:{website, hostname,
  url, title, language, screen, referrer}}` with a real browser User-Agent;
  the same call from curl is the end-to-end test (a `pageviews: 1` in stats
  proves collect → store → read). `/api/heartbeat` → `{"ok":true}` is the
  liveness probe; `/script.js` must serve the tracker (contains `api/send`).

## Operating

- Coolify: service `PATCH /services/{uuid}` `urls:[{name:"umami",url:…}]`
  set the domain (`force_domain_override` if it conflicts); `POST
  /services/{uuid}/start|restart`. The service went `starting:unhealthy →
  exited → running:healthy` in ~60 s on first boot (migrations) — poll,
  don't panic at `exited`.
- Default login is `admin`/`umami` — rotate it in the same session the
  service comes up, and verify the default answers 401 afterwards.
- Backup: Coolify **volume** backup on the Postgres storage
  (`PUT /services/{uuid}/storages/{storage_uuid}/backups {frequency,
  save_s3, s3_storage_uuid, retention_*}`; `POST …/backups/run` for one
  now) → the scope's R2. Register note hq `docs/backups/umami-postgres.md`.
- Upgrade: bump the image tag in the service compose, restart, check
  `/api/heartbeat` and the login page.
- Talaia `umami/surfaces` (heartbeat, `/script.js`, `/login`) alerts on it.
