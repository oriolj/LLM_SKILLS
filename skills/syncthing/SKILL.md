---
name: syncthing
description: Diagnose and configure Syncthing, recover sync-conflict files or lost note content, and repair or migrate Git repositories inside synced folders. Use for requests such as "why is this device not syncing?", "recover this note", "fix these sync conflicts", "ignore .git", or "heal this repo on Syncthing". Covers live daemon discovery, per-device ignores and versioning, safe recovery, and verified Git history transfer. Ordinary edits to synced files do not require this skill.
---

# Syncthing operations and recovery

Treat Syncthing as a file synchronizer. It does not merge text, preserve a
transaction across multiple files, or establish which copy reflects the user's
intent. Separate missing synchronization, content conflicts, and application
metadata damage before choosing a remedy.

## Choose the relevant workflow

- **Connectivity, configuration, paths, ignores or versioning:** read
  [operations.md](references/operations.md).
- **Conflict copies or a note that lost content:** read
  [file-recovery.md](references/file-recovery.md).
- **Git under a sync root, missing objects or index/ref conflicts:** read
  [git-repositories.md](references/git-repositories.md).

Do not load every reference for a routine connectivity check. If a repository
has its own runbook and tools, inspect them before replacing their workflow.
The references are self-contained; no other skill is required to recover data.

## Establish the actual state

Identify the host, the running daemon, the real Syncthing folder root/id, the
path relative to that root, sharing devices and their connectivity. Distinguish
what is observed locally from what has been verified on peers. Read the live
folder type, pause state, versioning and effective ignores; a directory called
`Sync` or a plausible `config.xml` is not sufficient evidence.

Stay within the requested scope. A local repair does not authorize logging into
every peer, changing every share, enabling remote GUI access or replacing a
user's existing Git hosting policy. Existing session authorization and host
access rules govern any remote work; routine authorized repairs need no extra
approval ceremony.

## Preserve recoverability during changes

- Before repair, preserve affected originals, conflict copies and useful
  metadata outside the synchronized tree. Keep sensitive recovery copies
  private. Hash or list contents for reporting rather than printing secrets.
- Coordinate active writers. Pause only the affected share when needed and
  record its original pause state. A pause on one device does not stop local
  editors or other devices writing. Do not kill unrelated sessions.
- Copy and inspect before selecting or deleting. If the original file is
  incomplete, making every device agree on it would propagate the loss.
- Resume after validation, restoring the earlier state. If an interrupted
  change makes resuming unsafe, leave the affected share paused and say exactly
  which one and why. Do not silently leave unrelated synchronization disabled.

## Verify the outcome at the right level

Check the behavior that failed: content completeness for a restored note,
application integrity for its metadata, effective per-device rules for an
exclusion, and delivery to the intended reachable peers for a handoff.
Syncthing reporting idle or zero pending items is useful transport evidence,
not proof that a Git repository or a document is complete.

Report what changed, preserved recovery locations, checks performed, and any
unreachable devices still needing migration. Do not call a local ignore change
fleet-wide: `.stignore` and versioning are configured separately on each device.
