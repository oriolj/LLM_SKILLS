---
name: age-env-secrets
description: Commit an encrypted .env to a PRIVATE PERSONAL repo using age passphrase encryption, so personal projects carry their own secrets across machines without a secret manager. Use when the user asks "can we commit the .env encrypted", "version the secrets", "how do I share .env between my machines via git", or when setting up a personal/hobby repo that needs API tokens/device passwords available after a fresh clone. Covers the two modes and how to choose: sops+age keypair (per-value encryption, readable diffs, agents can encrypt/decrypt autonomously — what busy-bar settled on) vs age -p passphrase (nothing on disk to back up, but interactive-only: agents can neither encrypt nor decrypt, so the committed copy goes stale unless the owner remembers — Oriol's repeated explicit choice, honor it). Also: Makefile encrypt/decrypt targets (single .env and multi-file secrets/ dir variants), the sops path_regex-matches-the-INPUT-file trap, the age-private-key-is-the-root-secret backup rule, the passphrase-mode automation pattern (ansible/scripts deploy from the controller's gitignored decrypted plaintext — they can never prompt), the no-TTY rule (agents can't run age -p at all; owner runs the make target in a terminal, passphrase never goes in chat), and the CLAUDE.md documentation rule so future agents don't ask for secrets that are already committed. HARD SCOPE LIMIT: personal private repos ONLY — never professional repos, public OR private; those get a real secret manager.
---

# Committed encrypted .env (age passphrase) — personal repos only

Field-tested 2026-08-08 on the busy-bar repo (private personal repo needing a
device password + Home Assistant + Toggl tokens available across machines)
and on hq (homelab monorepo; Resend API key deployed to every machine by
ansible, passphrase mode by explicit owner choice).

## Scope rule — read this first

Committing encrypted secrets is acceptable **only for private personal
repos** (hobby projects, homelab, single-owner tooling). It is NOT for:

- **Professional public repos** — obviously.
- **Professional private repos** — also no. Access to the repo outlives
  employment/contract changes (forks, clones on old laptops, CI caches), the
  passphrase inevitably spreads through insecure side channels, rotation
  requires a git commit, and git history preserves every
  previously-committed ciphertext forever (whoever later obtains the
  passphrase decrypts ALL historical secrets, including rotated-away ones).
  Professional projects use a secret manager (Vault, cloud KMS/SM, Coolify's
  env store, CI secrets) — the repo carries only references.

If the user asks for this on a work project, say the above and offer the
secret-manager path instead.

## Choosing the mode

Two workable modes; the deciding question is **who needs to run the
encryption**:

- **sops + age keypair** (what busy-bar settled on, 2026-08-08): per-value
  encryption (`FOO=ENC[AES256_GCM,...]` per line — diffs show WHICH var
  changed), and non-interactive, so agents/scripts keep `.env.enc` fresh
  autonomously after every `.env` edit. Cost: the private key is a file
  that must be backed up.
- **age -p passphrase**: nothing on disk to back up, passphrase in the
  owner's head. Cost: whole-file blob (no per-var diffs) AND
  interactive-only — **agents can neither encrypt nor decrypt**, so the
  committed copy silently goes stale unless the owner remembers to run
  `make env-encrypt` after each change. (This bit busy-bar: the passphrase
  variant was set up and the encrypted file was simply never produced.)

**sops does not support passphrases at all** (recipients only: age keys,
KMS, GPG) — passphrase mode means plain `age -p` and losing sops's
per-value format. Default to sops+age keypair unless the owner explicitly
insists on a passphrase and accepts the staleness risk. Oriol has now
insisted on passphrase mode twice (busy-bar initially, hq 2026-08-08 even
after the keypair default was presented and scaffolded) — when he asks,
state the staleness trade-off once, then build passphrase mode without
re-litigating.

## Passphrase mode in practice (field-tested on hq)

- **Agents cannot run `age -p` OR `age -d` at all** — both prompt on the
  TTY and agent shells have none, so they fail outright, not just
  awkwardly. Ask the owner to run the make target in a real terminal
  (in Claude Code: `! make secrets-encrypt`). **Never ask for the
  passphrase in chat**, and never try to pipe it in.
- **Repo-wide secrets dir variant**: for a monorepo, keep secrets in one
  place (e.g. `homelab/secrets/*.env`, gitignored via `secrets/*.env`)
  and loop in the Makefile — targets named `secrets-encrypt` /
  `secrets-decrypt`:

  ```makefile
  secrets-encrypt:
  	@for f in homelab/secrets/*.env; do \
  		[ -f "$$f" ] || continue; \
  		age -p -a -o "$$f.enc" "$$f"; \
  	done

  secrets-decrypt:
  	@for f in homelab/secrets/*.env.enc; do \
  		[ -f "$$f" ] || continue; \
  		out="$${f%.enc}"; age -d -o "$$out" "$$f"; chmod 600 "$$out"; \
  	done
  ```

  (`-a` = ASCII armor, so the committed .enc is text.)
- **Automation that must deploy the secret elsewhere** (ansible pushing a
  config to remote machines, cron scripts, etc.) can never decrypt
  mid-run. The working pattern: automation reads the **controller's
  gitignored decrypted plaintext** (produced once by a manual
  `make secrets-decrypt`) and pushes that to targets — targets never see
  the passphrase or the ciphertext. Guard with a stat + a warn-and-skip
  task so runs on a not-yet-decrypted controller degrade gracefully
  instead of failing.
- **Mode switches leave debris**: if keypair mode was scaffolded first,
  delete `.sops.yaml` when switching to passphrase — dead config misleads
  the next agent into the wrong flow.

## Setup (sops + age keypair)

Install from the system package manager (`pacman -S sops age`; both are
also single static binaries droppable into `~/.local/bin` when root isn't
available).

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

⚠️ **Trap: `path_regex` matches the INPUT file being encrypted** (`.env`),
not the output name — a rule for `\.env\.enc$` fails with
`no matching creation rules found`. Decryption needs no rule (recipients
are embedded in the encrypted file).

Makefile targets:

```makefile
env-encrypt:
	sops --encrypt --input-type dotenv --output-type dotenv .env > .env.enc
	@echo ".env.enc written — remember: git add .env.enc && git commit"

env-decrypt:
	sops --decrypt --input-type dotenv --output-type dotenv .env.enc > .env
	@chmod 600 .env
```

- `.env` stays in `.gitignore`; **`.env.enc` and `.sops.yaml` are
  committed**. Workflow: edit `.env` → `make env-encrypt` → commit.
  Fresh clone: place the key, `make env-decrypt`.

## The key IS the root secret

`~/.config/sops/age/keys.txt` must be backed up OUTSIDE the repo (password
manager / private dotfiles) — lose it and every `.env.enc` is
unrecoverable; leak it and every committed ciphertext in git history is
readable, forever. Never commit it, never put it in the repo it decrypts.
Multiple machines: copy the key, or add each machine's public key as an
additional comma-separated `age:` recipient and re-encrypt.

## Document it in the repo's CLAUDE.md

State: `.env.enc` is the committed encrypted copy, where the key lives,
the encrypt-after-edit rule, and the fresh-checkout decrypt step. Without
this, future sessions "fix" the missing `.env` by asking for secrets that
are already in the repo.

## When NOT to bother

- Repo never leaves one machine and is never cloned → gitignored `.env` is
  fine as-is.
- Secrets already travel a synced private channel (e.g. the working tree
  syncs via Syncthing) → the encrypted copy is belt-and-suspenders for the
  git remote (still worth it: the GitHub clone alone becomes
  self-sufficient).
- Team/professional context → secret manager, per the scope rule.
