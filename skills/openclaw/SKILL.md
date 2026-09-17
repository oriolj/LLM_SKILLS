---
name: openclaw
description: Operate the estate's OpenClaw agent VMs (petraclaw = personal, emmaclaw = Enantena, blakeclaw = SmartupSoft/BikeCRM — self-hosted personal-AI-agent gateways on the home LAN) — how they are installed (nvm Node, npm global, user systemd unit), the safe update procedure and the trap where `openclaw update` leaves the gateway DOWN on a pending state-DB migration, plugin version pins, the systemd unit reinstall, adding a Slack workspace (socket mode, manifest, tokens, allowlists), adding Telegram/other channels, reading the config without leaking secrets, and the verification that proves an update or a channel actually works. Use when the user mentions OpenClaw, petraclaw/emmaclaw/blakeclaw, "the claw", updating an agent VM, connecting an agent to Slack/Telegram/WhatsApp, `openclaw doctor`, a gateway that will not start, or plugin drift warnings.
---

# OpenClaw — the three agent VMs

**What OpenClaw is, the risks and the estate state live in hq
[`shared/docs/openclaw.md`](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/shared/docs/openclaw.md)**;
per-box facts in `hq/docs/servers/<name>.md`
([blakeclaw](/home/oriol/Syncthing/Syncthing-mobile-docs/hq/docs/servers/blakeclaw.md)
exists; petraclaw/emmaclaw pending). This skill is the *mechanics*. Verified
on blakeclaw 2026-09-17 (2026.7.1-2 → 2026.9.4); update the notes here when
a step changes.

## The estate model — one VM per scope, accounts follow the scope

| VM | Scope | LAN IP | Channels (2026-09-17) |
|---|---|---|---|
| petraclaw | personal (oriolj) | `192.168.7.73` | Telegram |
| emmaclaw | Enantena / EnaCast | `192.168.7.217` | Telegram + Enantena Slack (8 channels, one is an invoices-inbox → Holded purchase-draft flow) |
| blakeclaw | SmartupSoft / BikeCRM | `192.168.7.187` | Telegram; SmartupSoft Slack plugin installed, tokens pending |

Proxmox VMs on the home `proxmox` host (`.179`), Ubuntu 25.04, **LAN only**
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
  model `openai/gpt-5.6-luna` via the **Codex** plugin.

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
way if you print it. Prefer `openclaw config get <path>` for single values.

## Updating (the procedure that worked, with the trap)

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
   ~64 MB; `~/.openclaw` is ~2 GB mostly `npm/` cache.
3. `openclaw update --dry-run`, then `openclaw update 2>&1 | tee
   ~/backups/openclaw-update-<ver>.log`.
4. **THE TRAP** — on our units the updater's own doctor step fails
   (`Doctor could not enter maintenance… Gateway service ownership or
   shutdown could not be verified`), reports `Update Result: ERROR`, yet
   the package IS swapped and the service IS restarted — **on the new
   version, which refuses to start**: `Gateway failed to start: OpenClaw
   state database schema migration required (audit-events-v2)`. The
   gateway is down from this moment. Do not re-run `update`; finish by
   hand:
   ```bash
   systemctl --user stop openclaw-gateway.service
   openclaw doctor --fix --yes 2>&1 | tee ~/backups/openclaw-doctor-<ver>.log
   systemctl --user reset-failed openclaw-gateway.service
   systemctl --user start openclaw-gateway.service
   ```
   Doctor migrates: agent DB v1→v19, config keys the new schema rejects
   (`meta.lastTouchedAt`, `agents.defaults.imageGenerationModel`,
   `agents.defaults.memorySearch`, `gateway.tailscale.resetOnExit` → moved
   to SQLite state), device pairings (`devices/*.json` → `.migrated`),
   `HEARTBEAT.md` → cron scratch, `TOOLS.md` merged into `AGENTS.md`,
   exec approvals, config audit log. It also disables unusable skills
   (`model-usage` on blakeclaw) and writes `openclaw.json.bak`.
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
   `openclaw plugins update @openclaw/brave-plugin@latest`, then restart.
   `daemon status` shows `Plugin version drift: N active official plugin
   not on gateway <ver>` until every one is done. Plugin ids ≠ package
   names (`brave` = `@openclaw/brave-plugin`, `slack` = `@openclaw/slack`).
7. **Verify — all of these, not one**:
   - `journalctl --user -u openclaw-gateway --since "2 min ago"` shows
     `[gateway] http server listening (N plugins: …)` and `[gateway] ready`
     with the expected plugin list (brave is a capability plugin and is
     NOT in that list — that is normal).
   - `openclaw health` (channels `configured`, event loop `ok`; a
     `degraded` event loop in the first seconds after boot is cold start).
   - `openclaw status --deep` → channel rows `OK`, tasks `no issues · audit
     clean`.
   - a real turn: `openclaw agent -m "Reply with exactly: <HOST> OK <ver>"
     --timeout 90` and one that needs web search ("find the current
     OpenClaw version on npm") to prove the Brave key survived.
   - Telegram: inbound/outbound lines in the journal (`[telegram] outbound
     send ok`); nobody needs to message the bot for the update to be
     proven, but a DM from Oriol's phone is the end-to-end check.
   - `openclaw daemon status` — only the nvm warnings should remain.
8. Record: hq changelog line, the server file's Services row (version,
   date), and anything new here.

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
3. Stage on the box so he only fills a file: `~/slack-setup/{slack-app-
   manifest.json,tokens.env.example,apply.sh}` — `apply.sh` backs up the
   config, `openclaw config patch --file` a JSON5 with
   `channels.slack = {enabled, mode:"socket", botToken, appToken,
   dm:{enabled:true}, dmPolicy:"allowlist", allowFrom:[U…],
   groupPolicy:"allowlist", channels:{}, streaming:{mode:"partial",
   nativeTransport:true}}`, restarts, prints `channels status`. Tokens
   never go through chat; `tokens.env` is deleted after apply (they live
   in `openclaw.json`).
4. Channels: invite the bot, then `openclaw config set
   channels.slack.channels.<CHANNEL_ID> '{enabled:true,requireMention:true}'`
   per channel; `requireMention:false` + a `systemPrompt` turns a channel
   into an inbox flow (emmaclaw's FACTURES REBUDES channel is the model:
   extract invoice data, one allowed write — a Holded purchase DRAFT).
5. Verify: `openclaw channels status` → `Slack default: enabled,
   configured, running, connected, … health:healthy`; a DM from the
   allowlisted user gets a reply; journal shows `[slack]` lines.

HTTP mode (`signingSecret`, `webhookPath`) needs a public URL — not for
LAN-only claws.

## Telegram

Already on all three: `channels.telegram = {enabled, botToken, dmPolicy,
groupPolicy, streaming}`, bot names like `@blackeclaw_bot`, DM allowlist
migrated into SQLite state by doctor (config `allowFrom` entries were
moved). `[telegram] Plugin command "/dashboard" conflicts…` and "menu text
exceeded … budget" at startup are harmless.

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
