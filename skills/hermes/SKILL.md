---
name: hermes
description: Operate Hermes Agent (Nous Research) on the estate's agent VMs ("claw agents" — the personal, EnaCast and BikeCRM/SmartupSoft agents on the home Proxmox host, formerly petraclaw/emmaclaw/blakeclaw) — install shape, the CLI per user (not root), the tag-pinned update with its post-checkout driver and rollback, model and fallback switch, built-in memory limits (MEMORY.md/USER.md char caps) and where larger knowledge goes, importing from OpenClaw (`hermes claw migrate` and the underlying script with --include, the overflow trap, cron jobs it cannot see), Discord, Sign in with ChatGPT, healthchecks. Use when the user mentions Hermes, `hermes-gateway`, `hermes claw migrate`, the agents' memory or skills, Pep/Enzo/Bruno (or the old Petra/Emma/Blake), a claw agent VM, or connecting an agent to Discord/Telegram/Slack/email through Hermes.
---

# Hermes — the agent runtime on the claw agents

**Direction (Oriol, 2026-10-15): Hermes is THE runtime; OpenClaw was stopped
and disabled on all three VMs that day** and is being retired (its mechanics,
kept for reference and rollback, are the `openclaw` skill). Estate state lives
in hq: start page
[`shared/docs/agents.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/agents.md),
runtime state [`shared/docs/hermes.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/hermes.md),
per-box facts in `hq/docs/servers/<vm>.md`. This skill is the *mechanics*;
update it the same turn a step behaves differently.

## Official sources first (Oriol, 2026-10-15)

When a mechanic is not in this skill, or behaves differently, **check the
official Hermes docs before guessing or searching the web**:
<https://hermes-agent.nousresearch.com/docs/> (skills:
<https://hermes-agent.nousresearch.com/docs/user-guide/skills/>). The same
docs ship in the installed tree, matching the running version:
`~/.hermes/hermes-agent/website/docs/` on any claw (e.g. `user-guide/
configuring-models.md`, `features/voice-mode.md`, `features/web-dashboard.md`,
`guides/migrate-from-openclaw.md`), and the source is next to them. Third-party
write-ups are often stale: v0.22 changed the updater, STT and dashboard auth.

## Access

- One VM per scope on the home Proxmox host (`192.168.7.179`), LAN only.
  `ssh oriol@<vm>` by name from the workstations. Each VM holds only its
  scope's keys; never copy a token between them.
- Hermes is installed **per user (`oriol`)**. As root `hermes` is "command
  not found", and running it as root would start an empty `/root/.hermes`:
  always `ssh oriol@<vm>` (or `su - oriol`). Non-interactive ssh does not
  read `~/.profile`: call `~/.local/bin/hermes` by full path in scripts.

## Install shape and day-to-day


State: hq `shared/docs/hermes.md`. `~/.hermes/hermes-agent` is a **shallow
git checkout** (`.install_method` = git), venv `./venv`, `uv` at
`~/.hermes/bin/uv`, CLI `~/.hermes/hermes-agent/venv/bin/hermes`, linked as
`~/.local/bin/hermes` (on PATH for user `oriol` in a login shell since
2026-10-15), config `~/.hermes/config.yaml`, secrets `~/.hermes/.env` and
`auth.json` (its own Codex login — never print), user unit
`hermes-gateway.service`, provider `openai-codex`.

**Updating — pin a release tag, never a bare `hermes update`** (it tracks
`main`, which is canary; `hermes --version`'s "+N carried commits" / "N
commits behind" is a shallow-clone artifact, not local work). Releases:
`gh release list -R NousResearch/hermes-agent` (tag = `v<date>`, name =
`vX.Y.Z`). Procedure that worked 2026-10-03 (v0.19.0 → v0.21.5, all three):

The release's own post-update steps (lazy backends, npm workspaces with
system Node, web UI build, bundled-skill sync, config migration) run
through [scripts/hermes_post_checkout.py](scripts/hermes_post_checkout.py),
which calls `hermes update`'s private tail functions. It mirrors
`hermes_cli.update_cmd._finish_pulled_update` **as of `v2026.9.24`**: for a
newer tag, compare it with that function in the target tag first (a
renamed helper fails the run with the gateway down). Copy it to the box,
then run the update as a script (`ssh oriol@<vm> 'bash -s' < update.sh`),
not pasted line by line: `set -e` is what stops it at the first failed
step.

```bash
# from the LLM_SKILLS checkout:
ssh oriol@<vm> 'mkdir -p ~/backups' && scp skills/hermes/scripts/hermes_post_checkout.py oriol@<vm>:backups/
```

```bash
set -euo pipefail
umask 077                     # the backup holds .env + auth.json
TAG=<tag>
H=~/.hermes/hermes-agent; cd "$H"
test -f ~/backups/hermes_post_checkout.py
test -z "$(git status --porcelain | grep -v '^?? .install_method$')"   # only .install_method may be untracked
PRE_SHA=$(git rev-parse HEAD)   # driver args; the version (from pyproject, as `hermes update` reads it) only feeds its report line
PRE_VERSION=$(venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
systemctl --user stop hermes-gateway.service      # BEFORE the backup: tar fails "file changed" while it runs
BACKUP=~/backups/hermes-pre-$TAG-$(date -u +%Y%m%dT%H%M%SZ).tgz; echo "backup: $BACKUP"
tar czf "$BACKUP" -C ~ \
  --exclude=.hermes/hermes-agent/venv --exclude=.hermes/hermes-agent/node_modules .hermes
cp -a ~/.hermes/config.yaml ~/backups/hermes-config.yaml.pre-$TAG
git fetch --no-tags origin tag "$TAG" && git checkout "$TAG"
VIRTUAL_ENV=$PWD/venv ~/.hermes/bin/uv pip install -e ".[all]"
venv/bin/python ~/backups/hermes_post_checkout.py "$PRE_SHA" "$PRE_VERSION" | tee ~/backups/hermes-post-checkout-$TAG.log
systemctl --user start hermes-gateway.service   # reached only when the driver exits 0 (update_complete=True)
```

If it stops early, the gateway stays down (and pages). Before the
`git checkout`, nothing changed: fix the cause, then re-run or start it.
After it, the tree and maybe `~/.hermes` are half-updated; put both back
(planned, not yet exercised):
`cd ~/.hermes/hermes-agent && git checkout <PRE_SHA> && tar xzf <BACKUP> -C ~ && VIRTUAL_ENV=$PWD/venv ~/.hermes/bin/uv pip install -e ".[all]" && systemctl --user start hermes-gateway.service`
(the sha and tarball path are in the run's output; the tarball excludes
`venv` and `node_modules`, which the install and the old tag's own
`node_modules` cover).

Verify: `hermes --version`, a real turn, `~/.hermes/logs/agent.log` →
`model=gpt-6-luna provider=openai-codex`, `assistant-healthcheck@hermes`
exit 0. The update pings one failure to healthchecks.io per box. Rollback:
`git checkout <old tag>`, the same `uv pip install`, restore the config copy.

Model switch:

```bash
H=~/.hermes/hermes-agent/venv/bin/hermes
$H chat -Q --provider openai-codex -m gpt-6-luna -q "Reply with exactly: HERMES OK"   # test first
$H config set model.default gpt-6-luna
# fallback: top-level list; `hermes fallback add` is interactive only, and
# `fallback_model:` (still in its docs) is NOT a recognised key
grep -q '^fallback_providers:' ~/.hermes/config.yaml ||   # appending twice = duplicate top-level key
  printf '%s\n' 'fallback_providers:' '- provider: openai-codex' '  model: gpt-5.6-luna' >> ~/.hermes/config.yaml
$H fallback list; systemctl --user restart hermes-gateway.service
```

**Discord (v0.21.5; researched 2026-10-03, not yet enabled anywhere)** —
outbound websocket only, so LAN-only is fine. One Discord application per
VM in that scope's account (a token can run in only one gateway). Oriol,
in the Developer Portal: Bot → **Public Bot off**, **Message Content intent
on** (Server Members only for username/role allowlists), reset token,
invite with `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot+applications.commands&permissions=274878286912`;
he writes the token on the box himself:
`ssh -t oriol@<vm> 'read -rsp "token: " T; printf "DISCORD_BOT_TOKEN=%s\n" "$T" >> ~/.hermes/.env; chmod 600 ~/.hermes/.env'`
and hands over the app id + his numeric user id. Agent then:
`cd ~/.hermes/hermes-agent && VIRTUAL_ENV=$PWD/venv ~/.hermes/bin/uv pip install -e ".[messaging]"`
(else the gateway lazy-installs `discord.py[voice]`), appends
`DISCORD_ALLOWED_USERS=<id>` (numeric — no allowlist = everyone denied) to
`.env` without printing it, sets top-level `unauthorized_dm_behavior: ignore`
(default `pair` answers strangers with a pairing code), restarts. Defaults:
`DISCORD_REQUIRE_MENTION=true` (DMs exempt), `DISCORD_AUTO_THREAD=true`,
`DISCORD_ALLOW_BOTS=none`. Verify: journal `[discord] Connected as …`, no
`PrivilegedIntentsRequired` / `token rejected` / `No Discord access policy`,
a DM gets 👀 → ✅ + reply, a second account gets silence. Allowed users get
full tool/terminal access — allowlist Oriol only. Source:
`website/docs/user-guide/messaging/discord.md` in the tag.

**Sign in with ChatGPT**: Hermes support is open PR #128926, not released;
OpenClaw's beta exists since 9.7 — verdict and evaluation in hq
`shared/docs/openclaw.md` § Sign in with ChatGPT (not yet; device code stays).

## Updating to v0.22+ (stable channel) — what changed

- **v0.22.0 (2026-10-14) rebuilt the updater**: SemVer releases (`v0.22.1`),
  and official source checkouts track the **`stable` channel** (latest
  `vX.Y.Z`) instead of `main`; `hermes update --channel stable|canary|main`,
  `--set-channel` persists, `--plan` previews, `--check` checks.
  `_finish_pulled_update` is gone, so `scripts/hermes_post_checkout.py` only
  applies to the v0.19–v0.21.5 line. A v0.21.5 box still compares against
  `main` ("13012 commits behind"): never `hermes update` there.
- **Path that worked 0.21.5 → 0.22.1 (pep, 2026-10-15)**: Proxmox snapshot
  of the CT first (`pct snapshot <id> pre_hermes_<ver>`), stop the gateway,
  back up `~/.hermes`, `git fetch --no-tags origin tag v0.22.1 && git
  checkout v0.22.1`, `uv pip install -e ".[all]"` into the venv (Python 3.11
  is fine: `>=3.11,<3.15`), then **run one CLI call in the foreground BEFORE
  starting the gateway** (`hermes --version`): the first run of a new
  revision "completes source-update dependencies" (Python deps again, Node
  deps, TUI build, web UI build, ~1.8 GB peak). Started straight from
  systemd, that build blows the unit's default 90 s start timeout
  (`Type=notify`): systemd kills it, `Restart=always` restarts it, and the
  build starts over in a loop. Boot maintenance (config migration, skills
  sync) then runs per revision on its own. The first run also moved Hermes
  onto its own managed **Python 3.14** runtime (`hermes --version`).
- **Once on v0.22.x, use the official updater**: gateway stopped, then
  `hermes update --yes` in the foreground (pep, v0.22.1 → v0.22.2,
  2026-10-15: own zip backup in `~/.hermes/backups/pre-update-*.zip`, Node +
  TUI + web UI rebuilt, skills and config checked, "Update complete"), then
  start the gateway. enzo and bruno went 0.21.5 → v0.22.2 directly with the
  manual tag checkout above.
- **The first v0.22 run rewrites `~/.local/bin/hermes`** into a 2-line sh
  launcher (`exec ~/.hermes/hermes-agent/.hermes/bin/hermes "$@"`), replacing
  our symlink. The NEXT `hermes` call in the SAME script then died with
  `SyntaxError` (a Python trampoline `runpy`-ing the sh launcher), which
  under `set -e` left enzo and bruno with the gateway stopped (2026-10-15).
  The same command from a fresh ssh shell worked. So end the script after
  the first-run call and continue in a new session, and always check
  `systemctl --user is-active hermes-gateway` at the end.
- **Messaging platforms need the `messaging` extra**: without it a pairing
  QR prints "QR code unavailable … run: hermes pm install --extra
  messaging". Install it (`hermes pm install --extra messaging`), then
  restart the gateway. Installed on all three 2026-10-15.
- After the v46 → v50 config migration enzo and bruno warn that platform
  `homeassistant` references unknown toolset `hermes-homeassistant`: Home
  Assistant moved to a catalog plugin in v0.22. Harmless while that platform
  is unused; `hermes tools` reconfigures it.
- **WhatsApp in Hermes is its own code**, not WAHA: a built-in Node bridge on
  `@whiskeysockets/baileys` (`scripts/whatsapp-bridge/`, QR pairing as a
  linked device, unofficial, ban risk, docs say use a dedicated number), or
  `whatsapp_cloud.py` for Meta's official Cloud API (Business account + a
  public webhook). Pairing a number WAHA already holds just adds a second
  linked device.
- **Web dashboard**: `hermes dashboard` (default `127.0.0.1:9119`; `--host`,
  `--port`, `--no-open`); a non-loopback bind always requires an auth
  provider (password or OAuth). Its Chat tab runs the real TUI over a pty.
- **`hermes update --check` is not read-only on v0.22**: it installed the
  "default tools" `agent-browser` and `cua-driver` (opt out:
  `hermes pm install --without <tool>`). `--plan` changed nothing.
- Model switch to **`gpt-6.1-sol`** (2026-10-15, Oriol): test with
  `hermes chat -Q --provider openai-codex -m gpt-6.1-sol -q "…"`, then
  `hermes config set model.default gpt-6.1-sol`; `agent.log` shows
  `model=gpt-6.1-sol provider=openai-codex`. Fallback left at
  `gpt-5.6-luna`.

## Custom model providers (NaN as an option)

`providers.<name>: {api: <OpenAI-compatible base URL>, key_env: VAR (or
api_key: "${VAR}"), discover_models: false, models: {id: {context_length: N}}}`
in `config.yaml`; the key goes in `~/.hermes/.env`. Use it per run with
`hermes chat --provider <name> -m <model>` (also `custom:<name>`; `agent.log`
shows `provider=custom`) or `/model <name>:<model>` in a chat; `model.default`
is untouched. Ours: `nan` → `deepseek-v4-flash`, `glm5.3-flash` (2026-10-15,
verified a plain turn and a tool call on pep). Skip models that call tools in
XML (NaN's Qwen/Gemma).

## Speech-to-text (voice notes, audio) — NaN Whisper

- Built-in providers: `local` (faster-whisper), `groq`, `openai`, `mistral`,
  `xai`, `elevenlabs`, `deepinfra`; `stt.providers.<name>: {type: command,
  command: "… {input_path} {output_path}", format: txt, timeout: N}` adds
  your own. A command provider runs with Hermes's secrets scrubbed from its
  env (`env_passthrough: [VAR]` to pass one) and gets `{language}` defaulting
  to `en`: do not put it in the command if you want auto-detect.
- Hermes cuts long audio only by size (25 MB for `openai`) and by a
  per-model duration table (`whisper-1` 600 s, `gpt-4o*-transcribe` 450 s);
  an unknown model id gets no duration cap. `stt.openai.timeout` defaults to
  60 s. So `openai` + `STT_OPENAI_BASE_URL` pointed at a slow
  OpenAI-compatible server (NaN: ~1x realtime, 524 past ~2 min) fails on
  long voice notes.
- Ours (2026-10-15, all three): `stt.provider: nan` → command provider
  `~/.local/libexec/nan-stt {input_path} {output_path}` (source hq
  `homelab/tools/nan-stt.py`): ≤ 90 s Opus pieces, `model=whisper`, never a
  language, 6.5 s between requests, retries; key in `~/.config/nan/stt.env`.
  Test through Hermes itself:
  `cd ~/.hermes/hermes-agent && HERMES_HOME=~/.hermes venv/bin/python -c 'from tools.transcription_tools import transcribe_audio as t; print(t("/tmp/x.mp3"))'`
  → `provider: nan`. Detail: hq `docs/nan-builders.md`.

## From a dev machine: CLI wrappers and Hermes Desktop (2026-10-15)

- **`hermes-pep` / `hermes-enzo` / `hermes-bruno`** (hq dotfiles
  `local-bin/hermes-claw`, mapped three times in `sync-dotfiles.sh`): `ssh
  [-t|-T] <host> '~/.local/bin/hermes <args %q-quoted>'` as oriol; `-t` only
  when stdin AND stdout are ttys, so `hermes-pep chat -Q -q "…"` is clean in
  scripts. Use these instead of hand-rolled ssh quoting.
- **Hermes Desktop on Linux = a source install** (`scripts/install.sh
  --include-desktop`; their release workflow ships no Linux package). Traps:
  - Without `--branch release/X.Y.Z --commit vX.Y.Z` the installer clones
    **`main`** (a canary) yet labels the install `stable`, and `hermes update
    --channel stable` then refuses the "rollback" to the release. The tag
    commit is NOT on `main` (`--commit` alone fails `commit_not_on_branch`).
    Fixed by hand on minisforum: `git checkout --detach vX.Y.Z` in the
    checkout, `hermes --version` (rebuilds deps), `hermes desktop
    --build-only --force-build`.
  - Bulk: checkout + Electron build ~3.7 GB under `--dir`, plus
    `~/.hermes/{tools,installs,cache}` (pinned runtimes, the Python
    environment, uv's cache, ~1 GB). On the estate all four live in
    `~/not-important/homelab/hermes` (symlinks from `~/.hermes`, made BEFORE
    the installer runs); Desktop looks for the runtime at
    `~/.hermes/hermes-agent`, so that is a symlink to the checkout too.
  - `--non-interactive --skip-browser --skip-computer-use`: no wizard, no
    gateway service, no Chromium. The installer only edits `config.fish` when
    no `fish_add_path …/.local/bin` line is there (it did not on minisforum).
  - Launch from a shell needs the session's `DISPLAY` / `WAYLAND_DISPLAY`
    (Electron defaults to X11 and exits "Missing X server" without them); the
    menu entry `com.nousresearch.hermes.desktop` runs `hermes desktop
    --skip-build`. Log: `~/.hermes/logs/desktop.log`.
- **The connection registry** is `~/.config/Hermes/connections.json` (Electron
  userData, productName `Hermes`; schema v2 in
  `apps/desktop/electron/connection-registry.ts`): `{version: 2, primary,
  launchMode, lastUsed, connections: [{id, kind: local|remote|cloud|ssh,
  label, host, user, port, keyPath, remoteHermesPath, remoteProfile}]}`.
  Labels are unique case-insensitively; a malformed entry is quarantined, not
  dropped. Pre-seeding SSH entries works: ansible's
  `files/hermes-desktop-connections.py` (homelab, `--tags hermes-desktop`)
  adds `{id: host, kind: ssh, label, host, user: oriol}` only when the label
  or host is new. Close the app first: it rewrites the file from memory.
- **What an SSH connection does** (desktop.log, verified on all three):
  control master → `bash -lc 'command -v hermes'` on the remote (falls back to
  `~/.local/bin/hermes`) → version check → spawns a remote **dashboard on
  127.0.0.1** → forwards it to a local port → the agent joins the roster.
  It dialed all three at launch. Nothing to configure or expose on the
  containers: never bind a dashboard to 0.0.0.0 for this.

## Liveness and boot

- User timer `assistant-healthcheck@hermes.timer` runs
  `~/.local/libexec/assistant-healthcheck hermes`, which pings the
  healthchecks.io URL in `~/.config/assistant-monitoring/hermes.url` (or
  `/fail`). Since 2026-10-15 the probe requires BOTH `hermes-gateway.service`
  active AND `~/.hermes/gateway_state.json` saying `"gateway_state": "running"`
  with `pid` equal to the unit's `MainPID` (an active unit whose gateway gave
  up no longer passes). Still blind to a dead model login: only a real turn
  proves that. An outage during an update pages.
- The script is hand-installed on each box (no repo deploys it); a backup of
  the previous version is `~/backups/assistant-healthcheck.pre-2026-10-15`.
- Boot: `hermes-gateway.service` and the hermes timer are enabled user units
  with linger on. **OpenClaw cannot start**: its unit file and drop-in were
  moved to `~/backups/openclaw-retired-units/` and `openclaw-gateway.service`
  plus `assistant-healthcheck@openclaw.{timer,service}` are **masked**
  (2026-10-15). To bring it back: `systemctl --user unmask …`, move the files
  back to `~/.config/systemd/user/`, `daemon-reload`, `enable --now`.
- `~/.bashrc` still sources OpenClaw's bash completion from `~/.openclaw/`;
  harmless, but it errors if `~/.openclaw` is ever renamed (`hermes claw
  cleanup`): drop that line then.

## Memory: what Hermes keeps and where bigger knowledge goes

- Built-in memory is two small files injected every turn:
  `~/.hermes/memories/MEMORY.md` (cap `memory.memory_char_limit`, 2200 on our
  boxes) and `USER.md` (`user_char_limit`, 1375), entries separated by `§`.
  `memory.write_approval: true` on our boxes. Persona is `~/.hermes/SOUL.md`.
- The file format is entries joined by `"\n§\n"` (`ENTRY_DELIMITER` in
  `tools/memory_tool_store.py`). `write_approval` gates only the agent's own
  memory tool: editing the files directly (as the 2026-10-15 import did) is
  not blocked, and it is safe while the gateway runs, because every tool
  write rereads the file under a `.lock` and refuses on drift.
- Every entry passes `_scan_memory_content` (injection/exfil patterns) at
  write AND at load; a flagged entry is dropped from the prompt with a
  warning. Run it on curated text before installing it:
  `venv/bin/python -c 'from tools.memory_tool_store import _scan_memory_content as s; print(s(open("x").read()))'`
  from `~/.hermes/hermes-agent`.
- Leave headroom under the caps (we installed ~1.2 KB of 2.2 KB): the agent
  adds its own entries and an over-cap file blocks every further addition.
- An external memory provider can sit beside it (only one at a time;
  `hermes memory status`). Ours have **`mnemosyne`** configured (plugin
  `hermes-mnemosyne` 0.4.0 under `~/.hermes/plugins/`, data
  `~/.hermes/mnemosyne/`, local SQLite + embeddings, multilingual MiniLM)
  since 2026-07-23. Upstream is `mnemosyne-oss/mnemosyne` (3,420 GitHub stars
  on 2026-10-15, passes the >1k rule; the Hermes provider is by its author,
  GitHub AxDSan). Still: it recalls by similarity, so durable facts the
  agent must always apply belong in MEMORY.md or a file skill, not only
  there.
- Anything that does not fit the caps goes into a **file skill**
  (`~/.hermes/skills/<category>/<name>/SKILL.md`), loaded on demand. Imported
  OpenClaw skills land in `~/.hermes/skills/openclaw-imports/`. A category is
  just a folder with a one-line `DESCRIPTION.md`; `hermes skills list` shows
  a new skill immediately (scan by directory mtime), and new skills and
  memory take effect in a NEW session; no gateway restart needed. Check a
  hand-written skill with the built-in scanner (verdict SAFE → allowed):
  `venv/bin/python -c 'from tools.skills_guard import scan_skill, format_scan_report; from pathlib import Path; print(format_scan_report(scan_skill(Path("<dir>"))))'`.
- Our three agents each have `~/.hermes/skills/knowledge/agent-knowledge/`
  (since 2026-10-15): the long tail of what OpenClaw learned, grouped by
  topic. Keep it current there, not in the overflow files.

## Importing from OpenClaw

`hermes claw migrate [--dry-run] [--preset user-data|full]` (guide:
`website/docs/guides/migrate-from-openclaw.md` in the installed tree, the
reliable source; web write-ups are third-party). Traps:

- **The CLI has no `--include`, and `--preset user-data` still rewrites
  `config.yaml` (agent/compression/terminal, browser) and `.env` (Slack
  settings)**. For a scoped import call the underlying script:
  `~/.hermes/hermes-agent/venv/bin/python ~/.hermes/hermes-agent/optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py --include memory,user-profile,daily-memory --execute`
  (ids listed by `--help`; without `--execute` it is a dry run).
- **Memory merges are truncated at the char caps**: the rest goes to
  `~/.hermes/migration/openclaw/<ts>/overflow/*.txt`, which the agent never
  reads (the 2026-07-23 run spilled ~11 KB on petraclaw; on emmaclaw the
  overflow was mostly one reminder repeated daily). It also imports entries verbatim and
  with duplicates (`2026-02-02: …` lines, the template's "Learn about the
  person…" prose, misspelt names such as "Petrah-inbox"). On 2026-10-15 we
  did NOT re-run it: we read every source (MEMORY, USER, IDENTITY, AGENTS,
  `memory/*.md`, DREAMS, channel notes, the per-channel `systemPrompt`s in
  `openclaw.json`), replaced MEMORY.md/USER.md with hand-curated entries and
  put the rest in a knowledge skill. Verify with a fresh-session turn that
  only the moved facts can answer.
- OpenClaw knowledge also hides outside the workspace: per-channel
  `systemPrompt`s in `openclaw.json` (`channels.slack.channels.<id>`; Enzo's
  invoice-inbox → Holded purchase-draft rules lived only there) and
  `workspace/memory/channel-*.md`. `DREAMS.md` is narrative "dream diary"
  text with nothing durable on our boxes.
- Daily notes keep firing stale reminders as facts: check them against
  later notes before importing (Enzo's capital-increase reminder kept
  running after the increase was cancelled; Bruno's Daniela follow-up after
  the hand-off was done).
- `AGENTS.md` only moves with `--workspace-target`, and OpenClaw's is mostly
  OpenClaw mechanics (heartbeats, `memory/` daily files): translate the
  durable rules, do not copy it. `IDENTITY.md` is archived, merge it into
  `SOUL.md` by hand. `DREAMS.md` is not imported.
- **Cron jobs: "No cron configuration found"** on OpenClaw 2026.9.x, whose
  jobs live in SQLite state, not in `openclaw.json`. Recreate them with
  `hermes cron create` from `openclaw cron list --json` (hq keeps the
  2026-10-15 export: `shared/docs/openclaw-jobs-2026-10-15.md`).
- `--migrate-secrets` copies `TELEGRAM_BOT_TOKEN` etc. into `.env`: after a
  restart Hermes answers on that channel. Treat it as the channel switch-over,
  not part of a memory import. The Telegram allowlist is read from
  `credentials/telegram-default-allowFrom.json`, which OpenClaw's doctor
  moved into SQLite: expect `TELEGRAM_ALLOWED_USERS` empty and set it by hand.
- `hermes claw cleanup` renames `~/.openclaw` to `.openclaw.pre-migration`
  (undoable). Run it only once nothing is left to recover from OpenClaw.

## OS upgrades of the claw containers (runbook, first run pep 2026-10-15)

Ubuntu in the three LXC containers (Proxmox CT 100 pep, 102 enzo, 101 bruno).
**LTS only from now on** (Oriol, 2026-10-15). pep went 25.04 → 26.04.1 in
16 minutes of upgrade time; follow the same steps on enzo and bruno, one at a
time.

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
5. **Hop through an EOL interim release by hand**: 25.04 and 25.10 are both
   EOL, so `do-release-upgrade` from 25.04 offers nothing. Hop 1:
   `apt-get update && full-upgrade` on plucky, `sed -i 's/\bplucky\b/questing/g' /etc/apt/sources.list.d/ubuntu.sources`
   (keep a copy), `apt-get update && full-upgrade && autoremove --purge`
   (~6 min). `pct reboot <ct>` from the host.
   On enzo (2026-10-15) **sshd refused connections for a few minutes** in this
   hop, while openssh was upgraded; the tmux job carried on. Poll with a loop
   that tolerates a failed ssh (`until ssh -o ConnectTimeout=5 … 2>/dev/null`),
   never treat one refusal as a dead box. Two containers upgrading at once on
   the 2-core host roughly doubles this hop (11 min on enzo).
6. **Hop 2, the supported route** (bruno, 2026-10-15: started 2 s after the
   reboot it printed "No new release found" and exited 1 — the meta-release
   fetch ran before the container's network was up; so begin hop 2's script
   with `until curl -fsS -o /dev/null https://changelogs.ubuntu.com/meta-release; do sleep 5; done`.
   Also start each hop's tmux in its own command, not right after a
   `tmux kill-session` of the last session in the same line: the dying
   server swallowed bruno's hop-3 `tmux new`): `sed -i 's/^Prompt=.*/Prompt=normal/' /etc/update-manager/release-upgrades`
   (needed only from an interim release), then
   `do-release-upgrade -f DistUpgradeViewNonInteractive` (~9 min, rc 0; it says
   "Your Ubuntu release is not supported anymore" and carries on). It purges
   snapd, moves Python 3.13 → 3.14, and installs new conffiles where ours were
   untouched (`/etc/ssh/moduli`, the new `release-upgrades` already with
   `Prompt=lts`). sshd config, ufw rules and Syncthing config survive.
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
    `homelab/secrets/hermes-dashboards.env`); healthcheck Result success; a real
    turn shows `model=gpt-6.1-sol` in `agent.log`; `~/.local/libexec/nan-stt`
    on a short ffmpeg clip exits 0 (system python/ffmpeg changed); OpenClaw
    still masked; ufw rules intact; Syncthing version, peers and folder state
    over its REST API (key in `~/.local/state/syncthing/config.xml`). Hermes's
    own venv and managed Python 3.14 are untouched by the OS upgrade.
11. Record it in the hq server file (OS line, the upgrade with UTC times and
    snapshot name) and `docs/changelog.md`.

## Rules

- Update one VM, verify, then the others.
- Back up `~/.hermes` before any migration or update (`umask 077`, exclude
  `hermes-agent/venv` and `node_modules`; `.env` and `auth.json` are inside).
- Verified per-box facts go to the hq server file the same turn; mechanics here.
