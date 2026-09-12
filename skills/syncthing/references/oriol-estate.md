# Oriol's estate: shares, devices, vaults and the hq Git policy

Verified 2026-09-08 and 2026-09-12 on `xps13wc` and `minisforum-um880`.
Re-verify against the live daemon before relying on a number here.

## Shares under `~/Syncthing/`

All `sendreceive`, `fsWatcher=true`, `rescanIntervalS=3600`, Simple
Versioning `keep=5` / `cleanoutDays=30` (a cap, not a promise of every version).

| Share (folder id) | Vaults inside | Devices | Git inside |
|---|---|---|---|
| `Syncthing-mobile-docs` (`aemk7-7vf3s`) | `Obsidian vaults/Personal`, `hq` | 30 | Personal: `.git` still synced. hq: see policy below |
| `Enantena-docs` | `EnantenaObsidian` | 12 | none |
| `BikeCRM-docs` | `Obsidian_bikecrm/BikeCRM` | 12 | `.git` synced |
| `Syncthing-docs` (`qvvzc-ywzzd`) | none | 9 | — |

Thirty devices on the mobile share — phones (`Fold7`, `S21`, `FoldZ5`),
tablets, an e-reader (`Boox`), a dozen laptops — is why its daily notes
conflict and the Enantena vault mostly does not.

Resolve a conflict file's 7-character device suffix:

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse('/home/oriol/.local/state/syncthing/config.xml').getroot()
for d in r.findall('device'):
    print(d.get('id')[:7], '=', d.get('name'))
PY
```

Known offenders: `QKSA3OR`=Fold7 (phone), `UQBVM7N`=xps13wc, `R42IZ47`=Boox,
`HO7OJKA`=fw13pro, `M5CTZCN`=minisforum, `E4CQLHF`=X1yogaG9. IDs that resolve
to nothing (`77GSROW`, `XW7CVUO`) are removed devices; their conflicts date
back to 2018 and are safe to bulk-delete. On Linux both
`~/.config/syncthing/` and `~/.local/state/syncthing/` can exist (minisforum
has both; the live one there answers on `127.0.0.1:8080`) — discover with
`syncthing cli` rather than guessing the file.

## hq Git policy (decided by Oriol 2026-09-12)

**Git for hq lives only on `minisforum-um880`.** Every other device must
`#include hq/.stignore-hq` at the top of the share-root `.stignore`
(`make git-protect` in hq installs it after backing `.git` up outside the
share) and keeps no `.git` of its own. Working files sync everywhere; commits
happen on minisforum — from any other device, `make git-commit MSG="..."`
in hq waits for minisforum to report 100 % completion of the share and then
commits over ssh. This supersedes the 2026-09-09 bundle-handoff workflow;
`make git-bundle` on minisforum remains the backup/recovery artifact.
The hq runbook is `git_on_syncthing.md` in hq.

Per-device state, 2026-09-12: minisforum (git owner, ignore verified),
xps13wc (ignore verified, `.git` removed, recovery copy under
`~/.local/state/hq-git-recovery/`), fw13pro and Mac mini (ignore installed
2026-09-09, still hold an inert local `.git`). Everything else unmigrated —
check the rollout table in the runbook and `USER_TODO.md`.

## Obsidian-specific conflict triage

`assets/sync-conflicts.sh` (`list` / `notes` / `git` / `show <note>` /
`verify <note>`) runs the triage loop read-only, excludes `.stversions`
(which holds archived copies of conflicts) and uses `grep -F -e` so markdown
list items starting with `-` are not parsed as flags.

- Notes (`.md`): N-way union — see [file-recovery.md](file-recovery.md).
- `.obsidian/*.json`, `plugins/*/main.js`: pick the desktop's copy, delete
  the rest. `workspace.json` / `workspace-mobile.json` conflict constantly and
  are worth nothing; every vault `.gitignore` already drops them.
- `*.kdbx`: a KeePass database — never hand-merge or delete; KeePassXC's own
  *Merge database*, or hand to Oriol.
- The Personal vault still tracks four `.obsidian/*.sync-conflict-*.json`
  files despite `*.sync-conflict-*` in `.gitignore` (ignore rules never
  untrack) — `git rm --cached` when that cleanup is requested.

## Why conflicts happen here

`~/.local/bin/syncthing-power-guard.sh` stops Syncthing whenever the CPU
power profile is `power-saver` and restarts it otherwise (a D-Bus watch on
`net.hadess.PowerProfiles`), so a laptop on battery silently does not sync;
check `systemctl --user is-active syncthing; powerprofilesctl get` before
trusting a note is current. Obsidian mobile writes on blur/close, so a note
left open on the phone re-saves hours later on top of whatever synced.
