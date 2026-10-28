---
name: mattermost
description: Operate the estate's self-hosted Mattermost (chat.orioljops.com) — the one chat for every scope and the channel of the Hermes bots. Use when adding a bot (a claw or one of its profiles) to Mattermost, creating teams or users, inviting people, changing a server setting, upgrading Mattermost, wiring SMTP or push, debugging "the bot does not answer on Mattermost", 429s, uploads that fail, or a red Gatus `mattermost` row, and when restoring its database. Carries the edition trap (Team Edition, never the unlicensed enterprise image), config-as-env (MM_* in compose), the Cloudflare Tunnel specifics (client IP header, one rate-limit bucket for the whole house, 100 MB bodies), what mmctl local mode cannot do (bots), the bot tool and the Hermes wiring including profile bots.
---

# Mattermost — the estate's chat and the bots' channel

Why it exists (Oriol, 2026-10-28): Slack does not let us add bots
programmatically, and he wants to own the server. Every Hermes bot (a claw,
or one of its profiles) gets a Mattermost **bot account** from one command.
**Estate state** (box, ids, which bots, teams, backups) lives in hq
[`docs/servers/mattermost.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/docs/servers/mattermost.md).
This skill holds the **mechanics**. Update it in the same turn a step
behaves differently.

## 1. Shape

- Proxmox LXC CT 106 `mattermost` (`ssh mattermost`, `root@mattermost`),
  `/opt/mattermost/docker-compose.yml` + `.env` (root 0600:
  `MATTERMOST_VERSION`, `POSTGRES_PASSWORD`). Containers
  `mattermost-mattermost-1` (port **127.0.0.1:8065** only) and
  `mattermost-postgres-1` (Postgres 17, role `mmuser`, db `mattermost`).
- Public only through a **Cloudflare Tunnel** (`mattermost`, personal
  account): native `cloudflared.service`, ingress `chat.orioljops.com` →
  `http://localhost:8065`. No port forward, ufw allows only 22. A dead tunnel
  shows as Cloudflare's 530/1033 page; a dead app shows as a 502.
- Secrets in hq `homelab/secrets/`: `mattermost.env` (DB password, the first
  admin's login) and one `mattermost-bot-<name>.env` per bot. Parse with
  grep/cut, never `source`.

## 2. The edition trap

Run the image **`mattermost/mattermost-team-edition:<version>`**, never
`mattermost/mattermost-enterprise-edition`. Without a licence the enterprise
image runs as **"Entry"**, which caps visible message history at 10,000
messages server-wide (community reports, late 2025). Team Edition has no cap.
Check after every upgrade:
`curl -s 'https://chat.orioljops.com/api/v4/config/client?format=old' | jq .BuildEnterpriseReady`
→ `"false"`, and `license/client?format=old` → `IsLicensed "false"`. Pin an
exact version (`12.0.1`), never `latest` or `release-12`, and skip `-rc`
tags.

## 3. Settings are env vars in the compose file

- Every setting we care about is an `MM_<SECTION>_<KEY>` variable
  (`MM_SERVICESETTINGS_SITEURL`, `MM_TEAMSETTINGS_ENABLEOPENSERVER`…), so a
  rebuild reproduces it. Such settings show **read-only** in the System
  Console: change the compose file, then `docker compose up -d` as root in
  `/opt/mattermost` (≈ 20 s outage, the bots reconnect by themselves).
- Read the effective value:
  `docker exec mattermost-mattermost-1 mmctl --local config get ServiceSettings.EnableBotAccountCreation`.
- What the house config sets, and why:
  - `EnableOpenServer=false`: invite-only on a public URL; an anonymous
    `POST /users` answers 403 `api.user.create_user.no_open_server`.
  - `EnableDiagnostics=false`: telemetry off.
  - `EnableBotAccountCreation=true` + `EnableUserAccessTokens=true`: both
    needed for the bots.
  - `TrustedProxyIPHeader=CF-Connecting-IP`, rate limit on and keyed by
    that header: every request arrives from cloudflared on loopback.
  - `MaxFileSize` 95 MiB: Cloudflare's free plan refuses bodies over 100 MB,
    so a bigger upload dies at the edge with a 413 that Mattermost never sees.
  - Push via `https://push-test.mattermost.com` (the free test proxy, no
    SLA; production HPNS needs a licence), `PushNotificationContents=generic`
    so no message text crosses it.
  - Email off until SMTP exists (below).
  - `EnableLocalMode=true` for `mmctl --local`.
- **One rate-limit bucket for the whole house**: every claw and every device
  at home leaves through the same public IP, so they share
  `CF-Connecting-IP`. Defaults are 10 req/s, burst 100. On 429s from bots,
  raise `MM_RATELIMITSETTINGS_PERSEC` / `MM_RATELIMITSETTINGS_MAXBURST`.
- The WebSocket (`/api/v4/websocket`) needs nothing special through the
  tunnel: 101, then a `hello` event (verified 2026-10-28).

## 4. Admin tasks: mmctl local mode and its limits

- `docker exec mattermost-mattermost-1 mmctl --local <cmd>` acts as the
  system with no token: `user create|list|deactivate`, `team list`,
  `config get|set`, `token generate` for an existing user.
- **The image has no shell** (`sh: not found`). To pass a password, expand it
  on the CT host:
  `… | ssh root@mattermost 'read -r pw; docker exec mattermost-mattermost-1 mmctl --local user create --email … --username … --password "$pw" [--system-admin] --email-verified; unset pw'`.
  It shows briefly in `docker exec`'s argv on a root-only box.
- **`mmctl --local bot create` refuses** ("This command cannot be run in
  local mode"): a bot needs an owner user. Use the API as an admin (§5).
- Teams: `POST /api/v4/teams {"name","display_name","type":"I"}` (I =
  invite-only, O = open). The estate has **one team per scope**: `personal`,
  `enacast`, `bikecrm`, `panotxa` (Oriol, 2026-10-28). Never a second
  Mattermost instance for a scope.

## 5. Bots: one command per bot

hq `homelab/tools/mattermost-bot.py` (logs in as the admin from
`mattermost.env` on each run, so there is no standing admin token):

```sh
cd ~/Syncthing/Syncthing-mobile-docs/hq
homelab/tools/mattermost-bot.py create <name> --display-name "<Name>" --description "…" --team <scope team>
homelab/tools/mattermost-bot.py list
homelab/tools/mattermost-bot.py add-team <name> <team>…
homelab/tools/mattermost-bot.py disable <name>      # its tokens answer 401 at once
homelab/tools/mattermost-bot.py sidebar             # Oriol's DMs with the bots, one category per box
```

`sidebar` (also run by `create`) groups the admin's DMs with the Hermes bots
(those with a secrets file) into custom categories by box, the part of the
username before the first `-`: `POST|PUT /users/<me>/teams/<team>/channels/categories[/<id>]`
and `PUT …/categories/order`. Categories are per user AND per team, while DM
channels show in every team, so it does every team. Putting a channel in a
custom category moves it out of Direct Messages by itself.

`create` does `POST /bots` (owner: the admin) and `POST
/users/<bot_user_id>/tokens`. It writes `homelab/secrets/mattermost-bot-<name>.env`
(`O_EXCL`; never printed) with `MATTERMOST_URL`, `MATTERMOST_TOKEN` (the keys
Hermes reads), `MATTERMOST_BOT_USERNAME`, `MATTERMOST_BOT_USER_ID` and
`MATTERMOST_TOKEN_ID`. It refuses to overwrite: to rotate, revoke first
(`POST /api/v4/users/tokens/revoke {token_id}`), delete the file, then
create a token again.

**Wiring a Hermes bot** (mechanics of Hermes in the `hermes` skill):

1. A bot joins **its scope's team only**. `MATTERMOST_ALLOWED_USERS` takes
   26-char user ids (not usernames), and an allowed user gets that bot's
   terminal. Oriol is `neizaad99bbgix6aawfjgyymhy`.
2. On the box, check that the gateway is idle: `active_agents` 0 in
   `~/.hermes/gateway_state.json`. A restart cuts a turn in flight.
3. Back up `.env`, then pipe the lines in without printing them:
   `{ grep -E '^MATTERMOST_(URL|TOKEN)=' <secrets file>; echo MATTERMOST_ALLOWED_USERS=<ids>; } | ssh oriol@<box> 'umask 077; cp -p ~/.hermes/.env ~/.hermes/.env.bak-pre-mattermost; cat >> ~/.hermes/.env'`.
4. `systemctl --user restart hermes-gateway`. That restarts every platform
   of every profile; Telegram, Slack, Discord and A2A came back in ~15 s on
   all four boxes.
5. **A profile's bot** (bruno `qa` → `bruno-qa`): the same lines go into
   `~/.hermes/profiles/<p>/.env`, then `hermes -p <p> gateway restart`
   restarts only that profile inside the multiplexed gateway. Each profile
   needs its own bot token.
   **If the profile pins its tools** (`platform_toolsets` /
   `known_plugin_toolsets` in its `config.yaml`, like pep `inventari`), add a
   `mattermost:` entry first, copied from its telegram/cli one: an unlisted
   platform is not covered by those lists and may get Hermes's default
   toolset (not tested which), which would break a narrow profile's boundary. Then ask the bot over Mattermost to list its
   tools (pep-inventari, 2026-10-28).
6. Proof in `~/.hermes/logs/gateway.log` (not the systemd journal):
   `Mattermost: authenticated as @<name>`, `WebSocket connected and
   authenticated`, `gateway.run: ✓ mattermost connected`. A profile's
   adapter logs as `platforms__mattermost__home_<hash>`.
7. Then a real round trip: as the admin, `POST /channels/direct [admin_id,
   bot_id]`, post "Reply with exactly: MATTERMOST OK", and poll the
   channel's posts. Hermes first posts two notices on first contact ("Please
   add me to teams and channels…", "📬 No home channel is set…"); the model's
   answer comes after them (≈ 30–60 s). A home channel is
   `MATTERMOST_HOME_CHANNEL=<channel id>` or `/sethome` in a channel.

## 6. What users see (questions Oriol asked)

- **"Why is Patri in the BikeCRM team?"** It isn't. DM channels have an
  empty `team_id` and show in the sidebar of every team. Mattermost DMs a
  bot's owner ("Please add me to teams and channels…") when the bot is
  created, so the admin who ran `create` gets one DM per bot. Check real
  membership with `GET /teams/<id>/members`. To hide a DM, close it in the
  sidebar; it comes back on the next message.
- **Who can DM whom**: `TeamSettings.RestrictDirectMessage` `any` (the
  default) lets every user find and DM every user and bot on the server;
  `team` limits it to people who share a team (env
  `MM_TEAMSETTINGS_RESTRICTDIRECTMESSAGE`). A bot ignores non-allowlisted
  users anyway, but with `any` they still see that it exists.
- **Push on Android/iOS**: server → push relay → APNs/FCM → the official
  app. The relay is needed because only the app's publisher holds the
  Apple/Google credentials. The app registers its device id at login and
  fetches the message itself on tap. A self-hosted relay means building and
  publishing your own app with your own push credentials: not worth it.

## 7. Health, backups, upgrade

- Health: `GET /api/v4/system/ping?get_server_status=true` (unauthenticated)
  returns `status`, `database_status` and `filestore_status`, all `OK`. That
  is Gatus group `mattermost` (hq-monitoring
  `gatus/config/shared/mattermost.yaml`).
- Backups: `mattermost-pg-dump.timer` (03:40 Madrid) → `pg_dump -Fc` →
  `/var/backups/mattermost/mattermost.dump`, checked with `pg_restore -l`;
  the NAS pulls the whole `/` at 03:50 (hq `docs/backups/mattermost-data.md`).
  Restore: Postgres alone, then `pg_restore --clean --if-exists`, then the
  `mattermost_data` volume (uploads), then `up -d`. **Never restore into an
  older Mattermost**: migrations are one-way.
- Upgrade: run `mattermost-pg-dump` first, read the release notes, bump
  `MATTERMOST_VERSION` in `.env`, then `docker compose pull && docker compose
  up -d`. Check the edition (§2) and Gatus.
- SMTP (pending): `MM_EMAILSETTINGS_SENDEMAILNOTIFICATIONS`,
  `SMTPSERVER=smtp.resend.com`, `SMTPPORT=587`, `CONNECTIONSECURITY=STARTTLS`,
  `SMTPUSERNAME=resend`, `SMTPPASSWORD=<sending-only key>`,
  `FEEDBACKEMAIL`/`REPLYTOADDRESS` on a Resend-verified domain. Until then,
  password resets go through the System Console or
  `mmctl --local user change-password`.
