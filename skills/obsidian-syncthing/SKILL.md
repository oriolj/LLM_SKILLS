---
name: obsidian-syncthing
description: Resolve Syncthing sync-conflict files and keep multi-device Obsidian vaults healthy. Use when the user says "merge/resolve the syncthing conflicts", "sync-conflict", "conflicted note", "I lost a note", "the vault didn't sync", "which version is right", mentions .stversions, .stignore, a note that reverted or lost lines, duplicate notes with a device suffix, or a git repo that lives inside a Syncthing share (conflicted .git/index or refs/heads). Covers the N-way union merge for NOTES (never pick-one, dedupe by hash, include git HEAD as a variant, verify line-by-line), pick-one-and-delete for CONFIG, the .stversions recovery net (simple/keep=5/30 days), the synced-.git hazard, the gitignore-doesn't-untrack trap, and why this estate generates conflicts (30-device fan-out, power-saver auto-stop, Obsidian mobile write-on-blur).
---

# Obsidian vaults on Syncthing

Field-tested 2026-09-08 merging six conflict copies of one daily note in the
Personal vault. Everything below is verified against this machine's real
Syncthing config and conflict history, not the upstream docs.

Companion skill: **obsidian-vault** owns vault structure, `.obsidian`
preferences and Bases tables. This one owns *sync* — conflicts, recovery,
and multi-device hygiene.

## The estate (verified 2026-09-08)

Four Syncthing shares under `~/Syncthing/`, all `sendreceive`,
`fsWatcher=true`, `rescanIntervalS=3600`, versioning `simple` (`keep=5`,
`cleanoutDays=30`):

| Share | Vaults inside | Devices | Git repo inside? |
|---|---|---|---|
| `Syncthing-mobile-docs` (id `aemk7-7vf3s`) | `Obsidian vaults/Personal`, `hq` | **30** | yes, both |
| `Enantena-docs` | `EnantenaObsidian` | 12 | no |
| `BikeCRM-docs` | `Obsidian_bikecrm/BikeCRM` | 12 | yes |
| `Syncthing-docs` | (no vault) | 9 | — |

**`Syncthing-mobile-docs` is shared with 30 devices** — phones (`Fold7`,
`S21`, `FoldZ5`), tablets (`TabS4`, `Tabs8plus`), an e-reader (`Boox`), and
a dozen laptops. That fan-out is why the daily note conflicts and the
Enantena vault mostly does not. Treat any note in that share as
multi-writer by default.

Resolve a short device ID with:

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse('/home/oriol/.local/state/syncthing/config.xml').getroot()
for d in r.findall('device'):
    print(d.get('id')[:7], '=', d.get('name'))
PY
```

Known offenders in the history: `QKSA3OR`=Fold7 (phone), `UQBVM7N`=xps13wc,
`R42IZ47`=Boox, `HO7OJKA`=fw13pro, `M5CTZCN`=minisforum, `E4CQLHF`=X1yogaG9.
IDs that resolve to nothing (`77GSROW`, `XW7CVUO`) are **removed devices** —
their conflicts are ancient (some from 2018) and safe to bulk-delete.

## Anatomy of a conflict file

```
<base>.sync-conflict-<YYYYMMDD>-<HHMMSS>-<DEVICEID7>.<ext>
2026-09-07.sync-conflict-20260908-114210-UQBVM7N.md
```

- The **timestamp is when the conflict was detected on this device**, not
  when the content was written. It tells you nothing about which version is
  newer in content terms.
- The **device ID is the device that last modified the losing copy**. The
  winner keeps the plain filename.
- **The plain-named file is NOT necessarily the most complete one.** Verified
  today: `2026-09-07.md` had 41 lines while its `UQBVM7N` conflicts had 42,
  including two lines (`Alta client bcrm`, `Streamer Rubí`) that existed
  nowhere else. Never resolve by "keep the real filename".
- **Conflict copies duplicate.** Six files held three distinct contents —
  `215048`/`215050` were byte-identical, as were `114210`/`114212`. Always
  dedupe by hash before reading anything.

## Merging NOTES: the N-way union merge

The rule: **a note conflict is a union, never a choice.** These are captured
thoughts, not code — losing a line is the only real failure mode, and
duplicating one costs nothing.

### 0. Freeze the file first

Close the note in Obsidian on every device you can reach, and do not open
the vault while merging — Obsidian re-saves on blur and will manufacture a
fresh conflict on top of your merge. If the merge will take a while, stop
the local daemon (`systemctl --user stop syncthing`) and start it after you
commit.

### 1. Inventory and dedupe by hash

```bash
cd "<vault>"
ls -la <base>*.md
md5sum <base>*.md          # collapse 6 files into the 2-3 real variants
```

### 2. If the vault is a git repo, HEAD is a variant too

This is the step that is easy to skip and expensive to skip. The committed
version can hold lines that **every** current file has lost, because an
overwrite on one device silently dropped them:

```bash
git show HEAD:<base>.md | diff - <one-of-the-conflicts>
```

Today the 11-line committed version was the only place that still had
`llegir sobre tailscale serve per https internal` and the TestFlight line —
a phone edit had overwritten them the evening before. Nobody would have
noticed.

### 3. Diff every pair, then write the union

```bash
diff <base>.md <base>.sync-conflict-<...>.md
```

Write the merged file by hand with a heredoc. Put recovered lines back **in
their original position** (use the older variant's ordering as the guide),
not appended at the end — the note has to still read like the user's note.

### 4. Verify nothing was lost, mechanically

Never eyeball this. Assert that every non-empty line of every variant, and
of `HEAD`, survives into the merge:

```bash
check() {
  while IFS= read -r l; do
    t=$(echo "$l" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$t" ] && continue
    grep -qF -e "$t" "$MERGED" || echo "MISSING from $1: $t"
  done
}
for f in <base>.sync-conflict-*.md; do check "$f" < "$f"; done
git show HEAD:<base>.md | check HEAD
```

**`grep -qF -e "$t"` — the `-e` is mandatory.** Markdown list items start
with `-`, which grep parses as an option; without `-e` you get a screen of
bogus `MISSING: - blue green` lines and `ugrep: invalid option` noise, and
you will waste a round trip deciding whether the merge was broken. It
wasn't.

Also normalise leading whitespace before comparing: variants routinely
differ only by a leading space on the first line (` 6a98550126d20` vs
`6a98550126d20`), which is not a real difference.

### 5. Delete the conflict copies and commit

```bash
rm -f <base>.sync-conflict-*.md
git add <base>.md && git commit
```

Write the commit message so the *recovery* is legible — which variants
existed, and specifically which lines came back from the dead. That message
is the only record that a silent data loss happened.

## Merging CONFIG and binaries: pick one, delete the rest

A union merge on JSON produces invalid JSON. For anything that is not a
note:

- **`.obsidian/*.json`** (`app`, `appearance`, `core-plugins`,
  `community-plugins`, `graph`, `workspace`) — keep the version from the
  machine you actually configure on (the desktop), delete the others. No
  inspection needed. These are per-machine preference blobs.
- **`.obsidian/plugins/*/main.js`** — plugin code. Delete the conflicts;
  Obsidian re-downloads on update. Three conflicting copies of Templater's
  `main.js` in the Personal vault came from desktop and Boox pulling
  different builds.
- **`*.kdbx`** (26 in this estate) — a KeePass database. **Never touch these
  by hand and never delete one.** Open both in KeePassXC and use its own
  *Merge database* — it merges entry-level history. Hand it to the user if
  unsure.
- **`workspace.json` / `workspace-mobile.json`** — rewritten on every pane
  change on every device, so they conflict constantly and are worth nothing.
  Gitignore them (all three vaults with a `.gitignore` already do) and
  delete their conflicts on sight.

## The `.stversions` recovery net

Versioning is `simple` with `keep=5`, `cleanoutDays=30` on all four shares,
so every overwritten or deleted file leaves up to 5 timestamped copies:

```
~/Syncthing/<share>/.stversions/<original path>/<name>~YYYYMMDD-HHMMSS.<ext>
```

This is where a note goes when a device overwrites it with an older body and
**no conflict file is created at all** (the silent case — the one the merge
above recovered from `HEAD` only because the vault happened to be a git
repo). For a vault with no git, `.stversions` is the only net.

```bash
find "~/Syncthing/<share>/.stversions" -path "*<note name>*" -printf '%TY-%Tm-%Td %p\n' | sort
```

**Thirty days, then it is gone.** If the user reports a lost note, look here
first and copy the recovered body out immediately, before doing anything
else.

**Exclude `.stversions` from every conflict search.** It contains its own
archived copies of conflict files; a naive `find` will have you "resolving"
files that are already history:

```bash
find ~/Syncthing/<share> -name "*sync-conflict*" -not -path "*/.stversions/*"
```

Same for `Personal.old` and `Obsidian vaults/AwesomeVaults/*` in the mobile
share — template vaults, not live ones.

## A git repo inside a Syncthing share is the top hazard

Three of the four vaults are git repos living inside a synced folder, so
**`.git` itself is replicated to 30 devices**. Git assumes exclusive
ownership of that directory. Object files are content-addressed and merge
harmlessly; **refs, the index and the logs do not**.

Verified damage, 2026-08-29 on `hq` (device fw13pro):

```
.git/index.sync-conflict-...
.git/refs/heads/master.sync-conflict-...
.git/logs/HEAD.sync-conflict-...
.git/COMMIT_EDITMSG.sync-conflict-...
```

and `.stversions` shows the Personal vault's `refs/heads/master` being
versioned three separate times over 2026-09-07/08 — two machines advancing
the same branch.

Rules:

1. **Commit from one machine at a time.** Before committing in a synced
   repo, confirm the folder is *Up to Date* in the Syncthing UI.
2. **Audit for `.git` conflicts before trusting any repo state:**
   ```bash
   find ~/Syncthing -path "*/.git/*" -name "*sync-conflict*" -not -path "*/.stversions/*"
   ```
3. **A conflicted `refs/heads/master` means divergent history.** Read both
   files (each is a 40-char SHA), `git log --oneline` each commit, and
   merge or cherry-pick. Never `git reset --hard` to make the warning go
   away — that is the one move that turns a recoverable divergence into
   real loss.
4. **A conflicted `.git/index` is safe to repair**: `rm -f .git/index &&
   git reset` rebuilds it from HEAD. You lose only staged-but-uncommitted
   staging, never committed work. Delete the `index.sync-conflict-*` copy
   afterwards.
5. `.git/COMMIT_EDITMSG` and `.git/logs/*` conflicts are cosmetic — delete
   them.

The clean structural fix is a `.stignore` entry for `.git`, at the cost of
losing off-site replication of the history. **No share currently has a
`.stignore` at all.** Do not add one without asking — it changes what is
backed up.

## The gitignore trap (verified 2026-09-08)

The Personal vault's `.gitignore` ends with `*.sync-conflict-*`, and
`git check-ignore` confirms the rule matches. Four conflict files are
**still tracked** anyway:

```
.obsidian/app.sync-conflict-20251225-091346-QKSA3OR.json
.obsidian/app.sync-conflict-20251225-150301-QKSA3OR.json
.obsidian/core-plugins.sync-conflict-20251225-091346-QKSA3OR.json
.obsidian/core-plugins.sync-conflict-20251225-150301-QKSA3OR.json
```

**`.gitignore` never untracks a file that was already committed.** Adding
the rule after the fact does nothing. Fix with:

```bash
git rm --cached '*.sync-conflict-*' && git commit
```

Every vault repo should carry `*.sync-conflict-*` in `.gitignore` — and a
`git ls-files | grep sync-conflict` check to prove the rule is actually in
force.

## Why this estate generates conflicts (and how to stop it)

1. **30 devices on the mobile share**, most of them battery-powered and
   asleep. A phone that syncs twice a day is a two-day-old writer.
2. **`~/.local/bin/syncthing-power-guard.sh` stops Syncthing whenever the
   CPU power profile is `power-saver`** and starts it when it is not — a
   D-Bus watcher on `net.hadess.PowerProfiles`. So **a laptop on battery is
   silently not syncing at all.** Every edit made in that window is a future
   conflict. Check before trusting the vault:
   ```bash
   systemctl --user is-active syncthing; powerprofilesctl get
   ```
   This single mechanism explains most desktop-vs-phone conflicts on the
   daily note.
3. **Obsidian mobile writes on blur/close**, not on keystroke. A note left
   open on the phone re-saves hours later, on top of whatever synced in
   between. Close the daily note on the phone before editing it on the
   desktop.
4. `rescanIntervalS=3600` with `fsWatcher=true` — the watcher covers live
   edits, but a device that was asleep only reconciles on wake.

Prevention, in order of payoff: close the note on other devices; confirm
Syncthing is running and *Up to Date* before a long editing session; and
resolve conflicts the same day, while you still remember which device you
typed on.

## Audit commands

**Ready-made: [`assets/sync-conflicts.sh`](assets/sync-conflicts.sh)** — the
whole triage loop, read-only:

```bash
sync-conflicts.sh list              # per share, per originating device, + device map
sync-conflicts.sh notes             # only .md conflicts (the ones needing a real merge)
sync-conflicts.sh git               # conflicts inside .git, with the repair for each
sync-conflicts.sh show  <base.md>   # dedupe variants by hash, diff each against HEAD
sync-conflicts.sh verify <base.md>  # assert no line of any variant was lost
```

`show` then `verify` is the merge loop from the section above, with the
`grep -e` and `.stversions` traps already handled.

Or by hand. Scope every search to a share. **Never `find /`** — it descends into GVFS
and network mounts (see global CLAUDE.md).

```bash
# conflicts per share
for s in ~/Syncthing/*/; do
  echo "$(find "$s" -name '*sync-conflict*' -not -path '*/.stversions/*' | wc -l)  $s"
done

# which devices are producing them
find ~/Syncthing -name "*sync-conflict*" -not -path "*/.stversions/*" \
  | grep -oP 'sync-conflict-\d{8}-\d{6}-\K[A-Z0-9]{7}' | sort | uniq -c | sort -rn

# notes only (the ones that need a real merge)
find ~/Syncthing -name "*sync-conflict*.md" -not -path "*/.stversions/*"
```

Triage order: `.md` inside a vault first (real content, union merge),
`.kdbx` second (hand to the user), everything else is delete-on-sight.
