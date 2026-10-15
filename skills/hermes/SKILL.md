---
name: hermes
description: Operate Hermes Agent (Nous Research) on the estate's agent VMs ("claw agents" — the personal, EnaCast and BikeCRM/SmartupSoft agents on the home Proxmox host, formerly petraclaw/emmaclaw/blakeclaw) — install shape, the CLI per user (not root), the tag-pinned update with its post-checkout driver and rollback, model and fallback switch, built-in memory limits (MEMORY.md/USER.md char caps) and where larger knowledge goes, importing from OpenClaw (`hermes claw migrate` and the underlying script with --include, the overflow trap, cron jobs it cannot see), Discord, Sign in with ChatGPT, healthchecks. Use when the user mentions Hermes, `hermes-gateway`, `hermes claw migrate`, the agents' memory or skills, Pep/Enzo/Bru (or the old Petra/Emma/Blake), a claw agent VM, or connecting an agent to Discord/Telegram/Slack/email through Hermes.
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

Both runtimes are watched by user timers `assistant-healthcheck@{openclaw,hermes}`
→ healthchecks.io (service active + HTTP only — a dead model login stays
green) — an outage during an update will page.

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
  reads (the 2026-07-23 run spilled ~11 KB on petraclaw, mostly emmaclaw's
  repeated daily reminders there). It also imports entries verbatim and
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
  running after the increase was cancelled; Bru's Daniela follow-up after
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

## Rules

- Update one VM, verify, then the others.
- Back up `~/.hermes` before any migration or update (`umask 077`, exclude
  `hermes-agent/venv` and `node_modules`; `.env` and `auth.json` are inside).
- Verified per-box facts go to the hq server file the same turn; mechanics here.
