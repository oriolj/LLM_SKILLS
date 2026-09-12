# Git repositories inside Syncthing folders

## Choose a supported history transport

Keep live Git metadata local. Git's related files cannot be safely merged by a
continuous file synchronizer. This includes live bare repositories: removing
the working tree does not make object/ref updates transactional.

Choose the workflow that fits the user's constraints:

- Independent repositories with ordinary Git fetch/push are the usual choice
  when allowed. Do not replace an existing working remote policy with bundles.
- Synced documents with Git on one designated machine are simpler when only
  that machine needs to record history.
- Local metadata and completed Git bundles support offline/no-server history
  transfer. They require explicit review and integration on recipients.

One active human, frequent commits, avoiding rebases, ignoring only lockfiles,
or pausing periodically reduces some opportunities for failure; none makes
live `.git` sync reliable. `git --no-optional-locks status` avoids an optional
index write during inspection, but is not a distributed lock. A stale index can
travel even when the user thinks they are only reading files.

Sources: [Git FAQ](https://git-scm.com/docs/gitfaq#_transfers),
[Git status](https://git-scm.com/docs/git-status#_BACKGROUND_REFRESH),
[Syncthing maintainer explanation](https://forum.syncthing.net/t/resolving-sync-conflicts-in-git-folder/11969),
[2024 user experience](https://forum.syncthing.net/t/syncthing-as-a-server-for-multiple-devices/23346).

## Recover the existing repository before migration destroys evidence

1. Coordinate local Git writers and pause the affected share when necessary.
   Preserve `.git` including reflogs, indexes, conflict copies and unreachable
   objects, plus working files and untracked data, outside the sync root. Save
   staged/unstaged binary patches if Git can produce them. A copy of damaged
   metadata is evidence, not a verified usable backup.
2. Record HEAD and refs. Run `git fsck --full --no-progress`, inspect its exit
   code and diagnostics, and distinguish missing objects from harmless dangling
   objects. `rev-parse HEAD` can print a hash for an absent object; even walking
   commit ancestry does not verify every tree and blob.
3. Obtain missing objects from a healthy authorized peer, retained copies or a
   verified full bundle. Validate each object using Git's own hash calculation
   (`git hash-object -t <type> --stdin`, in the target repository's object format)
   before inserting those exact bytes with `-w`. Transfer binary bytes without
   shell interpolation or text decoding. Never invent an approximate tree,
   overwrite a known object with different bytes, or reset HEAD backward to
   conceal a missing object.
4. Repeat fsck after recovered parent objects reveal further missing children.
   Address index cache-tree errors too; do not clear the index to hide them.
   Prefer exact-object recovery. If rebuilding an index becomes necessary,
   preserve its original contents and stage semantics first, use a separate
   index, and verify the resulting staged entries before replacement.
5. Preserve every divergent ref under a named recovery ref before moving
   conflict artifacts out of `.git`. Compare reachability against the actual
   destination branch. Duplicate filenames may name the same commit, while a
   single conflict ref may retain unique history. Inspect each conflict index
   separately using `GIT_INDEX_FILE=<preserved-copy>` with
   `git --no-optional-locks ls-files --stage` in the correct repository. Compare
   paths, modes, stages and object ids against the live index and history;
   unique staged blobs may never have belonged to a commit. Check that those
   objects exist too; recover or explicitly report unavailable staged content.
   Keep raw index/reflog copies even when branch tips appear redundant.
   Do not auto-merge historical estate
   facts just because their commits are absent from master.
6. Require successful full fsck and a verified recoverable history artifact.
   Preserve unresolved evidence. Do not GC/prune during recovery; temporarily
   disabling `gc.auto`/`maintenance.auto` does not stop separately scheduled jobs.

If a needed object cannot be found, preserve the current history and say which
hash is unavailable. Do not call the repository healed after making only
`git status` succeed.

The 2026-09-09 hq repair illustrates recursive recovery: one missing root tree
revealed another missing tree and two missing blobs. Restoring the four exact
objects preserved HEAD. Two duplicate conflict refs retained nine commits not
reachable from master; they were preserved under a recovery ref, not discarded.
Reachable peers needed additional index-tree objects despite having readable
HEAD commits. Each host required its own fsck.

## Protect metadata on each device

Read [operations.md](operations.md) for ignore placement and precedence. Back up
metadata and install the exclusion on each relevant device before resuming it.
For a Git worktree or `--separate-git-dir` layout, inspect the `.git` pointer,
common directory and linked worktrees: excluding only the pointer file may
leave the actual Git directory inside another synced path.

Do not delete an old `.git` as a bootstrap step or assume a new local `git init`
recovers existing history. Receiving devices can hold unique commits/staging.
After exclusion, working files may be current while HEAD and index are older;
that is an expected workflow issue, not a reason to enable metadata sync again.

## Verified bundle handoff

Publish only completed artifacts. Build under a Syncthing-excluded temporary
path, verify, then atomically rename to a unique final name. Distinct source
hosts must not concurrently overwrite the same bundle filename.

- A `--all` full bundle carries refs and their reachable objects. It does not
  preserve the working tree, index, hooks, configuration, complete reflogs or
  all unreachable recovery evidence. Preserve those separately when needed.
- `git bundle verify` checks format/prerequisites, but is not an exhaustive
  packed-object integrity check. Import into a new empty bare repository, then
  run full fsck. This also proves a supposedly full bundle is self-contained.
- With a no-remote policy, bootstrap using `git init --bare` and a fetch from
  the bundle path; `git clone bundle ...` would create an `origin` by default.
- On receipt, take a private copy for verify/import so file sync cannot replace
  it between checks. Fetch into a distinct review namespace, disable automatic
  tag following, and avoid updating HEAD or the index. Inspect bundle refs
  before constructing refspecs; never blindly force them onto local branches.
- Review and integrate explicitly. A dirty synced checkout must not be reset to
  an incoming branch. Preserve local work and use an unsynced checkout when
  reconciling divergence. Even an allowed checkout/merge writes files that would
  then sync to peers; coordinate the working-file handoff too.
- Verify delivery on the intended peers. An import should leave HEAD, staged
  entries and working files unchanged unless integration was explicitly part
  of the operation. Test corruption rejection and this invariant in disposable
  repositories when creating transfer tooling.

Use full bundles until incremental transfer is justified. Incremental bundles
have prerequisites and need a retention/import-order scheme. Full bundles can
consume substantial space; retire generated artifacts only after a verified
replacement and required recovery history are retained.

Source: [Git bundle documentation](https://git-scm.com/docs/git-bundle).

## hq-specific policy and existing tools

These are local conventions, not defaults for other repositories:

- hq has no Git remote and must never be pushed to a hosting service.
- Its standard location is `~/Syncthing/Syncthing-mobile-docs/hq`; discover the
  actual share path on the current device rather than copying a Linux username
  onto macOS or Android.
- Read `git_on_syncthing.md` in hq for the current rollout and recovery record.
  The canonical implementation is `homelab/tools/hq-git-sync.py` in that repo;
  do not duplicate its mutable code into this skill.
- **Since 2026-09-12 Git for hq lives only on `minisforum-um880`** (Oriol's
  decision, superseding the per-device-`.git` + bundle handoff of 2026-09-09).
  Every other device installs the exclusion with `make git-protect` and keeps
  no `.git`; commits from another device go through `make git-commit MSG=...`,
  which waits for minisforum to report the share complete and commits over ssh.
  `make git-check` validates the exclusion; `make git-bundle` on minisforum is
  the backup artifact. The helper's `import` command still exists for recovery
  and deliberately does not advance the local branch.
- `hq/.stignore-hq` is included from the parent share's `.stignore` on each
  migrated device. Merely receiving the tracked include is not installation.
- Migrated: minisforum, fw13pro, Mac mini (2026-09-09), xps13wc (2026-09-12,
  `.git` removed). Verify current devices; do not claim the remaining fleet was
  migrated.
- Preserve concurrent sessions' staged and unstaged edits when committing a
  repair. Use an isolated index for task-only commits when needed and compare
  unrelated entries before/after. Recheck HEAD before updating it; a local
  writer can commit even while Syncthing is paused.
