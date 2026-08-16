---
name: ansible-gotchas
description: Write and review Ansible tasks that survive a FRESH host — the common gotchas, task ordering/grouping, and idempotency discipline. Load BEFORE writing or editing any Ansible task/role/playbook, and when reviewing one. Use when the user asks to "add a task/role", "fix the playbook", reports a run failing with "Destination directory does not exist", "command not found" mid-play, tasks that "work on my machine but broke on the new host", out-of-order tasks, all-or-nothing package transaction failures, --check breaking on probe commands, duplicate become password prompts, or handlers not firing. Covers the fresh-host mental model (copy/template do NOT create parent dirs — the #1 repeat offender), who-created-that dependency review, block grouping with one gate, probe-then-set idempotency, changed_when/failed_when/check_mode discipline, controller-vs-target lookup() traps, never stopping the active display manager/session service mid-run, and the validation ladder (syntax-check, list-tasks, unit playbooks, --check --diff).
---

# Ansible gotchas: write tasks for the machine that has nothing

Every rule here is a real failure from provisioning a small fleet
(Arch/CachyOS/Fedora/macOS workstations). The unifying cause of almost all of
them: **tasks get written and tested on a machine where the state already
exists, then break on a fresh host or a differently-shaped one.**

## The fresh-host mental model

Before finishing ANY task, re-read it while pretending the target was
installed five minutes ago: empty `$HOME`, no config dirs, no optional
packages, default shell, no prior run's leftovers. For every task ask:

- **Who created the destination's parent directory?** `copy`, `template`,
  `lineinfile` (even with `create: yes`... the FILE, not the dir) do **NOT**
  create parent directories. This is the #1 repeat offender — it has bitten
  twice in one repo: a role deployed scripts into `~/.local/bin` before
  anything created it (broke a fresh laptop's first provision), and a drop-in
  written to `/etc/sddm.conf.d/` which the distro package doesn't ship
  (sddm merely reads it if present — many `/etc/<thing>.d/` dirs are like
  this: optional, read-if-present, shipped by nobody).
  Fix: a `file: state=directory` task immediately before, or one early
  "create common directories" task at the top of the role for the shared
  ones (`~/.local/bin`, `~/.config`, `~/.config/systemd/user`, ...).
- **Who installed the binary this task runs?** A `command:` that calls a
  tool installed by a *later* task, another role, or "it was already on my
  machine" fails only on fresh hosts. Order the install before the use, or
  make the task self-contained (install its own dependency — best for
  tag-scoped runs, see Grouping below).
- **Who guarantees this service/unit exists?** `systemd:` against a unit an
  optional package provides needs a presence probe or `failed_when: false`.

## Ordering and grouping

- **Dependencies flow strictly downward** within a role: dirs → packages →
  files → services. If a task needs something from another role, either move
  it or make it self-contained; roles run in `site.yml` order today but that
  ordering is an accident waiting to be relied on.
- **Group related tasks in a `block:` with ONE `when:` gate.** A block-level
  `when` applies to every inner task, so a task added inside later is gated
  *by construction* — a per-task `when` is something someone must remember.
  Same for `become: yes`: prefer per-task (auditable) but if a whole block is
  privileged, gate the block.
- **Tag-scoped entry points must be self-contained.** If `--tags foo` is a
  documented way to run a feature alone, everything it needs (its own
  package, its own dirs) must be inside the tagged task file — not inherited
  from untagged earlier tasks that won't run. Facts it depends on must be
  computed under `tags: always`.
- **Rollback/cleanup goes in `block:` + `always:`.** Anything you stop,
  mount, stage, or write temporarily (askpass helpers, staged copies, a
  stopped daemon) must be restored/removed in an `always:` so a mid-play
  failure can't strand the machine. Real case: stopping a sync daemon to
  move its folders — the `always:` restarts it even when the move fails.
- **Never stop the active display manager / login session service mid-run.**
  `enabled: no` only; the swap lands next boot. Stopping it kills the session
  running ansible.

## Package installs

- **Batch installs are all-or-nothing transactions** (dnf/pacman): one
  unavailable name fails EVERY package in the batch. Keep risky sources
  (third-party repos, brand-new packages) out of the shared batch — install
  them in their own task with `update_cache: yes` (the run's earlier cache
  refresh predates the repo you just enabled). For lists of nice-to-haves,
  loop one-at-a-time with `ignore_errors: yes` so one absentee doesn't
  poison the rest.
- **Validate names before committing them to a list** (`pacman -Si NAME ||
  pacman -Sg NAME`, `dnf repoquery NAME`). Names differ per distro — keep a
  package_map keyed by a NORMALIZED distro key; `ansible_distribution |
  lower` is not normalized (e.g. `archlinux`, `macosx`) and silently indexes
  to nothing behind a `default([])`.
- **Enable third-party repos by writing the `.repo`/pacman.conf content
  directly** (a literal `copy`), not by shelling out to the distro's
  enable command — CLI behavior differs across versions (dnf4 vs dnf5
  `copr enable` prompting broke silently) while a static file is read
  identically by all.

## Idempotency and check-mode

- **Probe, then set only if different.** For CLI-managed state
  (`xdg-settings`, `xdg-mime`, `git config`, `systemctl set-default`):
  first a query `command` with `changed_when: false`, then the setter gated
  on `stdout != desired`. Blind setters report `changed` forever and hide
  real drift.
- **Read-only probes need `check_mode: false`** (name may vary by ansible
  version; the module option on the task) so `--check` runs still execute
  them — otherwise every task depending on the probe's `register` explodes
  in check mode with an undefined variable.
- **`command:` needs `changed_when`** (usually `false` for probes, or a
  condition on output) and often `failed_when: false` for existence checks.
  In a loop, `failed_when`/`changed_when` are evaluated per item against the
  current item's result — usable as a per-item assert.
- **Registered loop results** land in `.results`; a skipped task's register
  is a skip-stub — dereferencing `item.json.x` in a later `when` fails the
  item instead of skipping it. Put existence-check and dereference in ONE
  lazy expression: `item.json is defined and item.json.x == y`.
- **Hashed/opaque state needs a BEHAVIORAL probe, not a compare.** A stored
  bcrypt password, token hash, or write-only field can't be diffed against
  the desired value. Probe by exercising it: attempt an authenticated
  request/login with the desired credentials — success = skip, failure =
  set. (Real case: Syncthing GUI password — POST the creds to its login
  endpoint, 204 skip / 403 set. Bonus finding: its REST never honors basic
  auth; only the API key — verify which auth channel a probe actually
  tests.) A "compare user only, force-flag for password" fallback is
  strictly worse: it can't detect a drifted password.
- **Detect hardware against SHIPPED databases, not vendor greps.** For
  "does this box have X" facts, match device ids against an authoritative
  list already on disk (e.g. systemd's hwdb files are generated from the
  driver project's supported-device list — fingerprint readers have no USB
  class, but the libfprint hwdb enumerates every supported id). A curated
  vendor-name grep rots; the shipped database updates with the OS.
- **PAM: vendor-stack overrides must be COMPLETE files.** Some pam.d
  services live in /usr/lib/pam.d with /etc/pam.d taking full precedence —
  an /etc file with just your one line REPLACES the vendor stack (locking
  auth or opening it). Copy the vendor content + your line; revert =
  delete the file. For in-place edits (sudo), lineinfile with
  insertbefore + firstmatch, mark lines with a trailing comment for
  idempotent removal, and only ever add 'sufficient' methods so password
  auth survives a broken module.
- **One-shot tasks (run once per machine, ever):** `command:` + `args:
  creates: <artifact the script produces>` makes every later run free. Have
  the script print a machine-readable outcome on stdout ("applied: …" /
  "skipped: …") and key `changed_when` on it; for cosmetic features
  (wallpaper, greeting, MOTD) add `failed_when: false` — a nicety must
  never fail a provision. The script, not ansible, should detect whether
  the machine can use the feature (desktop present, hardware attached) and
  no-op cleanly — that keeps the ansible gate simple and the behavior
  correct when the script runs by hand.

## Controller vs target

- **`lookup('env', 'HOME')` and all `lookup()`s run on the CONTROLLER**, not
  the target. For the target's home use `ansible_env.HOME` (needs
  gather_facts). Same-username fleets hide this until the first mismatch.
- **`synchronize` runs rsync ON the controller** — src paths are
  controller paths; prefer `{{ playbook_dir }}`-relative over hard-coded
  home paths so moving the checkout can't break it.
- **Local runs make inventory groups useless** — when the normal run is
  `ansible-playbook site.yml` on the machine itself, every box is
  `localhost` and group membership can't distinguish them. Gate on DETECTED
  facts (DMI, /sys, /etc/os-release) computed in pre_tasks under
  `tags: always`; keep groups only for remote runs. And parse
  /etc/os-release yourself when derivatives matter: `ansible_distribution`
  short-circuits on marker files and reports the parent distro.
- **Fact caching can go stale/poisoned** — a cached fact from a probe that
  once failed sticks around; prefer re-probing cheap facts every run under
  `tags: always`.

## sudo / become

- **One source of the become password.** A `vars_prompt`-set
  `ansible_become_pass` plus `--ask-become-pass` = two sources = "Sorry, try
  again" on random tasks. Pick one, document which.
- **Child processes' sudo is not Ansible's become.** Build tools that
  invoke their own `sudo` (AUR helpers, installers) get no TTY under
  ansible; feed them a `SUDO_ASKPASS` helper script with the password
  EMBEDDED (written `no_log: true`, mode 0700, deleted in `always:`) — sudo
  sanitizes the environment, so an env-var password arrives empty and burns
  auth attempts into a faillock lockout.

## Validation ladder (run in this order, cheapest first)

1. `ansible-playbook site.yml --syntax-check` — parse errors only.
2. `--list-tasks` / `--list-tags` — did the wiring/tagging land where
   expected?
3. **Unit-test playbooks with no connection** — small localhost plays that
   assert gating/classification/templating logic against fabricated facts.
   If the repo has a policy test (e.g. deny-by-default over includes), run
   it after any structural change.
4. **Probe Jinja separately**: a 10-line scratch playbook exercising just
   the new expression (selectattr chains, dict/zip, loop conditionals) —
   syntax-check does NOT evaluate Jinja.
5. `--check --diff` where the tasks support it.
6. Real run — and remember the recap lies about coverage: `ok=` includes
   skipped-by-condition logic paths; grep the output for the tasks you
   actually changed.

Jinja gotchas for step 4: `| first` on an empty list raises (append a
sentinel: `(list + ['']) | first`); `default()` catches undefined, not
errors; filters bind tighter than `+`.

## Review checklist (before calling a task file done)

- [ ] Every `copy`/`template`/`lineinfile` dest: parent dir guaranteed by
      an earlier task in THIS file or a documented base task.
- [ ] Every `command`/binary: installed by an earlier task or probed.
- [ ] Every optional integration (unit, dir, package): probe +
      `failed_when: false`, or an explicit gate.
- [ ] Blocks gated once; tag-scoped paths self-contained; `always:` restores
      anything stopped or staged.
- [ ] Probes are `changed_when: false` + check-mode-safe; setters fire only
      on difference.
- [ ] Secrets under `no_log: true` and never in env vars for child sudo.
- [ ] Ran the validation ladder; on a fleet, considered the freshest and the
      weirdest machine, not the dev box.
