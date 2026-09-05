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
- **Enable third-party repos by writing the `.repo`/pacman.conf/apt
  `.list` content directly** (a literal `copy`), not by shelling out to
  the distro's enable command — CLI behavior differs across versions
  (dnf4 vs dnf5 `copr enable` prompting broke silently) while a static
  file is read identically by all. This applies to `apt_repository` too:
  **it only ADDS lines** — after a failed run with a wrong codename, the
  corrected task writes its line NEXT to the broken one and apt stays
  broken until someone hand-edits. `copy` owning the whole file
  self-heals. Related: third-party apt repos can lag brand-new distro
  releases (pkg.cloudflare.com had no Debian-trixie dist) — keep the
  codename a variable so one host var pins the previous release.
- **A skip-with-warning role reads as SUCCESS in the recap.** An optional
  feature that skips when its input is missing (no token, no key) ends the
  play green — `ok=13 skipped=5` — and the operator reports "apply done"
  while nothing was installed. When gating a whole role on an input:
  make the skip message name the missing thing AND the file to fix, and
  when someone says a play "ran", verify the ARTIFACT (unit exists, port
  answers), not the recap.

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
- **Detection probes must never need sudo — find a world-readable signal.**
  `/boot` is frequently a root-only ESP mount (vfat fmask → 0700): an
  unprivileged `stat` dies with EACCES, and "just add `become`" is WORSE —
  a wrong/mismatched sudo password fails the task BEFORE the module runs,
  where `failed_when: false` cannot rescue it (become errors precede the
  module; this killed a two-host run twice in one day). Probe an
  unprivileged equivalent instead: the package database (`pacman -Q x`,
  `dpkg -s x`), /sys, os-release, hwdb files. Always `failed_when: false`
  + consumer-side `default()` on top; a detection fact must never be able
  to fail a play.
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
  **But skip the `creates:` guard when the script can legitimately DEFER
  part of its work** (a step that must wait for an app to close, a
  network resource, a first login): an artifact guard freezes the partial
  state forever. Make the script itself the probe-then-set (parse the
  real state, act only on what's missing, ~instant when complete) and run
  it every provision with `changed_when` on its outcome.
- **GUI-app CLIs invoked from ansible usually need a headless flag.** A
  GTK/Qt binary aborts without a display even for pure-CLI subcommands
  (`firefox -CreateProfile` dies with "no DISPLAY" — it needs
  `firefox --headless -CreateProfile`). Test the exact invocation in an
  environment without DISPLAY/WAYLAND_DISPLAY before wiring it.

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
  For pure POLICY (not detectable hardware — e.g. "this box is the
  remote-dev machine"), hostname-key it in group_vars
  (`x_hostnames: [...]` + `is_x: "{{ ansible_hostname in x_hostnames }}"`)
  — works identically for local and remote runs, unlike host_vars.
- **A host with no python cannot run ANY module — bootstrap it with `raw`.**
  Termux (Android), minimal containers and some cloud images ship without
  python; every module, `ping` and `gather_facts` included, dies with
  "module interpreter … not found". The play for such hosts runs with
  `gather_facts: no`, its first task is a `raw:` that installs python
  (idempotent probe: `command -v python || <pkg install python>`), then an
  explicit `setup:`. Seen 2026-09-05 on a fresh Termux reinstall: the role
  had been written against a phone that already had python, so nothing
  noticed until the reinstall.
- **Facts can lie on unusual targets — verify the one you build paths
  from.** On Android/Termux `ansible_user_dir` is `/data` (bionic's passwd
  answer for the app uid) while the real home is `ansible_env.HOME`;
  `ansible_distribution` is `Android`. Pin the interpreter and shell
  (`ansible_python_interpreter`, `ansible_shell_executable`) when nothing
  lives under `/usr`, and set `ansible_become: false` where there is no
  sudo, so a stray `become` fails loudly rather than hanging.
- **Fact caching can go stale/poisoned** — a cached fact from a probe that
  once failed sticks around; prefer re-probing cheap facts every run under
  `tags: always`.

- **Risky updates: automate the NOTICING, never the applying.** Firmware
  flashes, bootloader changes, dist-upgrades — the playbook's job is a
  background metadata refresh + a notification/report ("updates exist,
  run X"), with the destructive step left as an explicit manual command
  that prompts for its own reboot. A desktop with no software-center UI
  needs the notifier built (systemd user timer + notify-send); a DE that
  already notifies (GNOME Software) should have the custom notifier
  SKIPPED, not duplicated. Check how neighbor distros handle the same
  problem before building — their issue trackers are free field reports
  (a capsule-staging bug on one distro's bootloader layout flagged the
  same risk on ours).

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

## Credentials, firewalls, alert plumbing (server fleets)

- **Group-scoped credentials must be managed BOTH ways.** An
  `authorized_key`/token task gated `when: "'somegroup' in group_names"`
  only ever ADDS: removing the host from the group silently leaves the
  credential behind. Drop the `when` and flip
  `state: "{{ 'present' if 'somegroup' in group_names else 'absent' }}"`
  so leaving the group revokes on the next run.
- **A tag-scoped task that restarts/reloads a listener must open its own
  firewall holes first.** Real case: `--tags ssh` reloaded sshd onto a new
  port while the ufw allow for it lived in the (unrun) `firewall` tag —
  the connected session survives but nothing new can get in. Probe
  `ufw status` (failed_when: false — ufw may not be installed yet) and
  allow the ports before the reload; duplicate allows are no-ops.
- **Daemon-vs-config convergence checks must compare BOTH directions.**
  "Reload if a wanted port is missing" passes while a stale extra
  listener (old port 22) stays bound forever. Use
  `symmetric_difference`, and assert the same both ways.
- **`logger` ignores stdin when given a message argument.**
  `body | logger -t x "subject"` journals only the subject — the piped
  diagnostic body is silently dropped. Pipe everything:
  `printf '%s\n%s\n' "$subject" "$body" | logger -t x`.
- **One-shot bootstrap playbooks: reload services unconditionally.** A
  `when: <file task> is changed` reload-gate wedges after an interrupted
  run (file written, reload never happened → every later run skips it).
  For a play that runs once per box, always reload and put the cosmetics
  in `changed_when`.
- **Unsigned release packages get a sha256 recorded at pin time.** GitHub
  release SHA256SUMS often covers only some artifacts (Loki: zips yes,
  deb/rpm no) — download once, hash, and store the checksums NEXT TO the
  version pin so a bump forces re-hashing; install via
  `get_url checksum:` + local-file apt/dnf, gated on a version probe.
- **Repeated blob-parsing Jinja belongs in a filter plugin.** The
  regex_search+`default([],true)`+sentinel+`first|trim` incantation for
  reading KEY=value out of a secrets file, copied per role, is a 15-line
  `filter_plugins/env_get.py` (split on first '=' — values can contain
  '=' and '|'; never `source` or `cut`). Wire the dir in ansible.cfg
  (cfg-relative) so plays under playbooks/ resolve it too.

## Validation ladder (run in this order, cheapest first)

- **From an agent shell, ansible refuses to start**: `ERROR: Ansible
  requires blocking IO on stdin/stdout/stderr. Non-blocking file handles
  detected: <stderr>` (Claude Code's Bash tool hands the process
  non-blocking pipes; seen 2026-09-04 running the shared/ansible
  observability play). Give it blocking handles instead of "fixing"
  ansible: `ansible-playbook … </dev/null 2>&1 | cat` (the `make` targets
  work the same way: `make dry TAGS=x HOST=y </dev/null 2>&1 | cat`).
  Output is unchanged, exit code rides `$PIPESTATUS[0]` if you need it.

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
      Protect the secret **at the point it first enters Ansible state** —
      the `set_fact`/`slurp`/`register` that reads it — not only the
      final `template`/`copy`: callbacks, `-v` output and event/log
      collectors serialize every task result, and a `no_log` on the last
      task does nothing retroactively (shipped twice in hq's NaN tasks,
      caught in review 2026-08-31).
- [ ] Ran the validation ladder; on a fleet, considered the freshest and the
      weirdest machine, not the dev box.
