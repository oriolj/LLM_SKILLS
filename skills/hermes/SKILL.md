---
name: hermes
description: Operate Hermes Agent (Nous Research) on the estate's agent containers ("claw agents" — the personal, EnaCast and BikeCRM/SmartupSoft agents on the home Proxmox host, formerly petraclaw/emmaclaw/blakeclaw) — install shape, the CLI per user (not root), updating on the v0.22 stable channel (first-run dependency build, launcher rewrite), model and fallback switch, voice (NaN Whisper STT with a local fallback, TTS), built-in memory limits (MEMORY.md/USER.md char caps) and where larger knowledge goes, importing from OpenClaw (`hermes claw migrate` and the underlying script with --include, the overflow trap, cron jobs it cannot see), Discord and WhatsApp, the dashboard and Hermes Desktop, OS upgrades of the containers, Sign in with ChatGPT, healthchecks. Use when the user mentions Hermes, `hermes-gateway`, `hermes update`, `hermes claw migrate`, the agents' memory or skills, Pep/Enzo/Bruno (or the old Petra/Emma/Blake), a claw agent container, or connecting an agent to Discord/Telegram/Slack/email through Hermes.
---

# Hermes — the agent runtime on the claw agents

**Hermes is THE runtime** (Oriol, 2026-10-15); OpenClaw was stopped and
disabled on all three boxes that day (its mechanics, kept for reference and
rollback: the `openclaw` skill). Estate state lives in hq: start page
[`shared/docs/agents.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/agents.md),
runtime state [`shared/docs/hermes.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/hermes.md),
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

- Three Ubuntu LXC containers on the home Proxmox host (`192.168.7.179`),
  one per scope: CT 100 **pep** (personal), CT 102 **enzo** (Enantena/EnaCast),
  CT 101 **bruno** (SmartupSoft/BikeCRM). LAN only; `ssh oriol@<box>` by name
  from the workstations. Each box holds only its scope's keys; never copy a
  token between them.
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

  Verified on pep 2026-10-15 (`tools.memory_tool_store`,
  `tools.transcription_tools`, `tools.tts_tool`, `tools.skills_guard` import).
  Below, `RT <code>` means this command.

## Updating (v0.22+, stable channel)

v0.22.0 (2026-10-14) rebuilt the updater: SemVer releases (`v0.22.2`),
source checkouts track the **`stable` channel** (latest `vX.Y.Z`) instead of
`main`; `hermes update --channel stable|canary|main`, `--set-channel`
persists, `--plan` previews (changed nothing). `hermes --version`'s
"N commits behind" on a shallow clone is not local work.

Procedure (pep v0.22.1 → v0.22.2, 2026-10-15), one box at a time:

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
- **`hermes update --check` is not read-only**: it installed the "default
  tools" `agent-browser` and `cua-driver` (opt out:
  `hermes pm install --without <tool>`). Use `--plan` to look.
- Rollback: the updater's `pre-update-*.zip` and the Proxmox snapshot exist;
  neither restore has been exercised.
- The v46 → v50 config migration warns that platform `homeassistant`
  references unknown toolset `hermes-homeassistant` (Home Assistant moved to
  a catalog plugin in v0.22). Harmless while unused; `hermes tools`
  reconfigures it.

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
  verdict in hq `shared/docs/openclaw.md` § Sign in with ChatGPT (not yet;
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
hq `shared/docs/agents.md` § Voice notes and audio. Mechanics:

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

## From a dev machine: CLI wrappers and Hermes Desktop

Setup: hq `homelab/ansible/roles/development/tasks/hermes-desktop.yml`, run
with the no-sudo `ansible-playbook playbooks/hermes-desktop.yml -l <host>`
(`-c local` on the controller; `--tags hermes-desktop` in site.yml does the
same but asks the sudo password), and `shared/docs/agents.md`. Traps:

- **`hermes-pep` / `hermes-enzo` / `hermes-bruno`** (hq dotfiles
  `local-bin/hermes-claw`): `ssh [-t|-T] <host> '~/.local/bin/hermes <args>'`
  as oriol, `-t` only when stdin AND stdout are ttys, so `hermes-pep chat -Q
  -q "…"` is clean in scripts. Use them instead of hand-rolled ssh quoting.
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
- `memory.write_approval: true` on our boxes gates only the agent's own
  memory tool: editing the files directly is not blocked, and it is safe while
  the gateway runs, because every tool write rereads the file under a `.lock`
  and refuses on drift.
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
