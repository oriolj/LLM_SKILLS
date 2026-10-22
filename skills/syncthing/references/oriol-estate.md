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
| `panotxa-vault` (id = label, 2026-10-17) | `Obsidian-panotxa` (Panotxa, shared with Anna) | patri (`~/panotxa-vault`, the always-on hub), minisforum (`~/Syncthing/panotxa-vault`), truenas-enantena (`~/panotxa-vault`); offered to Fold7-fork and truenas-personal | none; per-device `.stignore` drops `.obsidian/workspace*.json` |
| `maia-vault` (id = label, 2026-10-19) | `Obsidian-maia` (Laia's own vault, her bot Maia) | maia (`~/maia-vault`, the always-on hub), truenas-enantena (`~/maia-vault`, at 100 % the same day), truenas-personal (listed on maia; its Syncthing app was down, joins when back), Laia's devices later. **Not** on minisforum or Oriol's phone (Oriol's decision) | none |

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

`3YUBEUZ`=Fold7-fork is a second Syncthing install on the same Fold7
(model `SM-F966B`, presumably the Syncthing-Fork app), added on minisforum
2026-10-09 with introducer and auto-accept off and no folders shared yet.

`YSNXGLH`=annas-mba is Anna's MacBook Air (Panotxa collaborator), added on
minisforum (REST) and the mac mini (app-bundle `cli`) on 2026-10-22 at
Oriol's request, introducer and auto-accept off, no folders shared; not yet
connected that day (her side has to add our devices back).

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
When `make git-commit` fails with "has not converged … completion=99.x,
needItems=N" and the local `/rest/db/remoteneed` lists old files unrelated
to the work, it is the stale-delta-index case in
[operations.md](operations.md) § Diagnose — reset the local delta index IDs,
not the files. Until then, the intent of the gate can be met by hand:
`sha256sum` the exact paths on both sides over ssh, and when they match run
the same `git add -A -- <paths> && git commit -F -` on minisforum. The
minisforum GUI listens on `127.0.0.1:8080`, not the default 8384, and its
login shell is fish — pipe bash scripts into `ssh … bash -s`.
The hq runbook is `git_on_syncthing.md` in hq.

minisforum's daemon was down 2026-09-18 22:05 → 09-20 10:54 (stray
SIGTERM, `Restart=on-failure`); since then every Linux host gets
`Restart=always` from `roles/syncthing`. The gap cost uncommitted edits on
minisforum itself — **a session on minisforum commits before it ends**;
the recovery and the debris kinds are in hq `git_on_syncthing.md` §"When
minisforum itself is offline" and in [file-recovery.md](file-recovery.md)
§"Classify the copies before reading them".

**The recordings archive's audio is excluded from the share too** (Oriol,
2026-10-11): `.stignore-hq` ignores every audio extension under
`hq/oriolj/recordings/` (plus plaud-sync's `.audio.*` temp files), so the same
`#include` line that keeps `.git` off a device also keeps those private
recordings off it. Copies synced before stay where they are (ignoring never
deletes). Check a path's effective state with `GET /rest/db/file` (`local.ignored`);
minisforum's GUI/API is `127.0.0.1:8080`, key in `~/.config/syncthing/config.xml`.

**The secrets plaintext is excluded too** (Oriol, 2026-10-21): `.stignore-hq`
syncs only the `*.enc` files under `hq/homelab/secrets/` (`!/hq/homelab/secrets/**.enc`
then `/hq/homelab/secrets/**`); each host decrypts what it needs. A device
without the `#include` still sends and receives the plaintext: pep had none
until that day and held every scope's secrets.

Per-device state, 2026-09-12: minisforum (git owner, ignore verified),
xps13wc (ignore verified, `.git` removed, recovery copy under
`~/.local/state/hq-git-recovery/`), fw13pro and Mac mini (ignore installed
2026-09-09, still hold an inert local `.git`). Everything else unmigrated —
check the rollout table in the runbook and `USER_TODO.md`.

## Retired devices and stray introducers (2026-10-07)

Dead machines kept reappearing in every device list. The cause is
**introducers**: minisforum is the roster's introducer, but our hosts also
trusted phones and old boxes as introducers (Fold7, FoldZ5, S21, Xps1321,
NUC8i7Docker on minisforum). An introducer re-adds every device it knows, and
**the ignored-devices list does not stop that**: `handleIntroductions` in
`lib/model/model.go` never checks it (read 2026-10-07). Ignoring only silences
the "device wants to connect" prompt from the device itself.

So retiring a device means removing it, and keeping it removed:

- The list lives in hq `homelab/ansible/group_vars/all/main.yml`,
  `syncthing_retired_devices` (name, device id, date).
- `roles/syncthing/tasks/retired-devices.yml` runs with `--tags syncthing`.
  It `DELETE`s each device from `/rest/config/devices/<id>`, adds it with
  `syncthing cli config ignored-devices add` (there is no REST sub-endpoint;
  `/rest/config/remoteignoreddevices` answers 404 on v2.1, and the list is
  the `remoteIgnoredDevices` key of `/rest/config`), and warns about every
  introducer other than the roster's one.
- Removing a device on minisforum also de-introduces it from the devices
  minisforum introduced it to (`skipIntroductionRemovals` is false). On
  fw13pro the first seven had already vanished that way before its own run.
- What keeps the loop alive is any remaining stray introducer: Fold7 only,
  once FoldZ5 was retired on 2026-10-07. Un-ticking "Introducer" on it is
  Oriol's decision, and a retired device must be removed by hand on any phone
  or tablet that still lists it.

- `retired-devices.yml` is self-contained (it finds the binary and the API
  itself), and `playbooks/syncthing-retired.yml` runs only that file
  against inventory group `syncthing_hosts`: minisforum, the laptops, the mac
  mini and the claw VMs. The mac's binary is inside the app bundle
  (`/Applications/Syncthing.app/Contents/Resources/syncthing/syncthing`, not
  on PATH; its `cli` finds the app's config by itself). The claws run
  Syncthing as the `syncthing@oriol` system unit, so the full role must not
  touch them.

Applied 2026-10-07: 14 retired devices removed and ignored on minisforum,
fw13pro, the mac mini, pep (was petraclaw), enzo and bruno. minisforum and
fw13pro were also checked against `devices` / `remoteIgnoredDevices`, and a
second run changed nothing on any of the six. Stray introducers found: Fold7
on all of them, and truenas-personal on pep.

Applied again 2026-10-11 (`truenas-personal-old`, the NAS app before a
reinstall): the playbook reached six hosts, seven were offline.

**The two TrueNAS Syncthing apps are not ansible hosts** (no ssh, no CLI
from outside): manage them through REST with their API keys (hq
`homelab/secrets/syncthing-truenas-{enantena,personal}.env`; UI and API on
port **20910**, sync on 20978, the TrueNAS catalog defaults). Retired
devices: `DELETE /rest/config/devices/<id>`, then append to
`remoteIgnoredDevices` and `PUT /rest/config` with the whole config (entries
`{deviceID, name, address: "", time}`); no restart needed.

**A fresh or reinstalled Syncthing has NO ignore on `Syncthing-mobile-docs`**
(the `.stignore` is per device and never syncs), so it pulls whatever
`hq/.git` any unprotected peer announces. Seen 2026-10-11: the phone's
`fold7fork` instance still announces an old `hq/.git`, and both NAS apps had
pulled it within the hour. Check it on every new peer:
`GET /rest/db/ignores?folder=aemk7-7vf3s` (empty = unprotected) and
`GET /rest/db/file?folder=aemk7-7vf3s&file=hq/.git/HEAD` (`availability`
names the devices that hold it). Fix: `POST /rest/db/ignores?folder=…`
`{"ignore": ["#include hq/.stignore-hq"]}` once `hq/.stignore-hq` is present
locally (an include of a missing file stops the folder), and read the
`expanded` list back. The copy already on disk is not removed by the ignore.

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
