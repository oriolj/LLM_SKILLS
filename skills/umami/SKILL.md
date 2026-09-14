---
name: umami
description: The estate's ONE self-hosted Umami web analytics instance (stats.oriolj.com on oriolj-nc-1, Coolify service; alias hostname stats.enacast.com) used by EVERY scope — personal, Enantena/EnaCast/EnaSuite and SmartupSoft sites — add a site and its tag, read stats, operate and back up the instance, and the API quirks of self-hosted Umami v3 (login-JWT auth, no API keys, /api/users GET is 405, password change via POST /api/users/{id}). Use when adding analytics to any site in any scope, filling a deploy doc's analytics row, when the user mentions Umami / stats.oriolj.com / stats.enacast.com / "which sites have analytics", or when choosing an analytics tool for a new site (answer: this instance).
---

# Umami — the estate's web analytics (stats.oriolj.com, every scope)

## Account model (Oriol, 2026-09-14 — supersedes the one-instance-per-scope model of 2026-09-13)

- **ONE instance for the whole estate**: [stats.oriolj.com](https://stats.oriolj.com),
  self-hosted on oriolj-nc-1 as a Coolify **service** from the `umami`
  template (image + Postgres 16), service `vkqprndaou89yzkza5tmdzxl`,
  personal Coolify team. Personal, EnaCast/Enantena AND SmartupSoft sites all
  live here — "so we don't have to manage multiple ones". Chosen over
  Plausible CE (needs ClickHouse) and Matomo (PHP + MariaDB, cookies by
  default): one Node container, cookieless, sites added by API.
- Instance doc (ids, domain, backups, status table, the tracked-sites tables
  for all three scopes): hq `oriolj/docs/umami.md`. Cross-scope shared
  services in general: hq `shared/docs/shared-services.md`.
- Credentials: hq `homelab/secrets/umami-oriolj.env` —
  `UMAMI_URL`, `UMAMI_ADMIN_USER/PASSWORD` (Oriol),
  `UMAMI_AGENT_USER/PASSWORD` (login `agent`, role admin, for tools). Parse
  with grep/cut, never `source`.
- Tool: `hq/homelab/tools/umami-site.py list|add|tag|stats|rm` (default and
  only real scope `oriolj`; `--scope enacast|smartupsoft` are accepted and
  print a note — they map to the same instance).
- **Alias hostname `stats.enacast.com`** (since the 2026-09-14 merge): a
  second domain on the same Coolify service; CDmon A record `stats` →
  `159.195.114.24`. Exists so the enasuite tags already committed with
  `https://stats.enacast.com/script.js` keep collecting without a redeploy.
  **New tags always use `https://stats.oriolj.com/script.js`**; move old
  ones over on the surface's next deploy.
- Naming: one website per public hostname, `«Product · landing|site|docs|app»`.
  Apps behind a login get a site too (cookieless).

## History — what was merged and deleted (2026-09-14)

- **EnaCast instance** (`stats.enacast.com`, coolify-ovh-vps-1, service
  `0pwjsufkyczteh6ioqjiyopt`, created 2026-09-13): merged at the DB level —
  `website` rows copied with the SAME website ids (owner remapped to the
  personal `agent` user, `team_id` NULL) plus `session`/`website_event` (both
  3.0.3, same Prisma migration `14_add_link_and_pixel`); 22 → 37 websites.
  Recipe that worked: `COPY (SELECT …) TO STDOUT WITH (FORMAT csv)` per table
  on the source, one `psql -1 -v ON_ERROR_STOP=1` script with `COPY … FROM
  STDIN` blocks on the target, counts compared before/after. Then the alias
  (service `urls` PATCH + restart, CDmon edit, LE cert), then stop + `DELETE
  …?delete_volumes=false`. Cold copies a week on the old host
  (`/root/umami-merge/*.dump`, volume `…_postgresql-data`). Record: hq
  `oriolj/docs/umami.md` § Merge record.
- **SmartupSoft instance** (`umami.smartupsoft.com`, external-1, service
  `uwk0kkoc80kkwsoo8soc4o4w`): 8 months old, default `admin`/`umami` login,
  zero data — deleted with its volumes the same day.
- Traps met: a Traefik ACME attempt that validated against the OLD IP (DNS
  not yet propagated to LE's resolver) is not retried by itself —
  `docker restart coolify-proxy` clears the failed order and the next request
  gets the cert. `curl --resolve host:443:ip` in this Bash tool needs the
  option inline (a `$R` variable does not word-split).

## Adding a site (the whole job)

1. `hq/homelab/tools/umami-site.py add <domain> --name "<Product> · site"`
   — creates the website and prints the tag. `list` / `tag <domain>` /
   `stats <domain> --days N` / `rm`.
2. Put the tag in the site's base layout `<head>`. Astro: `is:inline` so it
   is not bundled; `defer`; nothing else.
   ```html
   <script is:inline defer src="https://stats.oriolj.com/script.js" data-website-id="<id>"></script>
   ```
   (Always `stats.oriolj.com` — the `stats.enacast.com` alias is only for
   tags that were committed before the 2026-09-14 merge.)
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
  `umami-enacast/surfaces` still probes the `stats.enacast.com` alias (fold it
  into `umami/surfaces` when convenient).
- First-boot timing, second data point (Enantena, 2026-09-13): `POST
  /services/{uuid}/start` → `starting:unknown` for ~40 s → `running:healthy`;
  Traefik served a self-signed cert until then (an httpx call in that window
  fails with `CERTIFICATE_VERIFY_FAILED` — not a config error, wait).
