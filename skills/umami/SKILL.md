---
name: umami
description: The self-hosted Umami web analytics instances — personal (stats.oriolj.com, oriolj-nc-1) and Enantena/EnaCast (stats.enacast.com, coolify-ovh-vps-1), both Coolify services — add a site and its tag, read stats, operate and back up an instance, and the API quirks of self-hosted Umami v3 (login-JWT auth, no API keys, /api/users GET is 405, password change via POST /api/users/{id}). Use when adding analytics to ANY personal (oriolj) or EnaCast/Enantena/EnaSuite site (EnaChat, EnaInbox, EnaPost, EnaJoin, EnaArchive surfaces), filling a deploy doc's analytics row, when the user mentions Umami / stats.oriolj.com / stats.enacast.com / "which sites have analytics", or when choosing an analytics tool for a new site (SmartupSoft has its own instance — check hq first).
---

# Umami — self-hosted web analytics (stats.oriolj.com · stats.enacast.com)

## Account model (Oriol, 2026-09-13)

- **Personal (oriolj) sites → this instance**, self-hosted on
  [oriolj-nc-1](../../../../Syncthing/Syncthing-mobile-docs/hq/docs/servers/oriolj-nc-1.md)
  as a Coolify **service** from the `umami` template (image + Postgres 16),
  service `vkqprndaou89yzkza5tmdzxl`, personal Coolify team. Chosen over
  Plausible CE (needs ClickHouse) and Matomo (PHP + MariaDB, cookies by
  default): one Node container, cookieless, sites added by API.
- **Company scopes do NOT use it**: Enantena/EnaCast has its OWN instance
  (`stats.enacast.com`, section below), SmartupSoft has its own Umami on
  external-1, Plausible Cloud stays parked (`plausible` skill). Accounts
  follow the scope. (Enantena's Matomo on whalehet-01 is the legacy tool
  that the new instance replaces for the EnaSuite surfaces.)
- Instance doc (ids, domain, backups, status table, the tracked-sites table):
  hq `oriolj/docs/umami.md`. Keep that table current when adding a site.
- Credentials: hq `homelab/secrets/umami-oriolj.env` — `UMAMI_URL`,
  `UMAMI_ADMIN_USER/PASSWORD` (Oriol), `UMAMI_AGENT_USER/PASSWORD` (login
  `agent`, role admin, for tools). Parse with grep/cut, never `source`.

## Enantena instance (stats.enacast.com) — created 2026-09-13

Same recipe, other account. Everything below (API quirks, adding a site,
operating) applies to both; only the ids and the credential file differ.

- Server [coolify-ovh-vps-1](../../../../Syncthing/Syncthing-mobile-docs/hq/docs/servers/coolify-ovh-vps-1.md)
  (the OVH box that already runs the EnaSuite production apps — EnaChat,
  EnaPost, EnaJoin, EnaInbox, EnaArchive — 24 GB RAM, 18 GB free at the
  time), **Enantena** Coolify team (`homelab/secrets/coolify.env`): project
  **Umami** `vamwsj6vm2ltj0xxdrhtbvrt`, service `umami`
  `0pwjsufkyczteh6ioqjiyopt` (app `tydppzfqtfs7lgy4d9frfut3`, db
  `3akozpu2athsv1rx0smfxbrp`, storage `gjbxhnwcnlgirwun7fdzov45`).
- DNS: CDmon A `stats` → `141.95.29.64` on the enacast.com zone (`cdmon.env`,
  the `cdmon-dns` skill's add-a-new-record path; set-diff verified).
- Credentials: hq `homelab/secrets/umami-enacast.env` — `UMAMI_ENACAST_URL`,
  `UMAMI_ENACAST_ADMIN_USER/PASSWORD`, `UMAMI_ENACAST_AGENT_USER/PASSWORD`
  (login `agent`, role admin). Default `admin`/`umami` rotated at creation.
- Tool: `hq/homelab/tools/umami-site.py --scope enacast …` (default scope is
  `oriolj`; the flag picks the secrets file and the `UMAMI_ENACAST_` prefix).
- Backup: volume schedule `oynvtfe96tqn3s4iwwqx79in` → Coolify S3 storage
  "Backblaze backups" `ooogcgocwc4k8og8o8w0cw8s` (bucket
  `coolify-backups-enantena`), daily 04:00 UTC, 14 kept. Note hq
  `docs/backups/umami-enacast-postgres.md`.
- Websites: **one per surface, named `<Product> · site|docs|app`** (domain =
  the hostname) — 15 created on day one for EnaChat (`enacast.chat`),
  EnaInbox, EnaPost, EnaJoin, EnaArchive (`<product>.enacast.com`,
  `docs.<product>.enacast.com`, `app.<product>.enacast.com`). The ids are in
  hq `enantena/docs/umami.md`; the EnaSuite agents tag their surfaces from
  that table (`umami-site.py --scope enacast tag <domain>` prints the tag).
- Talaia `umami-enacast/surfaces` (same three checks). Instance doc: hq
  `enantena/docs/umami.md`.
- Tag for these sites: `https://stats.enacast.com/script.js`, never
  `stats.oriolj.com` — company surfaces do not report into the personal
  instance.

## Adding a site (the whole job)

1. `hq/homelab/tools/umami-site.py [--scope enacast] add <domain> --name "<Product> · site"`
   — creates the website and prints the tag. `list` / `tag <domain>` /
   `stats <domain> --days N` / `rm`.
2. Put the tag in the site's base layout `<head>`. Astro: `is:inline` so it
   is not bundled; `defer`; nothing else.
   ```html
   <script is:inline defer src="https://stats.oriolj.com/script.js" data-website-id="<id>"></script>
   ```
   (`stats.enacast.com` for the Enantena instance — the tool prints the
   right host.)
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
- Talaia `umami/surfaces` (heartbeat, `/script.js`, `/login`) alerts on it;
  `umami-enacast/surfaces` does the same for the Enantena instance.
- First-boot timing, second data point (Enantena, 2026-09-13): `POST
  /services/{uuid}/start` → `starting:unknown` for ~40 s → `running:healthy`;
  Traefik served a self-signed cert until then (an httpx call in that window
  fails with `CERTIFICATE_VERIFY_FAILED` — not a config error, wait).
