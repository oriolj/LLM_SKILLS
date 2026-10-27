---
name: hermes
description: Operate Hermes Agent (Nous Research) on the estate's bots ("claws", the proactive agents — the personal, EnaCast, BikeCRM/SmartupSoft and Panotxa bots plus Laia's Maia on the home Proxmox host, formerly petraclaw/emmaclaw/blakeclaw) — install shape, the CLI per user (not root), updating on the v0.22 stable channel (first-run dependency build, launcher rewrite), model and fallback switch, voice (NaN Whisper STT with a local fallback, TTS), built-in memory limits (MEMORY.md/USER.md char caps) and where larger knowledge goes, importing from OpenClaw (`hermes claw migrate` and the underlying script with --include, the overflow trap, cron jobs it cannot see), Discord and WhatsApp, the dashboard and Hermes Desktop, OS upgrades of the containers, Sign in with ChatGPT, healthchecks. Use when the user mentions Hermes, `hermes-gateway`, `hermes update`, `hermes claw migrate`, the agents' memory or skills, Pep/Enzo/Bruno (or the old Petra/Emma/Blake), a claw agent container, or connecting an agent to Discord/Telegram/Slack/email through Hermes.
---

# Hermes — the runtime of the bots (the claws)

**Hermes is THE runtime** (Oriol, 2026-10-15); OpenClaw was stopped and
disabled on all three boxes that day (its mechanics, kept for reference and
rollback: the `openclaw` skill). Estate state lives in hq: start page
[`shared/docs/bots.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/bots.md),
runtime state [`shared/docs/bots.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/bots.md#runtime-hermes),
per-box facts in `hq/docs/servers/<box>.md`. This skill is the *mechanics*;
update it the same turn a step behaves differently.

## Official sources first

When a mechanic is not here or behaves differently, read the official docs
before guessing, both copies: online <https://hermes-agent.nousresearch.com/docs/>
(web search restricted to `hermes-agent.nousresearch.com`), and the installed
tree `~/.hermes/hermes-agent/website/docs/` on any claw (source next to it).
The installed copy describes what runs; the site describes what an update would
bring. Third-party write-ups are often stale (v0.22 changed the updater, STT
and dashboard auth).

## Access

- Ubuntu LXC containers on the home Proxmox host (`192.168.7.179`),
  one per scope: CT 100 **pep** (personal), CT 102 **enzo** (Enantena/EnaCast),
  CT 101 **bruno** (SmartupSoft/BikeCRM), plus CT 103 **patri** (Panotxa,
  shared with Anna, 2026-10-17) and CT 104 **maia** (Laia's own bot,
  2026-10-19). `ssh oriol@<box>` by name from the
  workstations; each also joins a tailnet (below). Each box holds only its
  scope's (or project's) keys; never copy a token between them.
- Hermes is installed **per user (`oriol`)**. As root `hermes` is "command
  not found", and running it as root would start an empty `/root/.hermes`:
  always `ssh oriol@<box>` (or `su - oriol`). Non-interactive ssh does not
  read `~/.profile`: call `~/.local/bin/hermes` by full path in scripts.

## Install shape (v0.22)

- `~/.hermes/hermes-agent` is a **shallow git checkout** (`.install_method` =
  git) on the **`stable` channel**. `~/.local/bin/hermes` is a 2-line sh
  launcher written by v0.22 (`exec ~/.hermes/hermes-agent/.hermes/bin/hermes "$@"`),
  which runs Hermes on its own managed **Python 3.14** at
  `~/.hermes/tools/python-3.*/bin/python3 -I`. The old `./venv` (Python 3.11)
  is still on disk from before v0.22 but is not what runs.
- Config `~/.hermes/config.yaml`; secrets `~/.hermes/.env` and `auth.json`
  (its own Codex login — never print); logs `~/.hermes/logs/`; persona
  `~/.hermes/SOUL.md`; user units `hermes-gateway.service` and
  `hermes-dashboard.service`; provider `openai-codex`.
- **Running Hermes's own Python code** (scanners, tool tests): the runtime
  Python plus `hermes_bootstrap`, absolute path (with `-I`, `~` is not
  expanded inside the string):

  ```bash
  ~/.hermes/tools/python-3.*/bin/python3 -I -c 'import sys; sys.path.insert(0, "/home/oriol/.hermes/hermes-agent"); import hermes_bootstrap; <code>'
  ```

  **After an update two runtimes can sit side by side** (pep 2026-10-26:
  `python-3.14.7…` and `python-3.14.9…`): the glob then expands to two paths
  and the first python runs the second binary as a script (`SyntaxError:
  source code cannot contain null bytes`). Pick one:
  `$(ls -d ~/.hermes/tools/python-3.* | tail -1)/bin/python3`.

  Verified on pep 2026-10-15 (`tools.memory_tool_store`,
  `tools.transcription_tools`, `tools.tts_tool`, `tools.skills_guard` import).
  Below, `RT <code>` means this command.

## Updating (v0.22+, stable channel)

v0.22.0 (2026-10-14) rebuilt the updater: SemVer releases (`v0.22.2`),
source checkouts track the **`stable` channel** (latest `vX.Y.Z`) instead of
`main`; `hermes update --channel stable|canary|main`, `--set-channel`
persists, `--plan` previews (changed nothing). `hermes --version`'s
"N commits behind" on a shallow clone is not local work.

Procedure (pep v0.22.1 → v0.22.2, 2026-10-15; all five v0.22.2 → v0.22.5,
2026-10-25), one box at a time. **Scripted** in
[scripts/hermes-update-claw.sh](scripts/hermes-update-claw.sh), which does
steps 2–5 plus a clean-checkout precheck, an archive of `~/.hermes` without
code, runtimes or caches, and a config diff. Copy it to the box and run it in
tmux so a dropped ssh cannot interrupt it:
`tmux new -d -s hermes-upd "bash ~/hermes-update-claw.sh > ~/hermes-upd.log 2>&1"`.
Then wait for `DONE-OK`/`DONE-FAIL` in the log, run a one-shot turn, and move
on to the next box only if both are good:

1. Optional for a big jump: Proxmox snapshot of the CT on the host
   (`pct snapshot <ct> pre_hermes_<ver>`).
2. `systemctl --user stop hermes-gateway.service`.
3. **In a fresh shell, in the foreground**: `~/.local/bin/hermes update --yes`.
   It makes its own zip backup (`~/.hermes/backups/pre-update-*.zip`), pulls,
   rebuilds Python deps, Node deps, the TUI and the web UI, syncs bundled
   skills, migrates the config, and ends with "Update complete".
4. `systemctl --user start hermes-gateway.service` (and restart
   `hermes-dashboard.service`).
5. Verify: `hermes --version`; a real turn; `~/.hermes/logs/agent.log` shows
   `model=gpt-6.1-sol provider=openai-codex`; `assistant-healthcheck@hermes`
   result success (the update costs one failed ping per box);
   `systemctl --user is-active hermes-gateway` at the very end.

Traps:

- **The first run of a new revision builds dependencies** ("completes
  source-update dependencies": Python deps, Node deps, TUI and web UI build,
  ~1.8 GB peak). After ANY revision change the first run must be a foreground
  CLI call, never the unit start: started from systemd (`Type=notify`) the
  build blows the default 90 s start timeout, systemd kills it,
  `Restart=always` restarts it, and the build starts over in a loop.
  `hermes update --yes` in the foreground is that call. Config migration and
  skills sync then run once per revision on their own.
- **What v0.22.5's updater does, and costs** (2026-10-25, five boxes):
  - **Time:** 5–7 min per box with the gateway down.
  - **Backup:** a "Pre-update snapshot" and then a full
    `pre-update-*.zip` (≈ 800 MB, ≈ 45 s; restore with `hermes import
    <zip>`; `updates.pre_update_backup: quick|off` shrinks or skips it).
    `~/.hermes/backups/` grows by one zip per update (933 MB on pep after two),
    so prune old zips.
  - **Fleet check:** it sees the running services ("Fleet: N running
    service(s)") and has its own gateway-restart follow-up. With the gateway
    stopped first, as in the procedure, it ends with "Update follow-up
    'gateway_restart' did not finish" and "Fleet version check returned no
    rows". Both are harmless when the next step starts the gateway (`hermes
    gateway status` was clean and NRestarts 0 afterwards).
  - **Config migration:** `_config_version` 50 → 51, and text-edited keys
    and their comments survived (`cron.wrap_response`, `display.interface`).
  - **New Python runtime** (3.14.7 → 3.14.9, a new
    `~/.hermes/tools/python-*` dir). The old one stays (≈ 400 MB) and still
    runs every process started before the update: a **long-lived interactive
    `hermes` (a mosh TUI) keeps the old code until it is reopened**.
  - It also re-prepares the pinned `cua-driver` (Computer Use) every run.
- **Bundled skills a bot edited stop receiving upstream updates**: the
  updater keeps them "user-modified" (pep: 6 on 2026-10-25, among them
  `hermes-agent`, `google-workspace`, `email-inbox-triage`). Review them with
  `hermes skills list-modified` / `hermes skills diff <name>`. To take
  upstream again, run `hermes skills reset <name>` (keeps the bot's copy as
  the new baseline) or add `--restore` (back to stock).
- **`hermes update --check` is not read-only**: it installed the "default
  tools" `agent-browser` and `cua-driver` (opt out:
  `hermes pm install --without <tool>`). Use `--plan` to look.
- Rollback: the updater's `pre-update-*.zip` and the Proxmox snapshot exist;
  neither restore has been exercised.
- The v46 → v50 config migration warns that platform `homeassistant`
  references unknown toolset `hermes-homeassistant` (Home Assistant moved to
  a catalog plugin in v0.22). Harmless while unused; `hermes tools`
  reconfigures it.
- **Home Assistant = the official catalog plugin `homeassistant`**
  (2.0.1, `hermes plugins install homeassistant --yes-deps --enable`; the
  gateway hot-reloads plugins, tools arrive next session). The four tools
  (`ha_list_entities`, `ha_get_state`, `ha_list_services`, `ha_call_service`)
  appear only once `HASS_TOKEN` is in `.env` (`HASS_URL` defaults to
  `http://homeassistant.local:8123`); then `hermes tools` per platform. The
  same token also enables the gateway platform, but it forwards no
  `state_changed` events until `platforms.homeassistant.extra` has
  `watch_domains` / `watch_entities` / `watch_all`. `ha_call_service` blocks
  `shell_command`, `command_line`, `python_script`, `pyscript`, `hassio`,
  `rest_command`; give the bot a non-admin HA user's token. (Pep, 2026-10-21.)

**Pre-0.22 boxes (legacy, none left on 2026-10-15).** A v0.19–v0.21.5 box
compares against `main` ("13012 commits behind"): never a bare `hermes
update` there. Stop the gateway, back up `~/.hermes`, `git fetch --no-tags
origin tag <tag> && git checkout <tag>`, `VIRTUAL_ENV=$PWD/venv
~/.hermes/bin/uv pip install -e ".[all]"`. Up to v0.21.5 the post-update
steps came from [scripts/hermes_post_checkout.py](scripts/hermes_post_checkout.py)
(it calls `_finish_pulled_update`, gone in v0.22); to land on v0.22 skip it and
make the first run a foreground `hermes --version` (trap above). That first
v0.22 run **rewrites `~/.local/bin/hermes`** (our old symlink) into the sh
launcher, and the NEXT `hermes` call in the SAME script died with
`SyntaxError`, which under `set -e` left enzo and bruno with the gateway down
for ~10 min (2026-10-15). End the script after that call and continue from a
new ssh session. Rollback on that line was `git checkout <old tag>`, the same
`uv pip install`, and the config copy.

## Model switch

Default `gpt-6.1-sol` via `openai-codex`, fallback `gpt-5.6-luna` (Oriol,
2026-10-15):

```bash
H=~/.local/bin/hermes
$H chat -Q --provider openai-codex -m gpt-6.1-sol -q "Reply with exactly: HERMES OK"   # test first
$H config set model.default gpt-6.1-sol
# fallback: top-level list; `hermes fallback add` is interactive only, and
# `fallback_model:` (still in its docs) is NOT a recognised key
grep -q '^fallback_providers:' ~/.hermes/config.yaml ||   # appending twice = duplicate top-level key
  printf '%s\n' 'fallback_providers:' '- provider: openai-codex' '  model: gpt-5.6-luna' >> ~/.hermes/config.yaml
$H fallback list; systemctl --user restart hermes-gateway.service
```

Then check `agent.log` for `model=gpt-6.1-sol provider=openai-codex`.

## Account limits and "is this the subscription or the API?"

- `hermes usage` (`/usage` in a chat): provider, plan, rate-limit windows,
  reset time and banked resets, e.g. `openai-codex (Pro) · Weekly: 99%
  remaining · resets in 6d 18h · 3 resets banked (/usage reset)`. Read-only.
- Subscription vs API, three checks: `~/.hermes/auth.json` pool entry
  `openai-codex` with `auth_type: oauth` and `base_url
  https://chatgpt.com/backend-api/codex` (ChatGPT sign-in; the API would be
  `api.openai.com` + an `sk-` key); `agent.log` "OpenAI client created …
  provider=openai-codex base_url=https://chatgpt.com/backend-api/codex";
  no `OPENAI_API_KEY`/`VOICE_TOOLS_OPENAI_KEY` in `~/.hermes/.env`.
  Verified on all three claws 2026-10-15: one shared ChatGPT **Pro** login
  (same plan, same window, same reset on every box).
- **Sign in with ChatGPT**: Hermes support is open PR #128926, not released;
  verdict in hq `shared/docs/bots.md` § Sign in with ChatGPT (not yet;
  the device code stays).

## Custom model providers (NaN as an option)

`providers.<name>: {api: <OpenAI-compatible base URL>, key_env: VAR (or
api_key: "${VAR}"), discover_models: false, models: {id: {context_length: N}}}`
in `config.yaml`; the key goes in `~/.hermes/.env`. Use it per run with
`hermes chat --provider <name> -m <model>` (also `custom:<name>`; `agent.log`
shows `provider=custom`) or `/model <name>:<model>` in a chat; `model.default`
is untouched. Ours: `nan` → `deepseek-v4-flash`, `glm5.3-flash` (2026-10-15,
verified a plain turn and a tool call on pep). Skip models that call tools in
XML (NaN's Qwen/Gemma).

## Voice: speech-to-text and text-to-speech

Box-level config (provider, vocabulary lists, key file, TTS voice per agent):
hq `shared/docs/bots.md` § Voice notes and audio. Mechanics:

- **Hermes STT providers**: `local` (faster-whisper), `groq`, `openai`,
  `mistral`, `xai`, `elevenlabs`, `deepinfra`; `stt.providers.<name>: {type:
  command, command: "… {input_path} {output_path}", format: txt, timeout: N}`
  adds your own. A command provider runs with Hermes's secrets scrubbed from
  its env (`env_passthrough: [VAR]` passes one) and gets `{language}`
  defaulting to `en`: leave it out of the command to keep auto-detect.
- **Why not `openai` + `STT_OPENAI_BASE_URL` pointed at NaN**: Hermes cuts
  long audio only by size (25 MB for `openai`) and by a per-model duration
  table (`whisper-1` 600 s, `gpt-4o*-transcribe` 450 s); an unknown model id
  such as NaN's `whisper` gets no duration cap, and `stt.openai.timeout`
  defaults to 60 s. NaN's proxy answers 524 when one request passes ~2 min
  (NaN's page says ~1x realtime; measured ~12x on 2026-10-15), so long voice
  notes fail.
- **Ours** (all three, 2026-10-15): `stt.provider: nan` → command provider
  `~/.local/libexec/nan-stt {input_path} {output_path}`, source hq
  `homelab/tools/nan-stt.py`:
  - ffmpeg → ≤ 90 s Opus pieces; each to NaN `whisper` (large-v3), **never a
    language**, with a names-only vocabulary `prompt`; 6.5 s between
    requests (10/min limit); 429/5xx backed off, a 524 retried at most once.
  - urllib, not curl, so the key (`~/.config/nan/stt.env`) never sits on a
    command line; it sends a real User-Agent (NaN's Cloudflare front 403s
    `Python-urllib`).
  - Per piece, when NaN fails or returns no text: local faster-whisper
    `tiny` int8 (~350 MB, seconds) in Hermes's runtime Python, with
    `vad_filter=True` and **no prompt**: tiny parrots a prompt back on
    silence ("Plaud, Plaud…", "see you in the next video").
  - Both empty → a `[no speech detected …]` line, so the output is never empty.
  - Local model install: `hermes pm install --extra stt-whisper` (goes into the
    managed runtime, not the old venv).
  - Test through Hermes: `RT 'from tools.transcription_tools import transcribe_audio as t; print(t("/tmp/x.mp3"))'`
    → `provider: nan`. Or run `~/.local/libexec/nan-stt` on a short ffmpeg clip.
- **An empty transcript is a failure to Hermes**, and the agent then
  improvises: a command provider that writes an empty file gets "wrote no
  output file … and produced no stdout", the gateway hands the agent the raw
  audio, and Pep `pip install`ed `openai-whisper` and ran large-v3 on CPU in
  its 4 GB container (2026-10-15: 3.8 GB RSS, swap thrash, box unreachable,
  host load 20). Defences in place: the never-empty output above, and a
  MEMORY.md rule that transcription is automatic and local models are off
  limits. Saying "use Whisper V3" in a voice note reads as an order to run it.
- **TTS on an OpenAI-compatible server** (NaN kokoro): `tts.provider:
  openai`, `tts.openai.{base_url, model, voice, api_key}`. Put the key in
  `tts.openai.api_key`, not `VOICE_TOOLS_OPENAI_KEY` (other OpenAI voice
  features read that env var and would send it to OpenAI).
  `tts.openai.language` is sent as `lang_code` (Kokoro-FastAPI style); the
  text_to_speech tool has no per-call voice, so one voice = one language per
  agent. Test: `RT 'from tools.tts_tool import text_to_speech_tool; …'`.

## Dashboard, look and messaging

- **Posting to a platform from a script or a `--oneshot` CLI turn: `hermes send`** (`--to slack:<channel or DM id>` / `telegram` / `slack:#name`, `--file`, `--json`; `hermes send --list slack` lists the targets, DMs included). It reuses the gateway's bot credentials, needs no LLM and no running gateway. A `chat --oneshot --source claude-code` turn has NO native send-message tool: Enzo then reached for the Nous Portal Slack connector and stopped at its OAuth link (2026-10-21). Never authorise that connector to get around it; have the bot write the text to a file and run `hermes send` (verified 2026-10-21 on enzo: two Slack DMs, `success: true` + `message_id`).
- **Web dashboard**: `hermes dashboard` (default `127.0.0.1:9119`; `--host`,
  `--port`, `--no-open`); a non-loopback bind always requires an auth
  provider (password or OAuth). Our `hermes-dashboard.service` binds
  `0.0.0.0:9119` with password auth (creds in hq
  `homelab/secrets/hermes-dashboards.env`; `/api/status` says
  `auth_required: true`). Its Chat tab runs the real TUI over a pty.
- **Dashboard plugins** (user): `~/.hermes/plugins/<name>/` needs a
  `plugin.yaml` (name/version/description) AND `hermes plugins enable <name>`;
  a folder with only `dashboard/manifest.json` is silently ignored. Restart
  `hermes-dashboard`; check `GET /api/dashboard/plugins`; bundles are served at
  `/dashboard-plugins/<name>/dist/index.js`. Ours: `claw-name` (agent name in
  `header-left` + tab title), source hq `homelab/tools/hermes-dashboard-claw-name/`.
- **CLI/TUI look = skins**, separate from dashboard themes: `display.skin` in
  `config.yaml` (`/skin x` = this session only); custom `~/.hermes/skins/<name>.yaml`
  overrides `colors` and `branding.agent_name/welcome/response_label/prompt_symbol`
  and inherits the rest from `default` (the gold one). Ours: pep/enzo/bruno,
  source hq `homelab/tools/hermes-skins/`. Check:
  `RT 'from hermes_cli import skin_engine as s; s.init_skin_from_config({"display":{"skin":"pep"}}); print(s.get_active_skin().name)'`
  → `pep`.
  **The status bar is not skinnable** (v0.22.2, checked 2026-10-19): the classic
  CLI (the default; `display.interface: tui` picks the Ink one) hardcodes
  ` ☤ <model>` as its first segment (`_status_bar_segments` in
  `hermes_cli/cli_status_bar_mixin.py`). `branding.agent_name` does not reach it,
  whatever the skins docs suggest, and `display.status_bar.fields` only hides
  segments; their order is fixed. The only config lever is the model label: it
  shows the shortest `model.aliases` / `model_aliases` key that maps to the
  running model id. That is a `/model` alias pressed into service as a label, and
  it vanishes as soon as the model changes.
  Wanted when it becomes possible (Oriol, 2026-10-19; rejected the alias as too
  hacky): an icon per agent first in the bar, Pep 👤, Enzo 🎤, Bruno 🚲,
  Patri 🌽, Maia 👧. Parked in hq `homelab/tools/hermes-skins/README.md`;
  after a `hermes update`, check whether skins gained a status-bar icon/prefix.
- **Messaging needs the `messaging` extra**: without it a pairing QR prints
  "QR code unavailable … run: hermes pm install --extra messaging". Install
  with `hermes pm install --extra messaging`, restart the gateway (done on all
  three 2026-10-15).
- **WhatsApp in Hermes is its own code**, not WAHA: a built-in Node bridge on
  `@whiskeysockets/baileys` (`scripts/whatsapp-bridge/`, QR pairing as a
  linked device, unofficial, ban risk, docs say use a dedicated number), or
  `whatsapp_cloud.py` for Meta's official Cloud API (Business account + a
  public webhook). Pairing a number WAHA already holds just adds a second
  linked device.
- **Discord (researched 2026-10-03, not enabled anywhere)** — outbound
  websocket only, so LAN-only is fine. One Discord application per box in
  that scope's account (a token runs in only one gateway). Oriol, in the
  Developer Portal: Bot → **Public Bot off**, **Message Content intent on**
  (Server Members only for username/role allowlists), reset token, invite with
  `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot+applications.commands&permissions=274878286912`;
  he writes the token on the box himself:
  `ssh -t oriol@<box> 'read -rsp "token: " T; printf "DISCORD_BOT_TOKEN=%s\n" "$T" >> ~/.hermes/.env; chmod 600 ~/.hermes/.env'`
  and hands over the app id + his numeric user id. Agent then: the
  `messaging` extra (else the gateway lazy-installs `discord.py[voice]`),
  appends `DISCORD_ALLOWED_USERS=<id>` (numeric; no allowlist = everyone
  denied) to `.env` without printing it, sets top-level
  `unauthorized_dm_behavior: ignore` (default `pair` answers strangers with a
  pairing code), restarts. Defaults: `DISCORD_REQUIRE_MENTION=true` (DMs
  exempt), `DISCORD_AUTO_THREAD=true`, `DISCORD_ALLOW_BOTS=none`. Verify:
  journal `[discord] Connected as …`, no `PrivilegedIntentsRequired` / `token
  rejected` / `No Discord access policy`, a DM gets 👀 → ✅ + reply, a second
  account gets silence. Allowed users get full tool/terminal access:
  allowlist Oriol only. Source: `website/docs/user-guide/messaging/discord.md`.

## A2A: agents calling each other (bundled plugin, v0.22)

Hermes ships an A2A (Agent2Agent v1.0) plugin, `plugins/platforms/a2a/`,
doc `website/docs/user-guide/messaging/a2a.md`. Inbound: Agent Card at
`/.well-known/agent-card.json`, JSON-RPC at `POST /`; the task runs in the
LIVE gateway session (same memory and tools) and the reply is the result.
Outbound: toolset `a2a` (`a2a_call`, `a2a_discover`, `a2a_list`,
`a2a_history`, `a2a_orchestrate`), peers in `config.yaml` `a2a_agents`.
Set up on the claws 2026-10-18 (hq `shared/docs/bots.md` § A2A). Mechanics
learned:

- **Inbound turns on with `A2A_PORT` in `~/.hermes/.env`** (the plugin's
  `is_connected` reads it); our config keeps platforms at top-level
  `platforms:`, not the doc's `gateway.platforms`, so no YAML edit is needed.
- **The env is read once at gateway start**, and the order is enforced:
  `A2A_HOST` is ignored (localhost bind, warning) unless `A2A_PEER_TOKENS`
  or `A2A_BEARER_TOKEN` is set, and a non-loopback bind with no
  `A2A_TRUSTED_PEERS` serves but 403s every task. Write all of `A2A_PORT`,
  `A2A_HOST=<LAN IP>`, `A2A_AGENT_NAME`, `A2A_PUBLIC_URL`,
  `A2A_PEER_TOKENS=name:tok,…`, `A2A_TRUSTED_PEERS=name,…`, then restart
  once. Proof: `agent.log` `A2A: serving … (REMOTE (bearer auth)) as '<name>'`
  and `ss -ltn | grep 9900`. Some boxes already had a stray
  `A2A_AGENT_NAME` line: check `grep ^A2A_ .env` before appending.
- **Caller tokens**: `auth: {type: bearer, token: "${A2A_TOKEN_TO_X}"}` in
  `a2a_agents` works: `load_config` expands `${VAR}` from `.env`. Writing
  that block from a shell: `$(…)` strips trailing newlines, so concatenated
  peer blocks fused lines and broke `config.yaml` (pep, 2026-10-18, restored
  from the backup at once). Write the block from a file and parse
  `config.yaml` with `yaml.safe_load` right after.
- **Outbound is per platform**: `hermes tools enable a2a --platform <cli|telegram|slack>`.
  Never `--platform a2a` unless you want an inbound task to call further
  peers (chaining with no person in the loop).
- Hermes runs on the host: plain ufw rules (`allow from <caller IP> to any
  port 9900`) restrict who connects. Test: card readable, wrong token 401,
  right token 200 (`GetTask` with a bogus id is a harmless probe), a
  non-caller times out; then one `a2a_call` per edge.
- Security built in: per-peer identity from the token, untrusted-peer
  framing and prompt-injection filtering, credential-shaped strings scrubbed
  from replies, audit `~/.hermes/a2a_audit.jsonl`, anti-loop
  `A2A_MAX_PINGPONG_TURNS` (5). It does NOT know scopes: the "a peer is not
  Oriol" rule lives in each agent's SOUL.md § Boundaries.

## MCP servers (remote, OAuth)

`hermes mcp catalog` lists Nous-approved entries (manifests under the install tree,
e.g. `sentry` → `https://mcp.sentry.dev/mcp`, `auth: oauth`); `hermes mcp install <name>`
writes the entry. From a non-interactive ssh the install's tool probe fails ("MCP OAuth …
non-interactive environment and no cached tokens") but the entry IS saved, enabled, with no
tool filter. The owner then runs `hermes-<bot> mcp login <name>` (prints the authorization
link; over ssh it explains the callback / paste-the-redirect step) or uses the dashboard's
Authorize. After login, drop write tools (the agent acts with the authorizing user's
permissions). `hermes mcp configure <name>` is an interactive checklist; from a script append
`tools: {exclude: [...]}` under `mcp_servers.<name>` in `config.yaml` instead (names or globs;
`include` wins over `exclude`), then `hermes mcp list` shows "-N excluded". `hermes mcp test
<name>` lists the server's tools non-interactively. Then restart the gateway and use a NEW
session (`/reload-mcp` in a running one). **Sentry's MCP** has 15 tools: exclude `update_issue`
(status/assignment), `analyze_issue_with_seer` (starts a paid Seer run) AND the generic pair
`search_sentry_tools` + `execute_sentry_tool` (a dispatcher that can call any catalog tool,
writes included, so excluding `update_issue` alone is not read-only). Verified on bruno
2026-10-17 (install) and 2026-10-18 (login by Oriol, the four excluded, read from a fresh
session: org, projects, latest issue, no status tool).

## From a dev machine: CLI wrappers and Hermes Desktop

Setup: hq `homelab/ansible/roles/development/tasks/hermes-desktop.yml`, run
with the no-sudo `ansible-playbook playbooks/hermes-desktop.yml -l <host>`
(`-c local` on the controller; `--tags hermes-desktop` in site.yml does the
same but asks the sudo password), and `shared/docs/bots.md`. Traps:

- **`hermes-pep` / `hermes-enzo` / `hermes-bruno`** (hq dotfiles
  `local-bin/hermes-claw`): when stdin AND stdout are ttys, `mosh <host> --
  sh -c 'exec "$HOME/.local/bin/hermes" "$@"'` (2026-10-20; mosh-server execs
  without a shell, so no `~` and no login PATH); otherwise `ssh -T <host>
  '~/.local/bin/hermes <args>'` as oriol, so `hermes-pep chat -Q -q "…"` is
  clean in scripts and keeps its exit code (mosh needs a terminal and drops
  it). `HERMES_SSH=1` forces ssh. Use them instead of hand-rolled ssh quoting.
- **`hermes-<bot>-ssh`** (hq dotfiles `local-bin/hermes-claw-ssh`): `mosh
  oriol@<host>`. mosh on a claw needs ufw `60000:61000/udp` and a UTF-8
  locale matching the client's `LANG`: the Ubuntu containers ship only
  `C.utf8`, so mosh-server dies with "needs a UTF-8 native locale" until
  `locale-gen en_US.UTF-8` (generate only; leave the system `LANG`, the
  gateway's env, alone). Testing mosh headless: give `script` a sized pty
  (`stty rows 40 cols 120`, else mosh-client asserts `s_height > 0`), a
  `TERM`, and `</dev/null` (it eats a heredoc's remaining lines).
- **Hermes Desktop on Linux is a source install** (`scripts/install.sh
  --include-desktop`; no Linux package is released: the platform-support doc
  says Linux desktop packaging is disabled in the release workflow).
  **On Arch, use it, not the AUR** (Oriol, 2026-10-15, "official way"): the
  AUR `hermes-agent` / `hermes-agent-desktop` are community builds (single-digit
  votes, an anonymous Desktop packager) that patch the runtime, install as
  root into `/opt`, disable Hermes's own updater and lag a release; the
  `-bin` variants are one person's CI artifacts. The pinned official
  installer trusts only Nous, runs as the user and self-updates on `stable`. Without `--branch
  release/X.Y.Z --commit vX.Y.Z` it clones **`main`** (canary) yet labels the
  install `stable`, and `hermes update --channel stable` then refuses the
  "rollback"; the tag commit is not on `main` (`--commit` alone fails
  `commit_not_on_branch`). Fix: `git checkout --detach vX.Y.Z`, `hermes
  --version` (rebuilds deps), `hermes desktop --build-only --force-build`.
- Bulk (~3.7 GB checkout + Electron build, ~1 GB `~/.hermes/{tools,installs,cache}`)
  lives in `~/not-important/homelab/hermes`, symlinked from `~/.hermes` BEFORE
  the installer runs; `~/.hermes/hermes-agent` is a symlink to the checkout,
  because Desktop looks for the runtime there. Use `--non-interactive
  --skip-browser --skip-computer-use` (no wizard, no gateway service, no
  Chromium). The installer edits `config.fish` only when no `fish_add_path
  …/.local/bin` line is there.
- **The app-menu entry is written by `hermes desktop`, not by the installer's
  desktop stage** (`hermes_cli/linux_desktop_entry.py`; fw13pro 2026-10-15:
  built, no entry). `hermes desktop --build-only` on a built app checks the
  content stamp, writes `com.nousresearch.hermes.desktop` + the hicolor icon
  and does not launch; the play runs it (`creates:` the entry).
- Launching from a shell needs the session's `DISPLAY` / `WAYLAND_DISPLAY`
  (else Electron exits "Missing X server"); the menu entry runs `hermes
  desktop --skip-build`. Log: `~/.hermes/logs/desktop.log`.
- **Connection registry** `~/.config/Hermes/connections.json` (schema v2,
  `apps/desktop/electron/connection-registry.ts`; labels unique
  case-insensitively, a malformed entry is quarantined). Ansible's
  `files/hermes-desktop-connections.py` pre-seeds `{id: host, kind: ssh,
  label, host, user: oriol}` only when new. Close the app first: it rewrites
  the file from memory.
- An SSH connection opens a control master, finds `hermes` on the remote
  (falls back to `~/.local/bin/hermes`), checks the version, spawns its own
  dashboard on the remote's 127.0.0.1 and forwards it. Nothing to configure
  or expose on the containers for Desktop.

## After changing an agent's memory, persona or skills: let the agent review it

Oriol, 2026-10-15: whenever we (Claude Code / Codex, from outside) add or edit
an agent's instructions — `~/.hermes/memories/MEMORY.md` / `USER.md`,
`~/.hermes/SOUL.md`, a skill under `~/.hermes/skills/`, config that changes
behaviour — **ask that agent itself to review the result**, then apply what
holds up. The agent reads its own context the way it will be used; we do not.

1. Built-in checks first (read-only): `hermes doctor` (no `--fix`),
   `hermes config check`, `hermes skills list` (the skill is `enabled`),
   `hermes curator status`.
2. Send the review as in the `send-to-claws` skill, as a **fresh one-shot**
   (`--oneshot`, no `-c` thread: a running chat loaded memory, SOUL and skills
   when it started and will not see the edits; tell Oriol to send `/new` on a
   messaging channel too). The prompt:

   > From a Claude Code session for Oriol: <what changed today>. Review
   > ~/.hermes/memories/MEMORY.md, USER.md, ~/.hermes/SOUL.md and <skill> as the
   > agent who uses them: right format and shape for you (memory entries, the §
   > separators, skill frontmatter, length vs the caps)? Anything unclear,
   > duplicated, stale, contradictory, or in the wrong place (memory vs skill vs
   > SOUL)? Do NOT change any file. Reply with concrete findings and the exact
   > edits you propose, max ~20 lines.

3. Apply the clear fixes yourself (back up first), show Oriol the judgement
   calls, and re-ask if the change was large.

Why it pays (first run, 2026-10-15): the reviews found a migrated "Whisper
model: medium" line contradicting the new transcription rule (the confusion
that had just made Pep run large-v3 itself), our "never run Whisper locally"
wording forbidding Hermes's own tiny fallback, identity duplicated between
MEMORY and SOUL, and SOUL's stock "these files are your memory" ignoring the
Mnemosyne provider.

## Unattended runs refuse flagged commands (one-shot, `-q`, cron)

With no user present to approve, Hermes BLOCKS every terminal command its
approval detector flags (`tools/approval_detection.py`): `rm -r` ("recursive
delete"), a script run through a heredoc, and `execute_code` itself. The agent
then reports "blocked" and does nothing (Bruno, 2026-10-17: a skill's setup
block ended in `rm -r "$T"`). Skill code blocks the agent must run alone avoid
those forms: temp files from `mktemp`, removed with `trap 'rm -f …; rmdir …' EXIT`,
and say "run as one plain bash command". Check each block before installing:
`RT 'from tools.approval_detection import detect_dangerous_command as d; print(d(open("/abs/block.sh").read()))'`
→ `(False, None, None)`. Blocked attempts show in `~/.hermes/logs/agent.log` as
`BLOCKED: Command flagged as dangerous (<reason>)`.

## Liveness and boot

- User timer `assistant-healthcheck@hermes.timer` runs
  `~/.local/libexec/assistant-healthcheck hermes`, which pings the
  healthchecks.io URL in `~/.config/assistant-monitoring/hermes.url` (or
  `/fail`). The probe requires BOTH `hermes-gateway.service` active AND
  `~/.hermes/gateway_state.json` saying `"gateway_state": "running"` with
  `pid` equal to the unit's `MainPID` (since 2026-10-15). Still blind to a dead
  model login: only a real turn proves that. An outage during an update pages.
- The script is hand-installed on each box (source hq
  `homelab/tools/assistant-healthcheck/`); the previous version is
  `~/backups/assistant-healthcheck.pre-2026-10-15`.
- Boot: `hermes-gateway.service`, `hermes-dashboard.service` and the hermes
  timer are enabled user units with linger on. **OpenClaw cannot start**: its
  unit file and drop-in were moved to `~/backups/openclaw-retired-units/` and
  `openclaw-gateway.service` plus `assistant-healthcheck@openclaw.{timer,service}`
  are **masked** (2026-10-15). To bring it back: `systemctl --user unmask …`,
  move the files back to `~/.config/systemd/user/`, `daemon-reload`,
  `enable --now`.
- `~/.bashrc` still sources OpenClaw's bash completion from `~/.openclaw/`;
  harmless, but it errors if `~/.openclaw` is ever renamed (`hermes claw
  cleanup`): drop that line then.

## Memory: what Hermes keeps and where bigger knowledge goes

- Built-in memory is two small files injected every turn:
  `~/.hermes/memories/MEMORY.md` (cap `memory.memory_char_limit`, 2200 on our
  boxes) and `USER.md` (`user_char_limit`, 1375), entries joined by `"\n§\n"`
  (`ENTRY_DELIMITER` in `tools/memory_tool_store.py`). Persona is
  `~/.hermes/SOUL.md`.
- **A one-shot turn from Claude Code does not edit skills** (2026-10-18,
  pep and bruno: "this session's instructions prohibit editing skills"; the
  cause in Hermes was not traced). Write the skill from outside and let the
  agent review it (the self-review section above).
- **Never patch Hermes's own code on a claw** (Oriol, 2026-10-25: "i dont
  want to modify hermes code"). A bot's features live in its plugins
  (`~/.hermes/plugins/`), scripts and skills, and use only what stock Hermes
  exposes. `git status --porcelain` in `~/.hermes/hermes-agent` must be empty.
  Check it before every `hermes update`, because a dirty tree makes the
  update refuse or drop the changes. On 2026-10-25 enzo had nine changed or
  new core files: a Slack audio-transcript proof its time-tracking tool
  imported, written by the bot on 2026-10-23. Reverting meant changing the
  tool first, because it imported the patched module on every call. Grep
  `~/.hermes/scripts ~/.hermes/plugins` for the patched module names before
  you `git checkout`. When a feature truly needs a core hook, it is Oriol's
  call: an upstream PR or a plugin hook, never a local edit.
- **`display.interface: tui` on every claw, and on every new one** (Oriol,
  2026-10-25: "set tui as default"). It sits under `display:` in each
  profile's `config.yaml` and is read at launch. With it, a bare `hermes` on
  a terminal opens the TUI. `--cli` forces the classic REPL, and with no
  terminal (cron, pipes, `ssh -T`) Hermes always stays classic
  (`_resolve_use_tui`, `hermes_cli/main_tui_launch.py`, v0.22.2). **Trap:**
  with a terminal, `chat -q "…"` also opens the TUI, with the query
  prefilled, and stays open instead of printing and exiting. A one-shot must
  therefore run without a terminal or with `--cli`. hq's `hermes-claw`
  wrapper does this by sending `-q`/`-z` calls over `ssh -T`.
- **`cron.wrap_response: false` on every claw, and on every new one**
  (Oriol, 2026-10-25). By default every cron delivery is wrapped as
  `Cronjob Response: <name>` / `(job_id: …)` / `-------------`, the message,
  then `To stop or manage this job, send me a new message (e.g. "stop
  reminder <name>").` (`cron/scheduler_delivery.py`, v0.22.2). One key per
  profile, not per job; the scheduler rereads `config.yaml` on each delivery,
  so no restart. Set it as a text edit under `cron:` (`hermes config set`
  can rewrite the file and drop its comments); check with `hermes config get
  cron.wrap_response`. Verified 2026-10-25 on pep with a one-shot test (`hermes cron
  create --name t --script t.sh --no-agent --deliver telegram --repeat 1 1m`:
  it ran within a minute, Telegram got only the script line, and the job
  deleted itself after its one run). A pre-v0.22 install may lack `cron:`, so add the
  section. Note: the old `~/.hermes/hermes-agent/venv` exists only on boxes
  installed before v0.22 (pep, enzo, bruno); patri and maia have none, so run
  one-off Python checks through the `hermes` CLI there.
- **`memory.write_approval: false` on every claw, and on every new one**
  (Oriol, 2026-10-17: "memory write approval should be off"). With `true`
  the agent's own memory tool waits for an approval, and on bruno
  (2026-10-17) the approval step itself failed with "Unknown Mnemosyne tool",
  so nothing was saved. Set it with `hermes config set memory.write_approval
  false`, restart `hermes-gateway`, check with `hermes config get
  memory.write_approval`. The setting gates only the memory tool: editing
  the files directly is always possible, and safe while the gateway runs,
  because every tool write rereads the file under a `.lock` and refuses on
  drift. The injection scan below still runs on every write.
- Every entry passes `_scan_memory_content` (injection/exfil patterns) at
  write AND at load; a flagged entry is dropped from the prompt with a
  warning. Scan curated text before installing it:
  `RT 'from tools.memory_tool_store import _scan_memory_content as s; print(s(open("/abs/path/x").read()))'`
  (`None` = clean).
- Leave headroom under the caps (we installed ~1.2 KB of 2.2 KB): the agent
  adds its own entries and an over-cap file blocks every further addition.
- One external memory provider can sit beside it (`hermes memory status`).
  Ours: **`mnemosyne`** (plugin `hermes-mnemosyne` 0.4.0 under
  `~/.hermes/plugins/`, data `~/.hermes/mnemosyne/`, local SQLite +
  multilingual MiniLM embeddings) since 2026-07-23; upstream
  `mnemosyne-oss/mnemosyne` (3,420 stars on 2026-10-15, passes the >1k rule).
  It recalls by similarity, so facts the agent must always apply belong in
  MEMORY.md or a file skill, not only there.
- Anything that does not fit the caps goes into a **file skill**
  (`~/.hermes/skills/<category>/<name>/SKILL.md`), loaded on demand. A
  category is a folder with a one-line `DESCRIPTION.md`; `hermes skills list`
  shows a new skill immediately, and new skills and memory take effect in a
  NEW session (no gateway restart). Check a hand-written skill with the
  built-in scanner (verdict SAFE → allowed):
  `RT 'from tools.skills_guard import scan_skill, format_scan_report; from pathlib import Path; print(format_scan_report(scan_skill(Path("/abs/dir"))))'`.
- Our three agents each have `~/.hermes/skills/knowledge/agent-knowledge/`
  (since 2026-10-15): the long tail of what OpenClaw learned, grouped by
  topic. Keep it current there, not in the overflow files. Imported OpenClaw
  skills land in `~/.hermes/skills/openclaw-imports/`.

## Cron, skills, background review, curator: how they really work

Read from the v0.22.2 code on enzo (`d923a5eb`) and the v0.22.4 docs,
2026-10-22. The estate's rules built on these facts (drift, poisoning, one
source for Enzo and Bruno) are hq
[bots.md § Running the bots well](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/bots.md#running-the-bots-well-drift-poisoning-shared-behaviours-2026-10-22).

**Cron** (`~/.hermes/cron/jobs.json`, ticker = a thread in the gateway, 60 s;
gateway down = nothing fires):
- The agent creates, edits, pauses and removes jobs from any chat with the
  `cronjob_manage` tool (renamed from `cronjob` in v0.22.0), **with no
  approval**. The only checks: an injection scan of the prompt, scripts must sit
  in `~/.hermes/scripts/`, a credential-exfil `base_url` guard. `paused=true` /
  `hermes cron create --paused` is opt-in. Inside a cron run the tool is denied
  unless `cron.allow_agent_scheduling: true` (default false; ours: default).
- A job is `{prompt, skills, script, no_agent, deliver, schedule, model,
  enabled_toolsets, workdir, …}`; no per-job timezone (top-level
  `timezone:`, ours `Europe/Madrid`). **The prompt is a frozen copy written
  when the job was made**: it does not follow later skill or memory changes,
  and it often restates who gets the result (bruno's "Pendientes" prompt says
  Telegram while `deliver` is a Slack channel, 2026-10-22).
- An agent run is a fresh session with SOUL + MEMORY/USER, the attached
  `skills` loaded in full before the prompt, toolsets from
  `platform_toolsets.cron` (or the job's `enabled_toolsets`), never
  `messaging`/`clarify`/`cronjob`, `approvals.cron_mode: deny`, no background
  review. The final answer is delivered (`[SILENT]` suppresses it).
- `no_agent` + `script`: no LLM; non-empty stdout is delivered verbatim,
  empty = silent success, non-zero exit = a watchdog alert.
- Missed runs: one catch-up run, then the schedule (`cron.catch_up_missed`).
- **Changing a job from outside** (used 2026-10-22, enzo and bruno):
  - `hermes cron create "<cron>" "<prompt>" --name … --script <rel> [--no-agent] --deliver … --failure-deliver … --workdir … --paused --paused-reason "…"`
    and `hermes cron edit <id> --prompt "$(cat file)"`.
  - Neither command has a toolsets flag. Set `enabled_toolsets` with the
    job API in the runtime:
    `RT 'from cron.jobs import update_job; print(update_job("<id>", {"enabled_toolsets": ["file"]})["enabled_toolsets"])'`.
  - `hermes cron remove <id>` deletes a job.
  - A Slack DM target for `deliver` is `slack:D…`: take the `D…` part of
    the `dm` entry for that person in `~/.hermes/channel_directory.json`
    (`platforms.slack`, id `D…:<thread>`).
- **Pattern for a job whose model reads untrusted text: split it, and give
  the model purpose-built tools only** (2026-10-22, tightened 2026-10-23 after
  Bruno's review):
  - The agent job gets a plugin toolset of its own and nothing else:
    `enabled_toolsets: ["<toolset>", "no_mcp"]`. In the catch-up, that is
    "read the evidence" (paged) and "submit the draft" (once). `["file"]`
    is not enough: `write_file` reaches anything `oriol` can write, this
    job's own scripts included, and the next `no_agent` run executes them.
  - **`no_mcp` is required.** Without it, a per-job toolset list gets every
    enabled MCP server merged in (`_merge_mcp_into_per_job_toolsets`).
    Bruno's `["file"]` job was quietly getting Sentry. `[]` means zero
    toolsets, with no MCP either.
  - **Gate the tools to the job in code.** `registry.dispatch` passes
    `task_id` to a handler that accepts it. In a cron run it is
    `cron:<job id>:<execution>`. The session ContextVar
    `HERMES_CRON_SESSION` is `"1"` (`get_session_env`), and it reaches the
    tool threads (`DaemonThreadPoolExecutor` copies the context). Require
    both, and keep the model's arguments apart from them. The model cannot
    set either, but this gates "runs of that job", not one execution.
  - Trusted code picks the target (file, report). A tool takes no path,
    and refuses unknown arguments in the handler: a schema's
    `additionalProperties: false` alone is not enforcement.
  - Put only a gate in the gateway. Do the work in a subprocess with the
    venv python and a fixed cwd: it stays testable, and generic module
    names (`digest`, `runtime`) do not collide inside the gateway.
  - A `no_agent` script job sends what was submitted, then verifies it.
  - Reference: hq `homelab/tools/bot-workflows/catchup/` (plugin
    `catchup-draft`, `scripts/draft_tool.py`, `plugin/verify_dispatch.py`),
    on Enzo and Bruno.
- **Plugin toolsets are ON by default on every platform** (v0.22,
  `_enabled_plugin_toolsets`): one is off only when it is listed in
  `known_plugin_toolsets.<platform>` and absent from that platform's
  `platform_toolsets` list. That is how `enacast_time_tracking` stays out of
  everything but Slack.
  - **`hermes plugins enable <name>` also adds the toolset to every
    platform list in `platform_toolsets`.** It still matters: it is what
    makes the running gateway load the plugin ("Gateway reloaded plugins",
    no restart; tools reach the next session).
  - **Do not fix that with `hermes tools disable --platform …`.** It rewrites
    the lists. Composites such as `hermes-discord` / `hermes-signal` become
    frozen explicit lists, it adds a `cron:` list, and it moves other plugin
    toolsets between lists. Seen on enzo, 2026-10-23.
  - What worked: back up `config.yaml` first. Run `plugins enable`. Then
    restore the backup, adding only the plugin to `plugins.enabled` and the
    toolset to `known_plugin_toolsets` for cli, slack, telegram, discord,
    cron, a2a, api_server and webhook. A config with comments needs a text
    edit, because `yaml.safe_dump` drops them; check that the edit loads
    equal to the intended dict.
  - Verify without a model, on the box, from `~/.hermes/hermes-agent` with
    the venv python:
    `cron.scheduler._resolve_cron_enabled_toolsets(job, cfg)`, then
    `model_tools.get_tool_definitions(..., skip_tool_search_assembly=True)`
    for the real tool names. `_get_platform_tools(cfg, platform)` gives
    each platform's set. Call the tools with
    `registry.dispatch(name, args, task_id=…)`, setting
    `gateway.session_context._VAR_MAP["HERMES_CRON_SESSION"]` for a cron
    caller.
  - **Plugin tools reach the model through the tool-search bridge**
    (`tool_search` / `tool_describe` / `tool_call`). The bridge is scoped
    to the session's grant: from a catch-up-only scope, `tool_call` on
    `terminal`, `write_file` or `read_file` answers "a directly-listed
    tool", and on `a2a_call` it answers "not available in this session".
    Verified with `handle_function_call(..., enabled_toolsets=…)` on enzo,
    2026-10-23.
- Ad-hoc Python on a box: the managed runtime started with `-I` has no
  `python-dotenv`; `~/.hermes/hermes-agent/venv/bin/python` (the v0.21
  leftover) has the project dependencies. Which interpreter the scheduler
  uses for `no_agent` scripts was not traced.
- Inspect: `hermes cron list|status|runs|doctor`; output in
  `cron/output/<id>/*.md`. Change jobs with the CLI or tool, not by editing
  `jobs.json` (the docs say so; the gateway rewrites it).

**Skills** (`~/.hermes/skills/<category>/<name>/SKILL.md`, agentskills.io format):
- The prompt carries only the index (name + description); `skill_view`
  loads the body. `skills.auto_load: [..]` pins bodies into every session.
  So the **description decides whether a skill is ever used**.
- Load order on a name clash: project dirs, `~/.hermes/skills`,
  `skills.create_dir`, `skills.external_dirs`. **External dirs are NOT
  write-protected**: `skill_manage` edit/patch works there; only file
  permissions stop it. On our bots `oriol` is in the docker group, which is
  root inside the container, so root ownership stops accidents, not the bot.
  The approval gate also lives only in `skill_manage`: a skill written with
  the file tools or the shell is not gated.
- `skill_manage` (create/edit/patch/delete/write_file/remove_file).
  **`skills.write_approval: true` on all our bots** (seen 2026-10-22; memory's
  is false): every write, foreground (`origin: assistant_tool`) or background
  (`background_review`), is staged in `~/.hermes/pending/skills/<id>.json` and
  waits. Review only with slash commands, in a CLI/TUI chat or a messaging
  chat: `/skills pending`, `/skills diff <id>`, `/skills approve <id|all>`,
  `/skills reject <id|all>`. No expiry, no dashboard route. Not gated:
  `write_file`/`patch` on the files directly (issue #117818), and our own scp.
- Bundled skills sync at gateway start and update; a locally edited one is
  skipped forever (`.bundled_manifest` hashes), a deleted one stays deleted.
- Agent-written skills are scanned only with `skills.guard_agent_created:
  true` (default false); skill bodies are never scanned at load. Run the
  scanner yourself on what you install (Memory section above).

**Background review** (the self-improvement loop): a forked agent after a
delivered turn, every `memory.nudge_interval` user turns (10) and when a turn
used `skills.creation_nudge_interval` tool calls (ours 15) without a skill
write. It writes memory and proposes skills. **Memory `patch`/`remove` from it
are staged in `pending/memory/` even with `memory.write_approval: false`**;
only `add` lands. Off: set the interval to 0. Not run for cron.

**Curator** (default on, every 168 h): archives (never deletes) skills marked
`created_by: agent` in `.usage.json` after 14/30 days unused; pinned skills and
skills named by a cron job are protected; ours, hub and external skills are
untouched. `hermes curator status|pin|restore|rollback`; every skill change by
any actor is in `skills/.curator_ledger.jsonl` (missing on bruno, 2026-10-22).

**Injection scanning**: memory writes (blocked) and memory at load (dropped
from the prompt), context files (AGENTS.md etc. from a checkout: blocked;
SOUL.md and files in HERMES_HOME: warning only, still loaded), cron prompts
(blocked). Tool output from `web_*`, `browser_*`, `mcp_*` is wrapped as
untrusted; **`terminal` and file reads are not** (issue #98587), so a vault
note read with `cat` reaches the model as plain text. Hermes's own SECURITY.md:
the only real boundary is the OS; scanners and approvals are heuristics.

**Prompt order**: SOUL, guidance, `auto_load` skills, platform hints;
then context files; then the skills index, MEMORY, USER, the memory
provider's block, plugin sections, the date. Built once per session (a
running chat does not see edits: `/new`).

## Profiles: several agents on one install

Read from the installed docs on enzo (v0.22.2:
`website/docs/user-guide/{profiles,multi-profile-gateways,profile-distributions}.md`,
`reference/profile-commands.md`) and the A2A plugin code, 2026-10-22;
rechecked against v0.22.5 on pep and the online docs, 2026-10-27. **The online
`profiles` page still says "each profile runs its own gateway process"**: that
is stale. `multi-profile-gateways.md` (online and installed) is the authority:
one host gateway, below. **First profile: `inventari` on pep (2026-10-27)**, the
home-inventory agent; source and lessons in hq
`homelab/tools/hermes-profiles/pep-inventari/README.md`, mechanics learned below
(§ "Building a narrow profile").
**When we use them** (the estate rule): hq
[bots.md § Profiles](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/bots.md#profiles-several-agents-on-one-bot-box-2026-10-22).

**What a profile is.** A separate Hermes home, `~/.hermes/profiles/<name>/`
(the default profile is `~/.hermes` itself). It has its own `config.yaml`,
`.env`, `SOUL.md`, `memories/`, sessions and `state.db`, `skills/`, `cron/`,
logs, `plugins/` and gateway state. The switch is just
`HERMES_HOME=~/.hermes/profiles/<name>`. Code, the managed runtime and
plugin dependencies are shared: `hermes update` updates them once and syncs
bundled skills into every profile. A profile whose `config.yaml` does not
parse breaks dependency preparation for the whole install.

**What a profile is NOT: a sandbox.**
- Same UNIX user, so the agent's terminal and file tools can read every
  other profile's `.env`, memory and sessions, and the default's
  `auth.json`.
- Tool subprocesses keep the real `HOME` (`terminal.home_mode: auto`), so
  `~/.ssh`, `gh`, `gws` and the git credentials are shared. Opt out per
  profile with `terminal.home_mode: profile`, which runs tools with
  `HOME=<profile>/home`; you then set those up again inside it.
- Only a separate box or UNIX user is a boundary. Inside the gateway the
  isolation is per profile (`.env` scope, allowlists, outbound bot, MCP
  connections), but that protects against mix-ups, not against a hostile
  agent.

**Commands** (`hermes -p <name> <anything>`, or the alias `<name> <anything>`
in `~/.local/bin/`):

| Command | What it does |
|---|---|
| `hermes profile create <name>` | Blank profile, bundled skills seeded; then `hermes -p <name> setup` |
| `hermes profile create <name> --clone` | Copies `config.yaml`, `.env`, `SOUL.md`, skills, `MEMORY.md`/`USER.md` and `plugins/` (with the memory provider's config). Sessions, `state.db` and cron start empty. `--clone-from <src>` picks the source |
| `--clone-all` | Everything except history, `state.db`, backups, checkpoints and **cron** (never cloned: two gateways would run every job twice) |
| any clone | Never copies **messaging channels**: bot tokens, allowlists, `platforms:`, pairing. `--clone-channels` overrides, but one token can only be polled by one profile |
| `hermes profile list` / `show <name>` / `use <name>` | `use` is a sticky default for plain `hermes`, like `kubectl use-context`: avoid it on a bot box, where scripts assume default |
| `hermes profile rename` | Renames a profile, its alias, and removes the old gateway service. Renaming `default` only sets `display_name` in `~/.hermes/profile.yaml` (the ID stays `default`) |
| `hermes profile delete <name>` | Stops it, removes service and alias, **deletes its data**; asks for the name |
| `hermes profile export <name>` / `import <file> [--name]` | A `.tar.gz` with keys stripped (`/export`, `/import` in a chat) |
| `hermes profile describe` / `create --description "<role>"` | The kanban routing description |
| `create … --sync-imports` | Carries `import-sync.json` so the clone can `import-agent --sync` external agent trees |
| `hermes profile migrate-identity` / `purge-identity` | Retry a rename/delete identity step that failed |
| `hermes profile install <git-url>` / `update` | Profile distributions: SOUL, config, skills, cron (installed paused) and MCP from a git repo. Unsigned; not for us |

**Logins.** Codex / Claude / xAI OAuth tokens are single-use refresh tokens,
so they are **shared, never copied**:
- a profile reads the root `~/.hermes/auth.json`, and its refreshes are
  written back there;
- all profiles therefore draw on the same ChatGPT subscription;
- `hermes -p <name> auth add <provider>` gives a profile its own login;
- static API keys are copied by a clone.

**Gateways.** Since v0.22 **one gateway process serves every profile**
(`gateway.multiplex_profiles`).
- **Default and how it switches on (v0.22.5):** an unset
  `gateway.multiplex_profiles` is settled by the default gateway at each boot.
  It multiplexes, and writes `true` into the default's `config.yaml`, only when
  the fold is safe: two or more profiles, no secondary running its own gateway,
  no duplicate bot token, no port-binding platform without a `/p/<profile>/`
  route. Otherwise it serves default only and prints a boxed warning (also in
  `hermes gateway status`, the `hermes update` summary and the dashboard's
  `multiplex_standalone_reason`). `true` is the only valid value: `false` is
  retired and rewritten to `true` with a notice. patri and maia already carry
  `true`.
- **No per-profile gateways:** `hermes -p <name> gateway install|start|run`
  (and the service step of `setup`) refuses with exit 78. The escapes are
  `--force` (a fleet split across UNIX users or a `HERMES_HOME` outside
  `profiles/`) and `gateway.standalone: true` in that profile's own config, a
  temporary shim kept while the WhatsApp bridge, Relay on secondary profiles
  and dashboard scoping are still unfinished. `hermes gateway migrate
  --multiplex` folds an existing per-profile fleet.
- **Same unit:** our `hermes-gateway.service` and the healthcheck keep
  covering everything.
- **Its own bot tokens per profile:** each profile needs its own Telegram,
  Slack or Discord token. The same token in two profiles is parked as
  `duplicate_credential`. `gateway.profile_routes` can route chats of ONE
  shared bot (by `user_id`, `chat_id`, `guild_id`) to different profiles.
- **Sessions:** keyed `agent:<profile>:…`; the default keeps `agent:main:…`.
- **HTTP inbound** (`api_server`, webhooks) comes in on the default's
  listener under `/p/<profile>/…`.
- **A2A is the exception:** it is not on that listener. A profile's own
  `A2A_PORT` in its own `.env` binds its own port (scoped read; issue
  #122126). It needs its own port, its own ufw rule, and its own
  `A2A_PEER_TOKENS` / `A2A_TRUSTED_PEERS`.
- **Cron:** each served profile's own cron runs in the one process.
  `hermes -p <name> cron status` names the host gateway.
- **Restarts:** restarting the default gateway restarts every profile's
  bots, and `hermes gateway restart` asks first. **Parking** takes one profile
  offline: `hermes -p <name> gateway stop` writes `<profile>/gateway.parked`
  (persists across restarts, can be pre-created to install a profile offline;
  its cron jobs stop too), `start` removes it, `restart` re-reads its config.
  The host rescans every 30 s, so a marker added or removed by hand also
  applies. `status` says `parked`; the dashboard's Stop/Start do the same.

**Dashboard.** It works at machine level, with a profile switcher
(`?profile=<name>` in the URL). Our basic-auth login therefore manages every
profile on the box. Its Profiles page "Set as active" only changes the sticky
CLI default; edit a profile through the switcher.

**Desktop Bot Mode.** A "Bot" in Hermes Desktop is a profile with roster
metadata (title, avatar) and a pinned Bot Chat. Every Bot is a profile; a
profile driven only from the CLI or a gateway stays a plain profile. Not our
"bots" (the claws), which are boxes.

**A directory counts as a profile** only with an identity file in it
(`config.yaml`, `.env`, `SOUL.md`, `profile.yaml`, `auth.json` or `state.db`).
`terminal.cwd` is separate from the profile home: set an absolute one for a
predictable start folder (SOUL.md enforces no workspace boundary).

**Same-machine collaboration** between profiles (checked against the docs 2026-10-27):
- **Delegation with `profile_routes`**: the catalog plugin `advanced-delegation` (not bundled;
  install in the profile that delegates) sets `delegation.backend: profile_routes` with
  `delegation.backends.profile_routes.profiles: [{name, description}]` (the allowlist) and an
  optional `default`; a task that picks no profile runs on the parent's own model. The child runs
  as the target profile (model, credentials, skills, SOUL, terminal policy) but **keeps the
  parent's toolset** (developer guide `delegation-provider-plugin.md`): a narrow profile whose
  boundary is its toolset does not keep that boundary as a delegated child, and the child does not
  get the target's plugin tools unless the parent's lists name them. Listing a profile also hands
  the parent that profile's credentials.
- **Kanban**: a card assigned to a profile spawns `hermes -p <name> chat -q` with that profile's
  own config and tools; asynchronous (dispatcher tick, result as a card comment).
  `hermes profile create … --description` feeds kanban routing.
- **A2A**: a served profile's own `A2A_PORT` in its own `.env` is read scoped (v0.22.5 adapter
  code: "a secondary multiplex profile must not borrow the default profile's bridged A2A_PORT");
  the online multi-profile page lists port-binding platforms without `/p/<profile>/` ingress as a
  preflight blocker, which an explicit `multiplex_profiles: true` bypasses. Not tested on a
  secondary profile yet.

**Building a narrow profile (learned on pep `inventari`, v0.22.5, 2026-10-27):**
- `hermes profile create <name> --description "…"` on a box with a running gateway is **served
  at once, no restart** ("served now by the running multiplexed gateway"), and the default's
  `config.yaml` gains `gateway.multiplex_profiles: true` by itself (expected diff). A blank profile
  copies the default's `model:` block; `.env` is empty; `~/.local/bin/<name>` wrapper.
- Harmless warning on every profile load: "Plugin 'basic' tried to register dashboard-auth
  provider … from profile scope …; ignoring" (dashboard auth belongs to the launch scope).
- **A CLI one-shot for a served profile runs inside the host gateway** (`tui_gateway.ws`,
  session `agent:<name>:local:…`, logged in the profile's `logs/agent.log`), so it sees the
  gateway's view of the profile, not a fresh load.
- **The host loads a profile's plugins when it first serves it.** A plugin copied in later is
  invisible ("unknown name(s): <toolset>" warnings) and `hermes -p <name> gateway restart` does
  NOT rediscover it. `hermes -p <name> plugins disable <p>` then `enable <p>` makes the running
  gateway reload plugins ("Gateway reloaded plugins — deferred: tools (next session)") without
  touching the default's bots. `enable` rewrites `platform_toolsets`, so copy `config.yaml`
  aside first and put it back after.
- **Explicit `platform_toolsets` + the tool-search bridge = no plugin tools.** With
  `tools.tool_search.enabled` at its default, plugin tools are deferred behind
  `tool_search`/`tool_call`; if the explicit lists do not include the bridge, the model gets
  neither and says the tools are unavailable (`tool_turns=0`). For a handful of tools set
  `tools: {tool_search: {enabled: "off"}}` in that profile.
- Verify the resolved set without a model: `HERMES_HOME=<profile> venv/bin/python` →
  `hermes_cli.plugins.discover_plugins(force=True)`, then
  `model_tools.get_tool_definitions(enabled_toolsets=[…], quiet_mode=True)` for the real names
  and `hermes_cli.tools_config._get_platform_tools(load_config(), "<platform>")` per platform.
- Make `known_plugin_toolsets.<platform>` list the plugin's toolsets on every platform, so a
  platform you did not list explicitly gets none of them.
- **Inbound photos**: native vision sends pixels and does NOT tell the model the file path; the
  gateway moves the file into the routed profile's `cache/images/` (`rehome_inbound_media`), so a
  plugin tool can list that folder newest first.
- **`MEDIA:<path>` policy is per profile**: `gateway.strict: true`, `trust_recent_files: false`,
  `media_delivery_allow_dirs: [<dir>]` in the profile's config limit what a reply can attach
  (default non-strict sends any readable file outside the credential denylist).
- A plugin runs in the gateway's managed Python (no PyYAML, no Pillow there): keep the plugin a
  thin gate and do the work in a subprocess with the system `python3 -I` (stdlib only) or a venv
  you own; ImageMagick (`magick`) is on the claws.

**Our own things that assume `default`.** Check each one before a profile
relies on it:
- the catch-up scripts (`runtime.profile_guard`,
  `slack_boundary.configured_api`) and Enzo's time-tracking plugin refuse a
  non-default home;
- skills we scp into `~/.hermes/skills/` exist only in default;
- `~/.config/<tool>/agent.env` files are shared through `HOME`, so they are
  visible to every profile;
- the `hermes-<bot>` wrappers target default (pass `-p <name>`);
- a default profile's catalog plugins (Home Assistant, Mnemosyne, claw-name) are not in a new
  profile: it starts with only the bundled ones.

## Importing from OpenClaw

`hermes claw migrate [--dry-run] [--preset user-data|full]` (guide:
`website/docs/guides/migrate-from-openclaw.md` in the installed tree). Traps:

- **The CLI has no `--include`, and `--preset user-data` still rewrites
  `config.yaml` (agent/compression/terminal, browser) and `.env` (Slack
  settings)**. For a scoped import call the underlying script with the
  runtime Python:
  `~/.hermes/tools/python-3.*/bin/python3 ~/.hermes/hermes-agent/optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py --include memory,user-profile,daily-memory --execute`
  (ids listed by `--help`; without `--execute` it is a dry run; the 2026-07
  run used the old venv's Python).
- **Memory merges are truncated at the char caps**: the rest goes to
  `~/.hermes/migration/openclaw/<ts>/overflow/*.txt`, which the agent never
  reads (~11 KB spilled on petraclaw in 2026-07). It also imports entries
  verbatim and with duplicates (`2026-02-02: …` lines, template prose,
  misspelt names). On 2026-10-15 we did NOT re-run it: we read every source
  (MEMORY, USER, IDENTITY, AGENTS, `memory/*.md`, DREAMS, channel notes, the
  per-channel `systemPrompt`s in `openclaw.json`), replaced MEMORY.md/USER.md
  with curated entries and put the rest in a knowledge skill. Verify with a
  fresh-session turn that only the moved facts can answer.
- OpenClaw knowledge also hides outside the workspace: per-channel
  `systemPrompt`s in `openclaw.json` (`channels.slack.channels.<id>`; Enzo's
  invoice-inbox → Holded purchase-draft rules lived only there) and
  `workspace/memory/channel-*.md`. `DREAMS.md` is narrative with nothing
  durable on our boxes and is not imported.
- Daily notes keep firing stale reminders as facts: check them against
  later notes before importing (Enzo's capital-increase reminder kept
  running after the increase was cancelled; Bruno's Daniela follow-up after
  the hand-off was done).
- `AGENTS.md` only moves with `--workspace-target`, and OpenClaw's is mostly
  OpenClaw mechanics: translate the durable rules, do not copy it.
  `IDENTITY.md` is archived; merge it into `SOUL.md` by hand.
- **Cron jobs: "No cron configuration found"** on OpenClaw 2026.9.x, whose
  jobs live in SQLite state, not in `openclaw.json`. Recreate them with
  `hermes cron create` from `openclaw cron list --json` (hq keeps the
  2026-10-15 export: `shared/docs/openclaw-jobs-2026-10-15.md`).
- `--migrate-secrets` (needed even under `--preset full`) copies
  `TELEGRAM_BOT_TOKEN` etc. into `.env`: after a restart Hermes answers on that
  channel. Treat it as the channel switch-over, not part of a memory import.
  The Telegram allowlist is read from `credentials/telegram-default-allowFrom.json`,
  which OpenClaw's doctor moved into SQLite: expect `TELEGRAM_ALLOWED_USERS`
  empty and set it by hand.
- `hermes claw cleanup` renames `~/.openclaw` to `.openclaw.pre-migration`
  (undoable). Run it only once nothing is left to recover from OpenClaw.

## A new claw container (patri 2026-10-17, maia 2026-10-19)

The order and checklist (decisions, estate, records) is hq
`shared/docs/bots.md` § "Adding a new bot (the recipe)"; these are the
commands. The order that worked, 40-60 minutes of wall time (maia: the
installer alone ~15 min). Traps found on maia:

- `--dev0 /dev/net/tun` set with `pct set` **before the first `pct start`**
  works and saves the Tailscale reboot (maia: `/dev/net/tun` present,
  `tailscaled` on a kernel `tailscale0` interface, not userspace networking).
- `fallback_providers` is a list `hermes config set` cannot write: append the
  block to `config.yaml` (`grep -q '^fallback_providers'` first). The
  managed Python run as `-I` with `hermes_bootstrap` could not `import yaml`
  on a fresh v0.22.2 box, so no Python YAML edit there.
- `truenas-rsync-sizes.sh` runs ON the target: `ssh root@<box> 'bash -s' <
  homelab/tools/truenas-rsync-sizes.sh`. Run bare, it measures the machine
  you are sitting on (it did, minisforum, read-only).
- NAS Syncthing env files quote their values: strip the quotes when you
  parse them (`cut -d= -f2- | tr -d "'\""`), or curl gets a URL starting
  with `'` and fails silently (code 000).


1. Host: `pveam update && pveam download local ubuntu-26.04-standard_26.04-1_amd64.tar.zst`;
   `pct create <ct> local:vztmpl/… --hostname <box> --cores 2 --memory 4096
   --swap 2048 --rootfs local-lvm:64 --unprivileged 1 --features nesting=1
   --net0 name=eth0,bridge=vmbr0,firewall=1,ip=dhcp --ostype ubuntu --onboot 1
   --tags claw-agent --timezone UTC --ssh-public-keys <roster.pub>`
   (the roster = `shared/ansible/roles/baseline/files/authorized_keys/*.pub`),
   then `pct set <ct> --dev0 /dev/net/tun` + a restart for Tailscale (below;
   passing `--dev0` at create time was not tried).
   Note the ed25519 host-key fingerprint it prints: the NAS pull compares it.
2. UniFi reservation + local DNS record + `static-dns` `<box>.localdomain`
   (`unifi` skill), `ssh` hosts.conf `Host … <box>` plus its own `Host <box>` block
   with `HostName <LAN IP>` + `HostKeyAlias <box>` (works away from home over
   the subnet route), both inventories.
3. As root: user `oriol` (uid 1000) with **passwordless sudo**,
   `/etc/sudoers.d/oriol` = `oriol ALL=(ALL:ALL) NOPASSWD: ALL`, 0440, checked
   with `visudo -cf` before installing (Oriol, 2026-10-23: his preferred setup
   on every claw, including bots someone else drives; the hq `claw_agent` role
   writes it too), copy the keys, `loginctl enable-linger oriol`,
   `Prompt=lts`, mask `netplan-configure.service`, full-upgrade, then `apt-get install -y --no-install-recommends libnspr4 libnss3` (Oriol, 2026-10-23: every claw, at creation and on every run of the hq `claw_agent` role).
4. As oriol, Hermes: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh`
   to a file, run it in tmux with `--branch release/X.Y.Z --commit vX.Y.Z
   --non-interactive`; wait on `tmux has-session`, not on a string in the
   `script` log (its header echoes the command line). ~1.3 GB in `~/.hermes`.
   `cua-driver` failed to install there and nothing needs it.
5. `hermes config set` model / provider / base_url, `memory.write_approval
   false`, the `fallback_providers` block, then as text edits
   `display.interface: tui` and `cron.wrap_response: false` (both house
   defaults since 2026-10-25), `hermes pm install --extra
   messaging`, `hermes gateway install --start-on-login --no-start-now`
   + the `10-private-memory.conf` (`UMask=0077`) drop-in, start it.
6. The model login is Oriol's: `hermes auth add openai-codex --type oauth --no-browser`.
7. **TTS on NaN kokoro, always** (Oriol, 2026-10-17: the default for every
   new claw): `hermes config set` `tts.provider openai`,
   `tts.openai.base_url https://api.nan.builders/v1`, `tts.openai.model
   kokoro`, `tts.openai.voice <voice>` (one per agent: `em_alex`, `ef_dora`…)
   and `tts.openai.api_key` from hq `homelab/secrets/nan.env` piped over ssh
   (never `VOICE_TOOLS_OPENAI_KEY`). Test with `RT 'from tools.tts_tool import
   text_to_speech_tool as t; print(t("…"))'`, read the MP3 back with NaN
   Whisper, restart the gateway. The Catalan voice rule goes in its MEMORY.md
   with the persona.
8. **STT on NaN Whisper, always** (Oriol, 2026-10-17, default for every new
   claw): system `ffmpeg` (apt; `nan-stt` calls it from PATH, Hermes's own
   copy is not on it: FileNotFoundError otherwise), `~/.local/libexec/nan-stt`
   (0755, from hq `homelab/tools/nan-stt.py`), `~/.config/nan/stt.env`
   (`NAN_API_KEY=`, 0600, piped from hq `nan.env`), a names-only
   `~/.config/nan/stt-vocabulary.txt` (hq `homelab/tools/nan-stt-vocabulary/<agent>.txt`),
   `hermes pm install --extra stt-whisper`, then `hermes config set
   stt.enabled true`, `stt.provider nan`, `stt.local.model tiny`,
   `stt.language ""` (a fresh config ships `"en"`), and with **`--force`**
   (the CLI rejects nested custom keys otherwise) `stt.providers.nan.type
   command`, `.command "/home/oriol/.local/libexec/nan-stt {input_path} {output_path}"`,
   `.format txt`, `.timeout 1800`. Test: `RT 'from tools.transcription_tools
   import transcribe_audio as t; print(t("<the TTS clip>"))'` → `provider: nan`
   and the text. Restart the gateway.

9. **Docker, with `oriol` in the docker group** (Oriol, 2026-10-18: "on all
   4 hermes hosts the user oriol needs docker access"): the `claw_agent` role
   (docker.com repo as a deb822 `docker.sources`, `usermod -aG docker oriol`).
   Docker CE works in the unprivileged CT with `nesting=1` alone (overlayfs,
   no `keyctl`). The group is root-equivalent for whoever drives the agent.
   A running gateway sees the group only after `systemctl restart
   user@1000.service` as root (check `active_agents` = 0 first; gateway,
   dashboard and timers come back by themselves, verified on all four).
10. **herdr + `h`** (Oriol, 2026-10-24): the same role installs herdr for
   `oriol` (official `install.sh`, then `herdr update`) and writes `alias
   h='/home/oriol/.local/bin/hermes'` to `~/.bash_aliases` (full path: the
   box's `~/.local/bin` is on PATH only in login shells). Then, on minisforum,
   `herdr machine add <box> --label <box>`: it refuses without a TTY, so from
   an agent drive it through a Python `pty.fork()`; with herdr already on the
   box it asks nothing and prints "Remote server is ready". Check `herdr
   machine status`. On the dev machines `h` is herdr (a fish function);
   on the boxes it is hermes. The clash is deliberate.

## Tailscale on the claws (2026-10-17)

An unprivileged LXC container has no `/dev/net/tun`: `pct set <ct> --dev0
/dev/net/tun` (PVE 9.1) and **`pct reboot <ct>`** (it does not hot-plug;
~20 s of agent downtime, the gateway comes back by itself). Then the
`pkgs.tailscale.com` repo for the Ubuntu codename, `systemctl enable --now
tailscaled`, ufw `allow 41641/udp`, and
`nohup tailscale up --hostname=<box> --accept-routes=false &` (the boxes sit
on the LAN that minisforum advertises; accepting it breaks LAN replies). The
login URL is in `tailscale status --json` → `AuthURL`; it is Oriol's to open
in the right account (pep/patri personal, enzo/bruno EnaCast). Check
`active_agents` in `~/.hermes/gateway_state.json` is 0 before the reboot.

## OS upgrades of the claw containers (runbook, first run pep 2026-10-15)

Ubuntu in the three LXC containers (CT 100 pep, 102 enzo, 101 bruno).
**LTS only from now on** (Oriol, 2026-10-15). pep went 25.04 → 26.04.1 in
16 minutes of upgrade time; one box at a time.

1. **Check Proxmox knows the target**: `grep "'26.04'" /usr/share/perl5/PVE/LXC/Setup/Ubuntu.pm`
   on the host (pve-container 6.0.18 does). An unknown release makes the CT
   refuse to start after the upgrade. Do not upgrade the host's packages for this.
2. **Snapshot**: `pct snapshot <ct> pre_ubuntu_2604 --description "…"` on the
   host (`ssh -o HostKeyAlgorithms=ssh-ed25519 root@192.168.7.179`). Rollback
   (`pct rollback`) is Oriol's call.
3. **Baseline**: os-release, `ufw status`, `systemctl --user` states of
   `hermes-gateway`, `hermes-dashboard`, `assistant-healthcheck@hermes.timer`,
   OpenClaw masked, `syncthing@oriol`, free disk.
4. **Everything as root in a detached tmux with a log**, never in the foreground
   ssh: `tmux new -d -s upgrade "script -f -q /root/upgrade-hopN.log -c /root/upgrade-hopN.sh"`,
   then poll from the workstation (`until ssh root@<ct> 'grep -q HOPN-DONE … || ! tmux has-session -t upgrade'; do sleep 20; done`).
   Scripts use `DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a` and
   `apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold`.
   Start each hop's tmux in its own command, not right after a `tmux
   kill-session` of the last session in the same line: the dying server
   swallowed bruno's hop-3 `tmux new`.
5. **Hop through an EOL interim release by hand**: 25.04 and 25.10 are both
   EOL, so `do-release-upgrade` from 25.04 offers nothing. Hop 1:
   `apt-get update && full-upgrade` on plucky, `sed -i 's/\bplucky\b/questing/g' /etc/apt/sources.list.d/ubuntu.sources`
   (keep a copy), `apt-get update && full-upgrade && autoremove --purge`
   (~6 min). `pct reboot <ct>` from the host. On enzo **sshd refused
   connections for a few minutes** in this hop while openssh was upgraded; the
   tmux job carried on. Poll with a loop that tolerates a failed ssh (`until
   ssh -o ConnectTimeout=5 … 2>/dev/null`), never treat one refusal as a dead
   box. Two containers upgrading at once on the 2-core host roughly doubles
   this hop (11 min on enzo).
6. **Hop 2, the supported route**: begin the script with
   `until curl -fsS -o /dev/null https://changelogs.ubuntu.com/meta-release; do sleep 5; done`
   (bruno, started 2 s after the reboot, printed "No new release found" and
   exited 1: the fetch ran before the network was up). Then
   `sed -i 's/^Prompt=.*/Prompt=normal/' /etc/update-manager/release-upgrades`
   (needed only from an interim release) and
   `do-release-upgrade -f DistUpgradeViewNonInteractive` (~9 min, rc 0; it says
   "Your Ubuntu release is not supported anymore" and carries on). It purges
   snapd, moves the system Python 3.13 → 3.14, and installs new conffiles where
   ours were untouched (`/etc/ssh/moduli`, the new `release-upgrades` already
   with `Prompt=lts`). sshd config, ufw rules and Syncthing config survive.
7. **Third-party sources come back disabled**: one-line `.list` files become
   `*.disabled` ("could not be automatically migrated"); Google's is migrated
   to deb822 but with `Enabled: no`. Move the `.disabled` files aside and write
   deb822 `.sources` with the existing keyrings:
   `syncthing.sources` (`URIs: https://apt.syncthing.net/`, `Suites: syncthing`,
   `Components: stable-v2`, `Signed-By: /etc/apt/keyrings/syncthing-archive-keyring.gpg`),
   `nodesource.sources` (`https://deb.nodesource.com/node_22.x`, `nodistro`,
   `main`, `Architectures: amd64`, `/usr/share/keyrings/nodesource.gpg`);
   `sed -i 's/^Enabled: no$/Enabled: yes/'` on `google-chrome.sources`. Then
   `apt-get update && full-upgrade` in tmux. Syncthing reached 2.1.6 already in
   hop 1 (from its own repo).
8. **Reboot, then `Prompt=lts`**: `grep ^Prompt /etc/update-manager/release-upgrades`
   must say `lts` (set it if not; check for a `.dpkg-dist` variant), and
   `do-release-upgrade -c` must find no newer LTS.
9. **`netplan-configure.service` fails on 26.04 in an LXC** ("Failed to send
   reload request": its `udevadm control --reload` has no udev). `/etc/netplan/`
   is empty; Proxmox writes systemd-networkd's `eth0.network`. `systemctl mask
   netplan-configure.service && systemctl reset-failed`; expect 0 failed units.
10. **Verify Hermes after the OS**: gateway active and `gateway_state.json`
    running for its MainPID; `hermes --version`; dashboard `/api/status`
    `auth_required: true` + a login 200 (creds in hq
    `homelab/secrets/hermes-dashboards.env`); healthcheck result success; a real
    turn shows `model=gpt-6.1-sol` in `agent.log`; `~/.local/libexec/nan-stt`
    on a short ffmpeg clip exits 0 (system python/ffmpeg changed); OpenClaw
    still masked; ufw rules intact; Syncthing version, peers and folder state
    over its REST API (key in `~/.local/state/syncthing/config.xml`). Hermes's
    managed Python 3.14 under `~/.hermes/tools/` is untouched by the OS upgrade.
11. Record it in the hq server file (OS line, the upgrade with UTC times and
    snapshot name) and `docs/changelog.md`.

## Rules

- Update one VM, verify, then the others.
- Back up `~/.hermes` before any migration or update (`umask 077`; exclude
  the rebuildable `hermes-agent/venv`, `hermes-agent/node_modules`,
  `tools/` (~1 GB of managed runtimes) and `backups/` (the updater's own zips);
  `.env` and `auth.json` are inside, so the archive is a secret). `hermes update`
  also writes its own `~/.hermes/backups/pre-update-*.zip`.
- Verified per-box facts go to the hq server file the same turn; mechanics here.
