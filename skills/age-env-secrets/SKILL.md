---
name: age-env-secrets
description: Commit an encrypted .env to a PRIVATE PERSONAL repo using age passphrase encryption, so personal projects carry their own secrets across machines without a secret manager. Use when the user asks "can we commit the .env encrypted", "version the secrets", "how do I share .env between my machines via git", or when setting up a personal/hobby repo that needs API tokens/device passwords available after a fresh clone. Covers age -p passphrase mode (Oriol's preference — no keypair to manage or lose), Makefile env-encrypt/env-decrypt targets, why sops CANNOT do passphrases (keypair-only, its per-value diffs are the trade-off), the sops path_regex-matches-the-INPUT-file trap if keypairs are ever used, and the CLAUDE.md documentation rule so future agents don't ask for secrets that are already committed. HARD SCOPE LIMIT: personal private repos ONLY — never professional repos, public OR private; those get a real secret manager.
---

# Committed encrypted .env (age passphrase) — personal repos only

Field-tested 2026-08-08 on the busy-bar repo (private personal repo needing a
device password + Home Assistant + Toggl tokens available across machines).

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

## Passphrase mode, not keypairs (owner preference)

Oriol prefers **a passphrase in his head over a keyfile on disk**: nothing
to back up, nothing that a stolen laptop leaks, works on any machine that
has `age` installed. The cost: the whole file is one encrypted blob (no
per-variable diffs) and encrypt/decrypt are interactive.

Consequences for agents:

- **Agents can NEITHER encrypt NOR decrypt the file** — the passphrase is
  the owner's. When `.env` changes, tell the owner to run
  `make env-encrypt` and commit; never try to script the passphrase in.
- `age -p` prompts on a TTY; it will not work from a non-interactive shell.

## Setup

`age` from the system package manager (`pacman -S age`). Two Makefile
targets:

```makefile
env-encrypt:
	age --encrypt --passphrase --output .env.age .env
	@echo ".env.age written — remember: git add .env.age && git commit"

env-decrypt:
	age --decrypt --output .env .env.age
	@chmod 600 .env
```

- `.env` stays in `.gitignore`; **`.env.age` is committed**.
- Workflow: edit `.env` → `make env-encrypt` (passphrase prompt, twice) →
  commit `.env.age`. Fresh clone: `make env-decrypt` (passphrase prompt).
- age passphrase mode uses scrypt — resistant to brute force for a decent
  passphrase; the passphrase strength IS the security of every committed
  ciphertext, forever (git history).

## Document it in the repo's CLAUDE.md

State: `.env.age` is the committed encrypted copy, the passphrase is the
owner's (agents must ask the owner to run the targets), and the
encrypt-after-edit rule. Without this, future sessions "fix" the missing
`.env` by asking for secrets that are already in the repo.

## Alternative: sops + age keypairs (when per-value diffs matter)

**sops does not support passphrases at all** — it needs recipients (age
public keys, KMS, GPG). If the owner ever wants git diffs that show *which*
variable changed (`FOO=ENC[AES256_GCM,...]` per line) rather than an opaque
blob, that's the trade for switching to keypairs:

- `age-keygen -o ~/.config/sops/age/keys.txt` (sops auto-discovers this
  path); the private key becomes the root secret and MUST be backed up
  outside the repo — lose it, lose everything; leak it, all history leaks.
- `.sops.yaml` committed at the repo root:

  ```yaml
  creation_rules:
    - path_regex: \.env$
      age: age1<recipient>
  ```

  ⚠️ **Trap: `path_regex` matches the INPUT file being encrypted**
  (`.env`), not the output name — a rule for `\.env\.enc$` fails with
  `no matching creation rules found`. Decryption needs no rule (recipients
  are embedded in the file).
- Encrypt/decrypt with `--input-type dotenv --output-type dotenv`.

## When NOT to bother

- Repo never leaves one machine and is never cloned → gitignored `.env` is
  fine as-is.
- Secrets already travel a synced private channel (e.g. the working tree
  syncs via Syncthing) → the encrypted copy is belt-and-suspenders for the
  git remote (still worth it: the GitHub clone alone becomes
  self-sufficient).
- Team/professional context → secret manager, per the scope rule.
