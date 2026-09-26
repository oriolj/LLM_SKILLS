---
name: whatsapp-waha
description: Send and read WhatsApp messages from Oriol's own account through the local WAHA instance (WhatsApp HTTP API, WEBJS engine — headless WhatsApp Web holding one Linked-devices slot) on minisforum-um880, and transcribe voice notes locally. Use when Oriol asks to "send X a WhatsApp", "remind X on WhatsApp", "tell X that…", "what did X say", "read my WhatsApp with X", "transcribe the audio X sent me", "is X on WhatsApp", or mentions WAHA, whatsapp-web.js, the WhatsApp API, the pairing QR, or Petra/Emma/Blake writing on WhatsApp. Covers the Petra identity rule (every outgoing message names the sender as Petra, Oriol's personal AI assistant — Emma is the EnaCast one, Blake the BikeCRM one), the send-only-when-asked and confirm-the-recipient rules, the bundled `scripts/wa.py` client (status, qr, find, chats, read, send with a persona guard and a dry run, media, transcribe via oj-transcribe), the API surface learned from the live Swagger (auth, chat-id formats, messages, media download, sessions, the built-in MCP endpoint), ban-risk limits of an unofficial client, and the install/firewall facts.
---

# WhatsApp via the local WAHA (Petra)

Oriol's own WhatsApp number, driven by an agent. Unofficial (WhatsApp Web
automation, not Meta's Cloud API): treat it as Oriol typing, at human pace.

## Rules (Oriol, 2026-09-26)

1. **Every message you send identifies the sender as Petra**, Oriol's
   personal AI assistant — never impersonate Oriol. Write it in the
   recipient's language, e.g. Catalan `Hola Anna! Sóc la Petra, l'assistent
   d'IA de l'Oriol. …`, Spanish `Soy Petra, la asistente de IA de Oriol. …`,
   English `This is Petra, Oriol's AI assistant. …`. Catalan text: load the
   `catalan-writing` skill.
   - The other two assistants: **Emma** = EnaCast/Enantena, **Blake** =
     BikeCRM/SmartupSoft (the OpenClaw VMs emmaclaw/blakeclaw; see the
     `openclaw` skill). This WAHA session is Oriol's PERSONAL number, so it
     signs as Petra. Use `--persona emma|blake` only if a company number is
     ever linked as its own session and Oriol says to.
2. **Send only what Oriol asked for, to whom he asked.** His request is the
   authorization; do not add recipients, follow-ups or "friendly" extras. If
   the recipient is ambiguous (two "Anna"s, a name not found), stop and ask —
   show the candidate ids from `wa.py find`. Show the exact text you sent in
   your reply.
3. **Reminders** ("remind X to…"): send one message now, unless a time is
   given — then schedule it (CronCreate / a one-off timer) and say when it
   will go out. Never repeat a reminder unasked.
4. **Reading** chats and **transcribing** voice notes is read-only and
   needs no confirmation — but don't mark chats as read (`sendSeen`,
   `messages/read`) unless asked: the blue ticks tell people Oriol saw them.
5. Low volume only. No bulk sends, no messaging strangers cold: WhatsApp
   rate-limits new chats (`/api/sessions/{s}/capping`, and error **463** =
   "reachout timelock", `/api/sessions/{s}/timelock`) and can ban the number.

## Where it runs

| | |
|---|---|
| Host | minisforum-um880 (Oriol's desktop), docker compose in hq `homelab/whatsapp/` ([README](../../../../../Syncthing/Syncthing-mobile-docs/hq/homelab/whatsapp/README.md)) |
| URL | `http://localhost:3010` on the box, `http://minisforum-um880:3010` on the tailnet (only xps13wc, fw13, fw13pro, x1yogag9 once the ufw DOCKER-USER play is applied) |
| Dashboard / Swagger | `/dashboard` (user `oriol`, `WAHA_DASHBOARD_PASSWORD`; the dashboard also needs the API key in its server entry) · Swagger UI at `/`, raw spec at `/-json` (basic auth `WHATSAPP_SWAGGER_*`) |
| Secrets | `~/.config/waha/env` on minisforum ONLY: `WAHA_API_KEY`, dashboard + swagger user/password. Never print them; parse with grep/cut |
| State | `~/.local/share/waha/sessions` (the linked login — whoever holds it IS the account; not synced, not in git), `media/`, `downloads/`, `sent.jsonl` (wa.py send log) |
| Version | WAHA Core `2026.9.1`, engine WEBJS (Chromium + [whatsapp-web.js](https://github.com/wwebjs/whatsapp-web.js)), image `devlikeapro/waha:latest` |

From another machine, the script needs `WAHA_URL=http://minisforum-um880:3010`
and `WAHA_API_KEY` in the environment (the key file is not on the laptops).

## The client: `scripts/wa.py`

Stdlib Python, key from `$WAHA_API_KEY` or `~/.config/waha/env`.

```sh
W=~/git/oriolj/LLM_SKILLS/skills/whatsapp-waha/scripts/wa.py
$W status                      # personal: WORKING = linked; SCAN_QR_CODE = not linked
$W find anna                   # contacts + groups, accent/case-insensitive
$W chats --limit 20            # newest first, with last message
$W read 34600111222 --limit 30 # a phone number or a chat id
$W send 34600111222 "Hola! Sóc la Petra, l'assistent d'IA de l'Oriol. …"   # dry run
$W send 34600111222 @/path/msg.txt --yes                                    # sends
$W transcribe 34600111222 --last 2   # newest 2 voice notes -> oj-transcribe --stdout
$W media <chat> <message-id>         # attachment -> ~/.local/share/waha/downloads/
```

- `send` refuses text that does not contain the persona name, and is a dry
  run without `--yes`. Do the dry run, check TO and TEXT, then `--yes`.
  It shows a typing indicator for a few seconds first (WAHA's own guidance:
  start-typing → wait → stop-typing → send), then logs UTC time, chat id,
  persona, text and message id to `~/.local/share/waha/sent.jsonl`.
- `transcribe` runs `oj-transcribe` (local whisper.cpp large-v3-turbo,
  language auto-detected, nothing leaves the machine). Summarise or
  translate the text for Oriol if he asks; quote it faithfully otherwise.

## API facts (from the live OpenAPI spec, 162 paths)

- **Auth**: header `X-Api-Key: <WAHA_API_KEY>` on every `/api/*` call; 401
  without it. `/ping` and `/health` are open.
- **Session**: Core runs ONE session. Oriol's is named **`personal`** (created from the dashboard 2026-09-26; `default` no longer exists), so paths below read `/api/personal/…`; wa.py uses the one WORKING session unless `WAHA_SESSION` is set. Status flow `STARTING` →
  `SCAN_QR_CODE` → `WORKING` (or `FAILED`/`STOPPED`). Pair by
  `GET /api/personal/auth/qr?format=image` (`Accept: image/png`, the first code
  lives ~60 s, then 20 s each), or by phone code:
  `POST /api/personal/auth/request-code {"phoneNumber":"34…"}`.
  `GET /api/sessions/personal` → `me` = linked account.
  `GET /api/screenshot?session=personal` = what the headless browser sees
  (WEBJS only, good for debugging).
- **Chat ids**: `<number>@c.us` person, `<id>@g.us` group, `<id>@lid`
  anonymous "linked id" (map with `/api/personal/lids/…`), `<id>@newsletter`
  channel. Resolve a phone with `GET /api/contacts/check-exists?phone=34…&session=personal`
  → `{numberExists, chatId}` — never hand-build `@c.us` for a number you
  have not checked (`contacts-get` answers even for non-WhatsApp numbers).
- **Send text**: `POST /api/sendText {"session","chatId","text"}` + optional
  `reply_to` (message id), `mentions`, `linkPreview`. Media:
  `/api/sendImage|sendFile|sendVideo {file:{mimetype,url}|{mimetype,data(b64)}, caption}`,
  `/api/sendVoice {file, convert:true}` (ffmpeg → opus). Typing:
  `/api/startTyping`, `/api/stopTyping`. Reactions `PUT /api/reaction`.
  Edit/delete own message: `PUT|DELETE /api/personal/chats/{chat}/messages/{id}`.
- **Read**: `GET /api/personal/chats/overview?limit=` (name + last message),
  `GET /api/personal/chats/{chatId}/messages?limit=&sortOrder=desc&downloadMedia=true`
  (`limit` is required; filters `filter.timestamp.gte/lte`, `filter.fromMe`;
  `merge=true` joins @lid and @c.us copies of one contact). Contacts:
  `GET /api/contacts/all?session=personal`; groups `GET /api/personal/groups`.
- **Media download**: with `downloadMedia=true` each message has
  `media.url` = `WAHA_BASE_URL/api/files/…`; fetch it with the same
  `X-Api-Key`. `WAHA_BASE_URL` is set to the tailnet name, so on the box
  itself rewrite to the path (wa.py does).
- **Webhooks** (not configured): per-session `config.webhooks[{url, events:["message","session.status",…]}]`
  via `PUT /api/sessions/personal`. That is the path to "tell me when X
  writes" if it is ever wanted.
- **MCP**: WAHA serves an MCP endpoint at `POST /mcp` (streamable HTTP,
  same `X-Api-Key`), ~150 tools (`send-text`, `chats-get-messages`,
  `contacts-check-exists`, …). NOT registered in Claude Code on purpose: the
  Petra guard and the send log live in wa.py; use the script for sends.
- Core vs Plus: the tier is `CORE` (`/api/server/version`). Which endpoints
  are Plus-only is not marked in the spec; sending media has not been
  tested yet — verify before promising it.

## Troubleshooting

- Dashboard says "WAHA is not connected / set the right API key": the
  dashboard's server entry lacks `WAHA_API_KEY` (the server itself is fine —
  check `curl -H "X-Api-Key: …" …/api/sessions` = 200).
- `FAILED` with `auth timeout` / "Session has been logged out" in `docker logs waha` right after setup = the pairing QR was never scanned and whatsapp-web.js gave up (seen 2026-09-26, ~40 min after start). `POST /api/sessions/<name>/restart` (or delete it and create a new one from the dashboard, which is what Oriol did) → back to `SCAN_QR_CODE`; restart just before Oriol is ready to scan.
- `SCAN_QR_CODE` after it had worked = Oriol's phone unlinked the device, or
  the phone was offline ~14 days. Re-pair; the session dir keeps the rest.
- Container restarts keep the login (`restart: unless-stopped`, sessions on a
  bind mount). `make logs` in hq `homelab/whatsapp`.

## Keep this current

Verified facts first recorded 2026-09-26 (install, auth, spec, QR, dry-run
guard). Linked 2026-09-26 (session `personal`, WORKING). Verified the same day: `wa.py chats` lists the account's chats. Not yet verified: a real send, media download and transcription on
a live linked account — record the first successful run of each here.
