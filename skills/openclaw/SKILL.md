---
name: openclaw
description: Operate the estate's OpenClaw agent VMs (petraclaw = personal, emmaclaw = Enantena, blakeclaw = SmartupSoft/BikeCRM — self-hosted personal-AI-agent gateways on the home LAN) — how they are installed (nvm Node, npm global, user systemd unit), the safe update procedure and the trap where `openclaw update` leaves the gateway DOWN on a pending state-DB migration, plugin version pins, the systemd unit reinstall, adding a Slack workspace (socket mode, manifest, tokens, allowlists), adding Telegram/other channels, reading the config without leaking secrets, and the verification that proves an update or a channel actually works. Use when the user mentions OpenClaw, petraclaw/emmaclaw/blakeclaw, "the claw", updating an agent VM, connecting an agent to Slack/Telegram/WhatsApp, `openclaw doctor`, a gateway that will not start, plugin drift warnings, or Hermes (the Nous Research Hermes Agent on the same VMs — `hermes-gateway`, tag-pinned update and rollback, model/fallback switch, a Discord bot on a claw).
---

# OpenClaw — the three agent VMs

**What OpenClaw is, the risks and the estate state live in hq
[`shared/docs/openclaw.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/openclaw.md)**;
per-box facts in `hq/docs/servers/<name>.md`
([petraclaw](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/docs/servers/petraclaw.md),
[emmaclaw](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/docs/servers/emmaclaw.md),
[blakeclaw](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/docs/servers/blakeclaw.md)).
This skill is the *mechanics*. Verified on all three 2026-09-17
(2026.7.1-2 → 2026.9.4); update the notes here the same turn a step
behaves differently.

## The estate model — one VM per scope, accounts follow the scope

| VM | Scope | LAN IP | Channels (2026-09-17) |
|---|---|---|---|
| petraclaw | personal (oriolj) | `192.168.7.73` | Telegram **only** — no personal Slack exists, decision 2026-09-17; never stage Slack here |
| emmaclaw | Enantena / EnaCast | `192.168.7.217` | Telegram + Enantena Slack (8 channels, one is an invoices-inbox → Holded purchase-draft flow) |
| blakeclaw | SmartupSoft / BikeCRM | `192.168.7.187` | Telegram + SmartupSoft Slack (app Blake; DMs Oriol + Enric, `#seaotter2026` no-mention, `#general` on mention) |

Current versions, models and login state per box live in hq
[shared/docs/openclaw.md](../../../../../Syncthing/Syncthing-mobile-docs/hq/shared/docs/openclaw.md#what-is-actually-on-our-boxes-verified-2026-09-17-updated-2026-10-03)
and the server files (read them before acting; this skill is mechanics).
Each VM ALSO runs **Hermes Agent** (Nous Research, `~/.hermes/`, user unit
`hermes-gateway.service`) with its OWN Codex login; see § Hermes and hq
[shared/docs/hermes.md](../../../../../Syncthing/Syncthing-mobile-docs/hq/shared/docs/hermes.md).
emmaclaw is the only one that
also loads secrets from a unit drop-in (`openclaw-gateway.service.d/
override.conf` → `EnvironmentFile=~/.openclaw/secrets/openclaw.env`:
Slack bot token, Trello, Ramen creds) — `gateway install --force` keeps
the drop-in.

Proxmox VMs 100 / 102 / 101 on the home `proxmox` host (`.179`), Ubuntu 25.04, **LAN only**
(no Tailscale, no public DNS). `ssh oriol@<name>` works by name from the
workstations with the usual key; `root@` too; sudo asks a password. Each VM
holds ONLY its scope's keys (model provider, Slack, Telegram, Brave) — never
copy a token from one claw to another.

## Install shape (all three identical)

- Node **24.18.0 from nvm** (`~/.nvm/versions/node/v24.18.0/bin`) — nothing
  is on PATH in a non-interactive ssh: prefix every command with
  `export PATH=$HOME/.nvm/versions/node/v24.18.0/bin:$PATH`.
- `openclaw` = npm global under that Node; official plugins under
  `~/.openclaw/npm/projects/`.
- **User** systemd unit `~/.config/systemd/user/openclaw-gateway.service`
  (linger on): `systemctl --user {status,stop,start,restart} openclaw-gateway`,
  `journalctl --user -u openclaw-gateway`. Not a system unit — `sudo
  systemctl` finds nothing.
- Gateway on `127.0.0.1:18789`, token auth, Tailscale exposure off; the CLI
  talks to it locally (`openclaw health`, `status`, `channels status`).
- Config `~/.openclaw/openclaw.json` (JSON5, plaintext secrets — OpenClaw
  has no secret store); state SQLite `~/.openclaw/state/openclaw.sqlite`;
  agent `main` with workspace `~/.openclaw/workspace` (a git repo:
  `AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `USER.md`, `memory/`, `skills/`);
  model `openai/gpt-6-luna` via the **Codex** plugin (fallback
  `gpt-5.6-luna`).
- User drop-in `openclaw-gateway.service.d/tmpdir.conf` (since
  2026-09-23): `TMPDIR=%h/.cache/openclaw-tmp` only. Its former
  `ExecStartPre` cleanup was removed 2026-10-03: OpenClaw 9.8's unit lint
  reports "Systemd Service.ExecStartPre contains an unrecognized setting",
  and 9.6+ reclaims abandoned copies itself. **Why the TMPDIR**: 2026.9.5
  stages a ~341 MB `openclaw-plugin-build-*` copy under `$TMPDIR` on every
  gateway start AND every CLI call that loads plugins, and never deletes
  it; `/tmp` on these VMs is **tmpfs (RAM)**, so on petraclaw 24 leftovers
  = 5.1 GB on a 4 GB VM → swap full, gateway OOM-killed three times, ssh
  timing out at the banner. `gateway install --force` keeps the drop-in.
  Export the same `TMPDIR` in any shell where you run `openclaw` by hand,
  and `rm -rf /tmp/openclaw-plugin-build-*` afterwards if you forgot.
  **The `.service.d/` dir must be `0755` or tighter** (`chmod go-w`): a
  `mkdir -p` under the default umask made it 775 and 2026.9.6's `gateway
  install --force` then refused with `[unsafe-permissions] The loaded
  service definition directory is group/world-writable`. 9.6 also
  reclaims abandoned plugin copies itself after a one-hour grace; before
  that, a nightly 03:00 job left ~13 builds per night on disk.

## Reading the config without leaking it

Never `cat openclaw.json` into a session — it holds bot tokens, the
gateway token and API keys. Strip `//` comments and redact by key name:

```bash
ssh oriol@<claw> 'python3 - <<"EOF"
import json,re
s=open("/home/oriol/.openclaw/openclaw.json").read()
d=json.loads(re.sub(r"^\s*//.*$","",s,flags=re.M))
def red(o):
    if isinstance(o,dict): return {k:("<redacted>" if re.search("token|secret|key|password",k,re.I) else red(v)) for k,v in o.items()}
    if isinstance(o,list): return [red(x) for x in o]
    return o
print(json.dumps(red(d.get("channels",{})),indent=1))
EOF'
```

`plugins.entries.*.config` also carries keys (Brave) — redact it the same
way if you print it. `openclaw config get <path>` is safe for non-secret
paths; on a secret field it returns a `__OPENCLAW…` placeholder, not the
value — so a script that needs the real bot token must read the JSON5
file (comment-stripped) as above, on the box, and never print it.

## Updating (the procedure that worked, with the trap)

0. **Pre-flight the model, not just the channels**: `journalctl --user -u
   openclaw-gateway --since "2 days ago" | grep -c OAuthRefreshFailureError`
   and `openclaw models status`. emmaclaw had answered nothing for 27 h
   (Codex OAuth refresh 401, `model-fallback … auth_permanent next=none`)
   while `health` and `channels status` were green. Also `chmod 600
   ~/.config/systemd/user/openclaw-gateway.service` (and delete any
   `.bak`) **before** `update` — the updater then installs the new unit
   itself instead of failing on `[unsafe-permissions]`.
1. **Release notes first**: `gh api repos/openclaw/openclaw/releases
   --paginate -q '.[] | select(.tag_name|test("^v2026\\.9")) | .body'`
   and grep `Breaking`. Versions are CalVer; `npm view openclaw dist-tags`
   shows `latest` / `beta` / `extended-stable`. 2026.8+ needs **Node ≥
   24.16 or ≥ 26.1** (older truncates SQLite TEXT at embedded NULs) —
   24.18 qualifies. The other 2026.9 breaks are plugin-SDK only; official
   plugins follow the core.
2. **Backup on the box**: `tar --exclude=npm --exclude='*.sqlite-wal' -czf
   ~/backups/openclaw-pre-<ver>-$(date -u +%Y%m%dT%H%M%SZ).tgz -C ~ .openclaw`
   and `cp -a ~/.openclaw/openclaw.json ~/backups/openclaw.json.pre-<ver>`.
   64 MB on blakeclaw, 475–576 MB on the other two (workspace `media/`);
   `~/.openclaw` is 2–5 GB, mostly `npm/` cache and media.
3. `openclaw update --dry-run`, then `openclaw update 2>&1 | tee
   ~/backups/openclaw-update-<ver>.log`.
   **2026.9.5 (atomic updater) failed on petraclaw** after passing every
   candidate check: `Failed: global install swap … tree changed
   Installation recovery is unverified`, 9.4 left running (harmless), and
   `openclaw update repair` then refused ("The update parent owns Gateway
   activation"). The manual path worked on all three, ~4 min downtime:
   ```bash
   export TMPDIR=$HOME/.cache/openclaw-tmp
   systemctl --user stop openclaw-gateway.service
   npm i -g openclaw@<ver> --allow-scripts=openclaw
   openclaw doctor --fix --yes
   openclaw gateway install --force && systemctl --user daemon-reload
   systemctl --user reset-failed openclaw-gateway.service; systemctl --user start openclaw-gateway.service
   openclaw update repair --yes     # converges codex/brave/slack plugins to <ver>, restarts itself
   ```
   After it, doctor keeps printing `Plugin "codex" state migration is
   pending` — the agent works regardless (verified by real turns); left
   as is. **Same path for 9.5 → 9.6 (2026-09-27)** on all three, ~4 min
   each; `update repair` then reported "Skipped finalize:doctor and plugin
   convergence: supervised Gateway owner … is verified serving 2026.9.6"
   — fine, the plugins had already converged (check `plugins list`).
   **9.6 → 9.8 (2026-10-03)**, same path. Lessons: (a) **never stop the
   gateway until it has logged `[gateway] ready`** — a stop sent the same
   second blakeclaw became ready hung 5½ min until systemd's shutdown
   deadline (`abandoning unfinished cleanup`, SIGKILL); (b) `update repair`
   can refuse with `Doctor could not enter maintenance … Service inspection
   deadline expired` — do what it says: stop, `doctor --fix --yes`, start,
   wait for ready, `update repair --yes` again; (c) `gateway install
   --force` writes a unit `.bak` every run — delete it; (d) **2026.9.7
   changed a default: Slack and Discord accept other bots' messages when
   `allowBots` is unset** — set `channels.slack.allowBots false` (root
   level; per-account/per-room overrides exist) on every Slack claw and
   prove it with the redacted pre/post diff (exactly that one line);
   9.8 also adds `channels.slack.joinIntro` (default true: one intro post
   when the bot joins an allowed channel). 9.8 bundles Codex 0.158.0. The
   `update status` line "Plugin codex data/settings upgrade is unfinished"
   persists although doctor reports the deferred migration completed —
   turns work; left as is.
4. **THE TRAP (not deterministic)** — on blakeclaw and emmaclaw the
   updater's own doctor step failed (`Doctor could not enter maintenance…
   Gateway service ownership or shutdown could not be verified`), it
   reported `Update Result: ERROR`, yet the package WAS swapped and the
   service WAS restarted — **on the new version, which refuses to
   start**: `Gateway failed to start: OpenClaw state database schema
   migration required (audit-events-v2)`, unit `failed`, `status=78/CONFIG`.
   On petraclaw (same shape) the same command reported `Update Result:
   OK`, ran the migrations itself and the gateway came up — with two
   cosmetic tails: `Gateway install blocked: … [unsafe-permissions]` (the
   664 unit, see step 0) and `Doctor failed: ERR_MODULE_NOT_FOUND …
   doctor-health-*.js` (the old CLI process importing chunks the swap
   removed). Either way, do not re-run `update`; run the doctor once:
   ```bash
   systemctl --user stop openclaw-gateway.service
   openclaw doctor --fix --yes 2>&1 | tee ~/backups/openclaw-doctor-<ver>.log
   systemctl --user reset-failed openclaw-gateway.service
   systemctl --user start openclaw-gateway.service
   ```
   Doctor migrates (when the updater did not already): agent DB v1→v19,
   shared state to v15 + STRICT typing, config keys the new schema
   rejects (`meta.lastTouchedAt` → SQLite, `agents.defaults.memorySearch`
   → `memory.search`, `imageGenerationModel` → `mediaModels.image`,
   `gateway.tailscale.resetOnExit` removed, legacy model map →
   `agents.defaults.modelPolicy.allow`), **auth profiles → SQLite** (this
   is what revived emmaclaw's expired-looking Codex auth), channel
   `allowFrom` entries and pairing requests → SQLite (they also stay in
   the file), device pairings (`devices/*.json` → `.migrated`, imported at
   the next gateway start), cron store → SQLite (`cron/jobs.json` →
   `.migrated`; doctor's "Cron store normalized at …/jobs.json" wording is
   stale), `HEARTBEAT.md` → cron scratch, `TOOLS.md` merged into
   `AGENTS.md`, exec approvals, config audit log, provider catalogs. It
   refreshes the `codex` plugin itself, disables unusable skills
   (`model-usage` everywhere), prunes orphaned Codex session bindings
   (182 on petraclaw) and writes `openclaw.json.bak` (older ones rotate to
   `.bak.1…`). If the updater already migrated, a second doctor prints no
   `Auto-migrated` lines — that is fine. The session store moves from
   `sessions.json` to `agents/main/agent/openclaw-agent.sqlite`. **The
   workspace git repo is left dirty** (`HEARTBEAT.md`/`TOOLS.md` deleted,
   `AGENTS.md`/`MEMORY.md` modified) — do not commit it unasked.
5. **Unit reinstall** — `openclaw daemon status` will say the service is
   "out of date or non-standard" (old `OPENCLAW_SERVICE_VERSION`,
   `KillMode=control-group`, unsafe 664 perms). `gateway install --force`
   refuses while the unit or its `.bak` is group-writable:
   ```bash
   chmod 600 ~/.config/systemd/user/openclaw-gateway.service
   rm -f ~/.config/systemd/user/openclaw-gateway.service.bak
   openclaw gateway install --force     # writes KillMode=mixed, --max-old-space-size=2048
   systemctl --user daemon-reload && systemctl --user restart openclaw-gateway.service
   ```
6. **Plugins are pinned** to the version they were installed with and do
   not follow the core (`brave is pinned to @openclaw/brave-plugin@2026.7.1`).
   `openclaw plugins update <id>` only tells you so; use the package spec:
   `openclaw plugins update @openclaw/brave-plugin@latest` (and
   `@openclaw/slack@latest` where Slack is installed), then restart.
   `daemon status` shows `Plugin version drift: N active official plugin
   not on gateway <ver>` until every one is done. Plugin ids ≠ package
   names (`brave` = `@openclaw/brave-plugin`, `slack` = `@openclaw/slack`);
   `codex` is refreshed by doctor and stays on the unpinned spec
   `@openclaw/codex` (the security audit's "unpinned npm specs" warning is
   about that and pre-exists). Until the Slack plugin is updated the
   journal repeats `[channels] failed to load configuredState checker for
   slack: plugin module path not found` at each boot — expected noise.
7. **Verify — all of these, not one**:
   - `journalctl --user -u openclaw-gateway --since "2 min ago"` shows
     `[gateway] http server listening (N plugins: …)` and `[gateway] ready`
     with the expected plugin list (17–18 entries on 2026.9.4 incl.
     brave, slack where installed; blakeclaw's first boots listed only 6
     and still worked — the count is not a pass/fail signal, the named
     channel plugins are).
   - `openclaw health` (channels `configured`, event loop `ok`; a
     `degraded` event loop in the first seconds after boot is cold start).
   - `openclaw status --deep` → channel rows `OK`; tasks `no issues ·
     audit clean` — or N "issues" whose timestamps all predate the update
     (2026.9 imports the legacy cron run log; check `openclaw tasks list
     --json` before calling them regressions). A Telegram row `WARN …
     requireMention=false … Bot API privacy mode` is a new 2026.9 lint on
     unchanged config, not a regression.
   - `openclaw channels status --probe` → each channel `…, works`. On
     2026.9.4 the plain `channels status` no longer prints
     `health:healthy` or `in:/out:` ages and shows `token:***` — do not
     grep for the old wording. Slack: journal `[slack] socket mode
     connected` and no auth errors; "socket mode reports N active
     connections" is stale sockets after rapid restarts, pre-existing.
   - `openclaw models status` → the provider `status=usable`, and the next
     `Heartbeat (main)` run in `openclaw cron list` says `ok`.
   - a real turn: `openclaw agent -m "Reply with exactly: <HOST> OK <ver>"
     --timeout 90` and one that needs web search ("find the current
     OpenClaw version on npm") to prove the Brave key survived.
   - Telegram: inbound/outbound lines in the journal (`[telegram] outbound
     send ok`); nobody needs to message the bot for the update to be
     proven, but a DM from Oriol's phone is the end-to-end check.
   - `openclaw daemon status` — only the nvm warnings should remain.
     `Capability: read-only` is what 2026.9.4 prints on every claw (was
     `admin-capable`); commands still work — a renamed field, not a loss.
   - For a Slack claw, dump the redacted `channels.slack` before and after
     and diff: channel ids, `allowFrom`, every `systemPrompt` must be
     byte-identical (they were on emmaclaw).
8. Record: hq changelog line, the server file's Services row (version,
   date), and anything new here.

2026.9.4 also creates managed cron jobs on first boot — `Heartbeat
(main)` 30 m, `Memory Dreaming Promotion` 03:00, `Skill collection
review` 7 d — next to the user's jobs; expected.

Leftover warnings that are cosmetic: "Gateway service uses Node from a
version manager" (no system Node; the unit pins the absolute nvm path, so
a future `nvm install` of a new major needs `gateway install --force`
again); dead-lettered outbound entries in the delivery queue are old
undeliverable Telegram sends, not the update.

Rollback: `npm i -g openclaw@<old> --allow-scripts=openclaw` (npm ≥ 11.16
needs the flag), restore `~/.openclaw` from the tarball (the state DB
migration is one-way), `gateway install --force`, restart. Untested.

## Adding a Slack workspace (socket mode — no inbound URL, VM stays LAN-only)

1. `openclaw plugins install @openclaw/slack` (from a shell, then restart
   the gateway; `health` then says `Slack: not configured`).
2. **Oriol creates the app** (a workspace admin, in the *scope's*
   workspace): <https://api.slack.com/apps/new> → *From a manifest* →
   paste the manifest (template: hq
   `smartupsoft/docs/blakeclaw-slack-manifest.json` — bot user, `/blake`
   slash command, 23 bot scopes, `socket_mode_enabled`, 16 bot events;
   rename display/command per claw). Then *Basic Information → App-Level
   Tokens → Generate* with `connections:write` → `xapp-…`; *Install App →
   Install to Workspace* → Bot User OAuth Token `xoxb-…`; his member ID
   (`U…`, profile → ⋯ → Copy member ID) for the DM allowlist.
3. Tokens: if Oriol pastes them in chat (he did on 2026-09-17), write them
   straight to the box over ssh inside a heredoc, `config patch`, then
   ALSO into hq `homelab/secrets/slack-<scope>.env` (0600, gitignored) with
   a catalog entry in hq `CLAUDE.md` and a USER_TODO line to encrypt +
   rotate — never into a doc, and grep every command output for
   `xoxb|xapp` before it lands in the transcript (`sed -E
   's/(xoxb|xapp)[^ ]*/<redacted>/g'`). Otherwise stage on the box so he
   only fills a file: `~/slack-setup/{slack-app-
   manifest.json,tokens.env.example,apply.sh}` — `apply.sh` backs up the
   config, `openclaw config patch --file` a JSON5 with
   `channels.slack = {enabled, mode:"socket", botToken, appToken,
   dm:{enabled:true}, dmPolicy:"allowlist", allowFrom:[U…],
   groupPolicy:"allowlist", channels:{}, streaming:{mode:"partial",
   nativeTransport:true}}`, restarts, prints `channels status`. Tokens
   never go through chat; `tokens.env` is deleted after apply (they live
   in `openclaw.json`).
4. Channels. Resolve ids on the box with the bot token
   (`conversations.list?types=public_channel,private_channel` — the
   manifest has `channels:read`/`groups:read`; `auth.test` first). The bot
   **cannot join by API** (`conversations.join` → `missing_scope
   channels:join`, not in the manifest) — Oriol runs `/invite @<bot>` in
   each channel. Then `openclaw config set
   channels.slack.channels.<CHANNEL_ID> '{enabled:true,requireMention:true}'`
   per channel (JSON5 literal is accepted; `config get
   channels.slack.channels` shows the map) and restart the gateway;
   `requireMention:false` + a `systemPrompt` turns a channel into an inbox
   flow (emmaclaw's FACTURES REBUDES channel is the model: extract invoice
   data, one allowed write — a Holded purchase DRAFT). Same-named
   channels from earlier years exist (`seaotter2025` vs `seaotter2026`) —
   match the exact name.
5. Verify: `openclaw channels status --probe` → `Slack default: enabled,
   configured, running, connected, bot:config, app:config, works`
   (2026.9.4 wording; older printed `health:healthy`); journal `[slack]
   socket mode connected`; `config get channels.slack.allowFrom` lists
   the member ids; a DM from an allowlisted user gets a reply. Right
   after a restart Telegram may show `disconnected` for a few seconds —
   re-probe before calling it broken.

HTTP mode (`signingSecret`, `webhookPath`) needs a public URL — not for
LAN-only claws.

## Changing the model

```bash
openclaw models list --all --refresh --plain | grep gpt-6   # what the catalog offers
openclaw config set agents.defaults.modelPolicy.allow '["openai/gpt-5.5","openai/gpt-5.6-luna","openai/<new>"]'
openclaw models set openai/<new>
openclaw models fallbacks add openai/gpt-5.6-luna
```

Hot-reloaded, no restart. `models list --all` WITHOUT `--refresh` shows
only allowed models. A model not in `modelPolicy.allow` is refused, so
extend the list first (preserve per-box extras such as `gpt-5.6-sol`).
Proof it took: journal `[gateway] agent model: openai/<new>` on the next
boot, or a turn with no `model-fallback` line (a fallback still answers,
so "it replied" proves nothing).

**The OpenClaw catalog lags model releases — never conclude a model does
not exist from it.** 2026-09-23: Oriol asked for GPT-6 Luna (released the
day before); the catalog (`generated 2026-09-18`) listed only
`gpt-6-astra`, and Astra was set by mistake, then reverted. Check the
provider directly first — a Hermes one-shot (§ Hermes) or the Codex
release notes (`gh api repos/openai/codex/releases`).

**2026-09-27 resolution**: 2026.9.6's catalog lists `gpt-6-luna`,
`gpt-6-sol`, `gpt-6-astra` and a turn on `openai/gpt-6-luna` works with no
fallback — although its Codex runtime is still **0.155.1**. So the 400
below was the client-side model catalog, not a backend version floor:
once the catalog knows the model, it works. Switch with a gateway
**restart** after `models set`, not just the hot reload — the first
post-switch turn otherwise hits the "session policy handoff" wedge; and
re-check `models status` after `models set` (on blakeclaw it silently did
not stick the first time).

**A model the catalog lacks can be registered by hand** —
`openclaw config set models.providers.openai.models '[{"id":"<id>","name":"<id>"}]'`
(without it: `Unknown model … no matching models.providers["openai"].models[]
entry`) — **but through Codex the backend gates models by the Codex
client version**: GPT-6 Luna/Sol need `@openai/codex` ≥ 0.156.1, and
`@openclaw/codex` 2026.9.5 pins 0.154.0 → HTTP 400 *"The 'gpt-6-luna'
model is not supported when using Codex with a ChatGPT account."* Check
the pin with `npm view @openclaw/codex dependencies.@openai/codex`. Remove
the hand entry (`config unset models.providers.openai`) once the catalog
has the model. After several live model switches a Codex thread can wedge
(*"Codex session policy handoff failed … did not confirm unloading its
previous configuration"*) — restart the gateway.

## Hermes (Nous Research Hermes Agent, on the same VMs)

State: hq `shared/docs/hermes.md`. `~/.hermes/hermes-agent` is a **shallow
git checkout** (`.install_method` = git), venv `./venv`, `uv` at
`~/.hermes/bin/uv`, CLI `~/.hermes/hermes-agent/venv/bin/hermes` (not on
PATH), config `~/.hermes/config.yaml`, secrets `~/.hermes/.env` and
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
ssh oriol@<vm> 'mkdir -p ~/backups' && scp skills/openclaw/scripts/hermes_post_checkout.py oriol@<vm>:backups/
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

Both runtimes are watched by user timers `assistant-healthcheck@{openclaw,hermes}`
→ healthchecks.io (service active + HTTP only — a dead model login stays
green) — an outage during an update will page.

## Pre-flight: a stranded Codex login (emmaclaw, since 2026-09-25)

`health`, `channels status --probe` and the healthchecks.io probe all
stay green while the agent cannot answer at all. Symptom: every turn →
`Explicit auth order for openai has no usable profiles`, `openclaw cron
list` shows `Heartbeat (main) … error (34x)`, `models status` →
`effective=missing:missing | status=missing`, `models auth list` shows
every `openai:*` profile with `expires 1970-01-01`. Cause on 2026.9.5: a
plugin reload during an OAuth refresh (`OAuth token refresh failed for
openai: Plugin openai was reloaded or disabled` → `auth profile
"openai:default" is no longer available`) — fixed in 2026.9.6 ("retiring
catalog workers now wait for already-started OAuth refreshes"), but an
already-stranded login needs a fresh sign-in. `models auth activate
<profile>` does NOT revive it. Recovery needs Oriol's browser:

```bash
setsid nohup script -qfc "openclaw models auth login --provider openai --device-code --profile-id openai:default" ~/backups/openai-login.log >/dev/null 2>&1 </dev/null &
sleep 30; sed -E 's/\x1b\[[0-9;?]*[A-Za-z]//g' ~/backups/openai-login.log | grep -E 'URL:|Code:'
```

He opens `https://auth.openai.com/codex/device`, enters the code (15 min
validity) and signs in as oriolj@gmail.com; the log ends `Script done`.
Pre-flight this on every visit: `openclaw models status | grep status=`
must say `usable`, and `openclaw cron list | grep Heartbeat` must not say
`error`.

## Telegram

Already on all three: `channels.telegram = {enabled, botToken, dmPolicy,
groupPolicy, streaming}`, bot names like `@blackeclaw_bot`, DM allowlist
migrated into SQLite state by doctor (config `allowFrom` entries were
moved). `[telegram] Plugin command "/dashboard" conflicts…` and "menu text
exceeded … budget" at startup are harmless.

## Cron jobs and where their output goes (2026.9.4)

Two kinds, and the difference decides whether a reminder reaches anyone:

- `sessionTarget: isolated` + `agentTurn` payload + `delivery: {mode:
  announce, channel, to}` — the runner delivers the final text to a fixed
  destination (`openclaw cron edit <id> --announce --channel telegram --to
  <chat id> --best-effort-deliver`). Deterministic. petraclaw's jobs are
  built this way (`announce telegram:5095664`).
- `sessionTarget: main` + `systemEvent` payload — the event is injected into
  the main session at the next heartbeat and **the model decides whether
  and where to send** with the message tool; `delivery` is refused for
  main-session jobs (`cron channel delivery config is only supported for
  sessionTarget="isolated"`). Emma's *Ampliació de capital* and Blake's
  three BikeCRM checks are this kind.

**Trap (emmaclaw, 2026-09-18, first run after the update)**: with no
destination in the payload the model passed `telegram` as the target and
2026.9.4's message tool resolved it as the username **`@telegram` =
"Telegram News", chat `-1001005640892`** → `403 Forbidden: bot is not a
member of the channel chat`, and Emma DMed Oriol a Catalan apology
instead of the reminder. Before the update the same job had defaulted to
his DM. The next manual run picked the DM again — it is a guess per run.
Fix applied: the payload text now ends with an explicit "LLIURAMENT: …
chat_id 5095664 (target telegram:5095664), no other destination". Rule:
**every main-session job that must reach a human names the exact
destination (`telegram:<chat id>` / `slack:channel:<id>`) in its payload**;
or make it isolated + announce when it does not need the main session's
memory. Diagnose with the file log (`/tmp/openclaw/openclaw-<date>.log`,
subsystem `gateway/ws` carries the `chat_id`) — the journal line does not
show the chat id. Verify a Telegram id with the Bot API on the box:
`getChat?chat_id=@name` (public channels) — never from a workstation with
the token.

`openclaw cron run <id>` runs a job now (a real send — the human gets a
duplicate reminder); `cron show <id>` prints `last delivery` only for
isolated jobs.

## Useful commands

```
openclaw --version · openclaw daemon status · openclaw health · openclaw status [--deep]
openclaw channels status · openclaw plugins list · openclaw plugins info <id>
openclaw config get|set|patch|validate · openclaw doctor [--lint] [--fix --yes]
openclaw gateway install --force · openclaw agent -m "…" --timeout 90 · openclaw logs
openclaw security audit --deep   (run before exposing anything)
```

## Rules

- Accounts follow the scope: a claw's Slack/Telegram/model keys are that
  scope's; catalogue new ones in hq `homelab/secrets/` per the
  `secrets-in-git` skill when they exist outside the box.
- Update one claw, verify, then the others (emmaclaw: re-verify Slack
  after any update — it is the production invoice inbox).
- Everything verified on a box goes to its hq server file the same turn;
  new mechanics go here.
