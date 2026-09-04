---
name: secrets-in-git
description: Manage credentials for PRIVATE PERSONAL repos by committing them age-encrypted, so every machine (and every agent session) has the same secrets after a clone — without a secret manager. Use when the user asks "can we commit the .env encrypted", "where do I put this API key / token / password", "add a secret to hq", "version the secrets", "share .env between my machines via git", "back up the Coolify envs", "rotate this token", when a token that used to work returns 401/403, when a fresh clone or new host is missing its secrets, when an agent needs a credential that "should be somewhere", or when writing/reviewing a Makefile encrypt/decrypt target, a secrets/ .gitignore, or an ansible task that deploys a credential. Covers the whole lifecycle: the store layout (one dir, one file per provider×scope, deny-all gitignore with !*.enc, any extension, directories as one tarball), the two modes and how to choose (sops+age keypair = per-value diffs + agents can encrypt/decrypt autonomously; age -p passphrase = nothing on disk but interactive-only, agents can neither encrypt nor decrypt — Oriol's repeated explicit choice for hq, honor it), the once-per-run passphrase Makefile (util-linux script pty), the FILE= single-file re-encrypt rule (age output is randomised — a full re-encrypt destroys the diff), make secrets-status (the only freshness check an agent can run), the agent handoff (plaintext + catalog entry + USER_TODO item; never the value in chat; the auto-mode classifier refuses secret writes — stop after ONE refusal), the CLAUDE.md catalog contract (keys by NAME, account/scope, dates, lifetime, consumers, parse rule), token lifetimes and rotation (30-day Coolify tokens, IP-locked Cloudflare tokens, write-once tunnel tokens, "went through chat → rotate"), exporting secrets that exist only in a SaaS store (Coolify env backup per team), and deploying from the store (ansible reads the controller's decrypted plaintext with a stat + warn-and-skip; servers never see the passphrase). HARD SCOPE LIMIT — personal private repos ONLY, never professional repos public OR private; those get a real secret manager.
---

# Secrets in git — the committed encrypted store (personal repos only)

Field-tested on hq (Oriol's homelab monorepo: ~25 credentials in
`homelab/secrets/`, age passphrase mode, consumed by ansible, agents and
CLI tools on every machine since 2026-08-08; passphrase-once Makefile
since 2026-09-03) and busy-bar (`homelab/busy-bar/`, sops + age keypair,
2026-08-08). Reference implementation: hq's root `Makefile` and the
"Secrets" section of hq's `CLAUDE.md`.

## Scope rule — read this first

Committing encrypted secrets is acceptable **only for private personal
repos** (hobby projects, homelab, single-owner tooling). It is NOT for:

- **Professional public repos** — obviously.
- **Professional private repos** — also no. Access to the repo outlives
  employment/contract changes (forks, clones on old laptops, CI caches),
  the passphrase inevitably spreads through insecure side channels,
  rotation requires a git commit, and git history preserves every
  previously-committed ciphertext forever (whoever later obtains the
  passphrase decrypts ALL historical secrets, including rotated-away
  ones). Professional projects use a secret manager (Vault, cloud KMS/SM,
  Coolify's env store, CI secrets) — the repo carries only references.

If the user asks for this on a work project, say the above and offer the
secret-manager path instead. Company credentials that a PERSONAL repo
must hold anyway (hq holds the Enantena Coolify token so agents can
deploy) are fine — the repo is personal and never leaves Oriol's
machines; the rule is about who can reach the repo, not whose account the
token belongs to.

## The model: three places a secret lives

1. **The provider / SaaS store** — Coolify env vars, Vercel env, the
   provider's own dashboard. Runtime source of truth for the deployed app.
2. **The repo's encrypted store** — `secrets/*.enc`, committed. The
   durable copy and the cross-machine carrier: a fresh clone + one
   `make secrets-decrypt` restores everything.
3. **Per-machine plaintext** — the gitignored decrypted siblings in the
   working tree, and whatever ansible copied out of them
   (`~/.config/resend/env`, `~/.config/tplink-m7010/password`, …).

Rules that follow:

- **Every credential an agent or a machine needs exists in (2).** A value
  that only exists in (1) — a generated Django `SECRET_KEY`, a magic DB
  password, a metrics token pasted into a Coolify UI — is one lost
  instance away from gone: export it into (2) (see "Exporting from SaaS
  stores").
- **A value that exists only in (3) on one machine is a pending item**,
  not a finished task: it needs encrypting and committing before the
  session ends, and until then `USER_TODO.md` says so.
- **Chat is not a place.** Never ask for a value in chat, never print
  one, never paste one into a commit message or a doc. A secret that
  went through chat gets rotated (write that in the TODO item).

## Choosing the mode

Two workable modes; the deciding question is **who needs to run the
encryption**:

- **sops + age keypair** (busy-bar, 2026-08-08): per-value encryption
  (`FOO=ENC[AES256_GCM,...]` per line — diffs show WHICH var changed) and
  non-interactive, so agents/scripts keep `.env.enc` fresh autonomously
  after every `.env` edit. Cost: the private key is a file that must be
  backed up outside the repo.
- **age -p passphrase** (hq): nothing on disk to back up, passphrase in
  the owner's head. Cost: whole-file blob (no per-var diffs) AND
  interactive-only — **agents can neither encrypt nor decrypt**, so the
  committed copy goes stale unless the owner runs the make target after
  each change (busy-bar's first attempt at this mode never produced the
  encrypted file at all).

**sops does not support passphrases** (recipients only: age keys, KMS,
GPG) — passphrase mode means plain `age -p` and losing sops's per-value
format. Default to sops+age keypair unless the owner explicitly insists
on a passphrase and accepts the staleness risk. Oriol has insisted on
passphrase mode twice (busy-bar initially, hq 2026-08-08 even after the
keypair default was scaffolded) — when he asks, state the trade-off once,
then build passphrase mode without re-litigating.

## Layout of the store (hq reference)

```
homelab/secrets/            # deny-all except *.enc in the ROOT .gitignore (see below)
  resend.env            # plaintext, gitignored, chmod 600
  resend.env.enc        # committed, ASCII-armored age
  cdmon.env(.enc)       # enacast CDmon account
  cdmon-oriolj.env(.enc)# personal CDmon account — same provider, other scope
  fish-ai.ini(.enc)     # any extension works; the pipeline is extension-agnostic
  vpn/                  # a DIRECTORY of client configs …
  vpn.tar.gz.enc        # … committed as ONE tarball
```

- **One directory per repo, one file per provider × scope.** Name files
  `<provider>[-<scope>].env` (`coolify.env` = the company team,
  `coolify-oriolj.env` = the personal team). Accounts follow the scope, so
  the file name must say which account a key belongs to — an agent
  picking "the Coolify token" must not be able to pick the wrong one by
  accident. Generated per-app values get their own file (`fichachat.env`,
  `h2a-accountant.env`), exports get theirs (`coolify-envs.env`).
- **Prefix the keys with the scope when two accounts of one provider
  coexist**: `COOLIFY_API_TOKEN` vs `COOLIFY_ORIOLJ_API_TOKEN`,
  `ENACAST_CLOUDFLARE_*` vs `ORIOLJ_CLOUDFLARE_*`. Same reason.
- **Deny-all gitignore, allow only the ciphertext** — a stray plaintext
  with any extension (`.ini`, `.json`, `.txt`, no extension, editor
  backups) can never be committed:

  ```gitignore
  homelab/secrets/*
  !homelab/secrets/*.enc
  ```

  Put those two lines in the repo's ROOT `.gitignore`, not in a
  `.gitignore` inside the secrets dir: the encrypt loop runs with
  `dotglob` (dot-named secrets must not be skipped), so a `.gitignore`
  living there would be encrypted along with everything else.

- **A header comment in every plaintext** saying what it is, which
  account, and who consumes it (which ansible tag, which tool). The
  ciphertext is opaque, so the header is the only in-file documentation
  the next reader gets after decrypting.
- **Directories go in as one tarball** (`vpn/` → `vpn.tar.gz.enc`):
  age -p output is opaque either way, so per-file would not buy readable
  diffs, and one unit is easier to restore.
- **Never `source` a secrets file.** Values carry `#`, `$`, spaces,
  quotes; some files repeat keys across blocks. Read one key with
  `grep '^KEY=' file | cut -d= -f2-`, or a tiny `env_get` helper.
- Keep the decrypted plaintext `chmod 600`; the Makefile enforces it.

## The Makefile (passphrase mode)

The full, current version lives in hq's root `Makefile`; copy from there
rather than from memory. What it does and why:

- **`make secrets-encrypt`** — every plaintext in the dir → `*.enc`
  (`-a` ASCII armor, so the committed file is text), plus the `vpn/`
  tarball. **`FILE=homelab/secrets/x.env` does ONE file** — this is the
  normal way to use it: age output is randomised, so re-encrypting an
  untouched secret rewrites its ciphertext completely and the commit
  diff can no longer show that only the intended plaintext changed. A
  full run is for the initial import or after a passphrase change.
  `VPN=1` adds the tarball. Skips editor/merge leftovers (`*~`, `*.bak`,
  `*.orig`, `*.rej`, `*.sw?`, `*.tmp`) with a warning instead of
  committing them as secrets. Refuses a `.enc` passed as `FILE`.
- **`make secrets-decrypt`** — every `*.enc` → plaintext, `umask 077` +
  temp file + `mv` (never a half-written secret), `chmod 600`, and
  **skips a file whose plaintext is newer than its ciphertext** (that
  plaintext is an unencrypted edit — re-encrypt it or delete it to force).
  Sets the plaintext's mtime to the ciphertext's (`touch -r`) so a fresh
  clone's decrypt does not look like a stale edit afterwards.
- **`make secrets-status`** — read-only, no passphrase, **the one target
  agents can run**: per file `current` / `stale` (plaintext newer than
  `.enc`) / `not encrypted` (plaintext without `.enc`) / `not decrypted`
  (`.enc` without plaintext here), the `vpn/` tarball the same way, and
  any uncommitted `.enc` changes. Exits non-zero when something needs doing. Run
  it before asking Oriol to encrypt anything and before claiming the
  store is current.
- `SHELL := /bin/bash` + `.SHELLFLAGS := -eu -o pipefail -c` — without
  pipefail a broken `tar | age` reports only the last command's status
  and the recipe prints success over missing secrets.
- `shopt -s dotglob` — dot-named secrets were silently skipped before.

### Ask for the passphrase once per run, not once per file

age reads the passphrase from `/dev/tty` and nothing else — no flag, no
env var, no stdin fallback — so a naive loop prompts for every file
(twice each on encrypt). With ~25 secrets that is 50 prompts. The fix
(hq, 2026-09-03): `read -rs` it once from `/dev/tty` (+ a confirmation
on encrypt), then feed it to each `age` through a pseudo-terminal that
util-linux `script` lends:

```bash
{ : </dev/tty; } 2>/dev/null || { echo "error: no terminal" >&2; exit 1; }
IFS= read -rsp "age passphrase: " pw </dev/tty; echo >/dev/tty
run_age() {          # run_age <age args>; passphrase in $pw
    printf '%s\n%s\n' "$pw" "$pw" \
        | SHELL=/bin/bash script -qefc "$(printf '%q ' age "$@")" /dev/null >/dev/null \
        || { echo "error: age failed on ${@: -1} (wrong passphrase?)" >&2; return 1; }
}
run_age -p -a -o "$f.enc" "$f"      # encrypt (reads pw twice)
run_age -d -o "$out" "$f.enc"       # decrypt (reads pw once, ignores the 2nd line)
```

Details that matter: probe `/dev/tty` in its own `2>/dev/null` block and
keep the `read` outside it — `read -p` prints its prompt on stderr, so
wrapping the read silently hides the prompt and the run looks hung (the
first version shipped like that); `printf` is a builtin, so the
passphrase never appears in an argv or `/proc`; `SHELL=/bin/bash` because
`script -c` runs the command through `$SHELL` and the `%q` quoting is
bash's (Oriol's login shell is fish); `-e` propagates age's exit code, so
a wrong passphrase still aborts; `>/dev/null` hides the pty output
because the passphrase can be echoed there before age switches the tty
to no-echo — never print that output on failure, print a fixed message;
anything piped to age (a tarball) has to go through a temp file, since
stdin now carries the passphrase. `script -V` distinguishes util-linux
from BSD `script` (macOS: no `-c`/`-e`) — fall back to plain `age` there.

**This does NOT let agents run it**: there is still no tty in an agent
shell, and the read fails with a clear error. Never try to pipe the
passphrase in from an agent, never ask for it in chat.

## The agent workflow

### Adding or changing a secret

1. **Write the plaintext** into the store (`homelab/secrets/<name>.env`,
   header comment, `chmod 600`), or edit the existing file. In Claude
   Code's auto mode the permission classifier may refuse writes that
   look like credentials (it did for Coolify/Vercel env writes,
   2026-09-02) — **after ONE refusal stop retrying**, put the exact file
   and keys (names, not values — the values go nowhere until Oriol
   switches the session to manual mode) in `USER_TODO.md`, and say so.
2. **Catalog it** in the repo's `CLAUDE.md` secrets list the same turn
   (contract below).
3. **Add the `USER_TODO.md` item**: `make secrets-encrypt FILE=<path>`,
   then commit the `.enc`; *why you*: the age passphrase; *blocked
   until then*: the plaintext exists only on this machine. One item per
   file, or one item listing all the files of the turn.
4. **Commit** the catalog + TODO with the work that created the secret.
   The plaintext cannot be committed (deny-all gitignore) — do not fight
   that.
5. **After Oriol encrypts** (the `.enc` appears / changes in the working
   tree): run `make secrets-status`, `git add` the `.enc`, commit it
   ("secrets: x.env.enc committed (Oriol encrypted <date>)"), remove the
   TODO item, and mark the catalog entry "encrypted + committed <date>".
   Committing the ciphertext is the agent's job — this is the established
   pattern in hq's history.

### Reading a secret

- `make secrets-status` first if anything looks missing. Plaintext
  absent → the machine has not decrypted yet: TODO item asking for
  `make secrets-decrypt` (fresh clone / new host), never a request for
  the value.
- Read the one key you need (`grep`/`cut`), pass it through an env var
  or a header, never echo it, never put it in a log line or a doc.
- Machines that share the working tree through Syncthing already carry
  the plaintext (gitignored files sync too, mtimes preserved) — they do
  not need the passphrase. The encrypted copy still has to be current:
  a fresh clone, a rebuilt host and git history are the recovery path.

### Never

- Print, paste or commit a value; ask for a value or the passphrase in
  chat; try to work around the tty (pipe, expect, `script` from an agent
  shell).
- `source` a secrets file; `git add -A` inside the secrets dir (the
  gitignore protects, but a sibling session's `git add -A` can still
  sweep YOUR staged `.enc` into its commit — commit small, commit soon).
- Re-encrypt everything to change one file (`FILE=`).
- Use one scope's token for another scope's account because it happens
  to be at hand (accounts follow the scope; the file name tells you
  which).
- Deploy an IP-locked / workstation-only token to a server.

## The CLAUDE.md catalog contract

The repo's `CLAUDE.md` carries **one bullet per secrets file**, and it is
the only reason future sessions do not "fix" a missing credential by
asking for one that is already committed. Each bullet says:

- **what it holds, keys by NAME** (`COOLIFY_ORIOLJ_API_TOKEN`,
  `COOLIFY_ORIOLJ_API_URL`) — never a value, never a fragment of one;
- **which account and scope** (personal / company X / shared), and the
  sibling file for the other scope when one exists;
- **status and dates**: "EXISTS since 2026-08-28", "encrypted +
  committed 2026-09-02", "plaintext only until Oriol encrypts — see
  USER_TODO.md", "PARKED (tier has no API)", or "may legitimately be
  EMPTY" for write-once tokens;
- **lifetime and rotation**: expiry (Coolify Cloud API tokens: 30 days,
  root permission), IP lock (personal Cloudflare token: workstation
  egress IP, rotated every 30 days), no expiry (AWS IAM key), write-once
  (Cloudflare tunnel tokens — only needed to seed a host);
- **what a failure means**: a 401/403 on a token that used to work =
  expired or rotated → ask Oriol for a new one, never retry or work
  around it;
- **consumers**: which ansible role/tag deploys it and where it lands on
  the target, which tool or script reads it, which hub/app holds the same
  value under which name (a metrics token lives in the app's Coolify env
  AND in the monitoring hub's config — name both, so a rotation touches
  both);
- **how to parse** when it is not a plain `KEY=value` file (`# ---
  resource` blocks with repeating keys; "never `source`").

Correct a stale bullet in place; never append a contradicting one.

## Token lifetimes and rotation

- **Rotation = new value at the provider → edit the plaintext →
  `make secrets-encrypt FILE=…` → commit the `.enc` → update every
  consumer that holds a copy** (Coolify env, hub config, the deployed
  `~/.config/...` file via the ansible tag). The catalog's "consumers"
  line is the checklist.
- **Git history keeps every old ciphertext forever.** Changing the
  passphrase does not un-leak anything already committed; if the
  passphrase leaks, every secret ever committed under it is compromised
  and must be rotated at the provider. Rewriting history is not an option
  in a Syncthing-synced repo (peers diverge) and does not help against
  existing clones anyway.
- **"It went through chat" → rotate**, and say so in the TODO item.
- **Scoped tokens beat root tokens** where the provider allows it
  (Route53 key that can write one zone; R2 token scoped to one bucket
  without IP filter for a server that must upload backups, while the
  IP-locked account token stays on the workstation).
- **Write-once tokens** (tunnel tokens the ansible role only needs to
  seed `/etc/cloudflared/cloudflared.env` once): the secrets file may be
  empty between provisions; that is not an error and not a reason to ask
  for the token unless a host is being (re)provisioned.

## Exporting from SaaS stores

Values generated or pasted inside a provider (Coolify magic
`SERVICE_PASSWORD_*`, a Django `SECRET_KEY` typed into the UI, metrics
tokens, admin paths) exist only in that provider's database. Losing the
instance loses them: signed sessions and tokens die, DB volumes become
unreachable without their password. So:

- Keep an **export tool** that dumps every resource's runtime env into
  the store — hq: `homelab/tools/coolify-env-backup.py` (`--scope
  oriolj` for the personal team) → `coolify-envs.env` /
  `coolify-envs-oriolj.env`, one `# --- resource` block per resource.
- **Re-run it after every first deploy and every env change**, then the
  owner re-encrypts that ONE file (`FILE=`) — add the TODO item in the
  same turn the deploy happens.
- Keys repeat across blocks: parse by block, never `source`.
- Same idea for anything else that only lives in a provider: DNS API
  tokens are re-issuable, generated app secrets are not — export the
  latter.

## Deploying from the store (automation that must push a secret)

Automation (ansible pushing a config to machines, cron scripts) can
never decrypt mid-run in passphrase mode. The working pattern (hq
`homelab/ansible`, roles `development/email-cli`, `dotfiles/tplink-m7010`,
`shell/fish-ai`, `syncthing/gui-auth`):

- The play reads the **controller's gitignored decrypted plaintext**
  (`stat` with `delegate_to: localhost`), copies it to the target with
  `mode: '0600'` and `no_log: true`, or extracts one key into a
  single-purpose file (`~/.config/tplink-m7010/password`).
- **Guard + warn-and-skip**: when the plaintext is missing the role
  installs the tool anyway and prints "run `make secrets-decrypt` at the
  repo root and re-run with --tags X" instead of failing the play.
- **Seed, don't manage**, for write-once credentials: write the file only
  when a token is provided AND the file does not exist; re-runs manage
  the non-secret lines only (`shared/ansible` `cloudflared` role).
- Targets never see the passphrase or the ciphertext. Servers never get
  the whole store — only the one value they need.
- Ansible mechanics (delegate_to, lookup on the controller, check mode):
  the `ansible-gotchas` skill.

## Setup (sops + age keypair — busy-bar)

Install from the system package manager (`pacman -S sops age`; both are
also single static binaries droppable into `~/.local/bin`).

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt   # sops auto-discovers this path
```

`.sops.yaml` committed at the repo root:

```yaml
creation_rules:
  - path_regex: \.env$
    age: age1<recipient-public-key>
```

⚠️ **`path_regex` matches the INPUT file being encrypted** (`.env`), not
the output name — a rule for `\.env\.enc$` fails with `no matching
creation rules found`. Decryption needs no rule (recipients are embedded
in the encrypted file).

```makefile
env-encrypt:
	sops --encrypt --input-type dotenv --output-type dotenv .env > .env.enc.tmp && mv .env.enc.tmp .env.enc || { rm -f .env.enc.tmp; exit 1; }
	@echo ".env.enc written — remember: git add .env.enc && git commit"

env-decrypt:
	sops --decrypt --input-type dotenv --output-type dotenv .env.enc > .env.tmp && mv .env.tmp .env || { rm -f .env.tmp; exit 1; }
	@chmod 600 .env
```

(temp + `mv`: a failed sops run must not leave an empty `.env.enc` or
`.env` behind.) `.env` stays gitignored; **`.env.enc` and `.sops.yaml` are
committed**. Workflow: edit `.env` → `make env-encrypt` → commit. Fresh
clone: place the key, `make env-decrypt`. In this mode the agent runs
`env-encrypt` itself after every `.env` change — no TODO item needed.

**The key IS the root secret.** `~/.config/sops/age/keys.txt` must be
backed up OUTSIDE the repo (password manager / private dotfiles) — lose
it and every `.env.enc` is unrecoverable; leak it and every committed
ciphertext in history is readable, forever. Never commit it, never put it
in the repo it decrypts. Multiple machines: copy the key, or add each
machine's public key as an additional comma-separated `age:` recipient
and re-encrypt.

**Mode switches leave debris**: if keypair mode was scaffolded first,
delete `.sops.yaml` when switching to passphrase — dead config misleads
the next agent into the wrong flow.

## Checklists

**New repo that needs a store**

- [ ] Scope rule passed (personal, private).
- [ ] Mode chosen and written down (`CLAUDE.md`): keypair unless the
      owner insists on a passphrase.
- [ ] `secrets/` dir + deny-all gitignore with `!*.enc`.
- [ ] Makefile: encrypt / decrypt / status targets (copy hq's), `make
      help` lines, `.PHONY`.
- [ ] `CLAUDE.md` Secrets section: mode, the targets, the encrypt-after-
      edit rule, the fresh-clone step, the catalog (empty is fine), a
      pointer to this skill.
- [ ] `README.md` says the same in two lines for humans.

**Adding one secret** (every time)

- [ ] Plaintext in the store with a header; `chmod 600`.
- [ ] Catalog bullet in `CLAUDE.md` (names, scope, dates, lifetime,
      consumers, parse rule).
- [ ] `USER_TODO.md` item with the exact `make secrets-encrypt FILE=…`
      and the commit step, why-you, what-is-blocked.
- [ ] Every consumer that must hold the same value named (Coolify env,
      hub config, ansible tag).
- [ ] Later: `.enc` committed, TODO removed, catalog dated.

## When NOT to bother

- Repo never leaves one machine and is never cloned → gitignored `.env`
  is fine as-is.
- Secrets already travel a synced private channel (Syncthing working
  tree) → the encrypted copy is belt-and-suspenders for clones and
  history — still worth it, it is what makes a rebuilt host
  self-sufficient.
- Team/professional context → secret manager, per the scope rule.
