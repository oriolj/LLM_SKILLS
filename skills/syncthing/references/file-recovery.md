# Conflict copies and missing note content

Use this for readable documents. Git's index, refs and object database need
[Git-specific recovery](git-repositories.md); do not text-merge a binary index.
Databases likewise need their application's recovery tools.

## Collect the evidence

Locate the affected share root and preserve the plain-named file, all relevant
`sync-conflict` copies, and useful retained versions outside the share before
editing or cleanup. Inventory paths, sizes and content hashes; several conflict
filenames may hold identical bytes. Deduplicate the comparison by hash while
preserving provenance and the original copies.

Include the versioning store on reachable authorized peers when needed. It may
be a custom path, and the affected file may have vanished from the current
working tree altogether. A version on another peer may have survived when no
local version did.

For Git-tracked notes, examine `HEAD:path`, relevant earlier revisions, the
current index and any known divergent/recovery refs. Do not presume HEAD is the
latest or most complete copy. If Git is damaged, preserve its metadata and repair
or inspect a healthy copy before relying on its history.

## Classify the copies before reading them

When the note is Git-tracked, hash each copy against the recent committed
revisions of its path first:

```bash
for c in $(git log --format=%h -12 -- "$path"); do
  git show "$c:$path" | cmp -s - "$copy" && echo "$copy == $c"
done
```

A copy identical to a committed revision is pure stale — nothing to merge,
delete it after the recovery set is preserved. Only the copies that match
no revision carry information, and the diff against the nearest revision
(not against the current file) shows exactly what that is. On 2026-09-20
this turned nine conflict filenames into five distinct contents and then
into three that mattered, in two commands.

Two tells from a device that was offline for a long stretch (hq,
minisforum down 37 h):

- Conflict copies whose suffix is the **local** device's own ID are the
  local, unsynced edits that lost to a peer's newer mtime — the copy is
  the side to mine, the plain-named file is the peer's.
- A **plain-named file that reappears untracked** (`git status` `??`,
  no `sync-conflict` in the name) after a peer renamed or deleted it is a
  modify-vs-delete resolution: Syncthing keeps the modified file. It is
  part of the recovery set even though nothing marks it as a conflict.

## Merge information, not timestamps

The canonical filename is not necessarily the best copy. Conflict names and
mtimes describe synchronization events, not editorial authority. A file with
more lines can still omit a unique section present in a shorter version.
Syncthing creates conflict copies; it does not perform a text merge.
[Conflict behavior](https://docs.syncthing.net/users/syncing.html).

Compare each distinct candidate against the proposed recovered document:

- Retain unique useful sections, facts, links, requirements and tasks from all
  relevant sources. This is an N-way information union, not concatenation.
- Reconcile overlap and remove duplicate passages. Keep the established file
  structure and repository link/frontmatter conventions.
- Distinguish accidentally lost content from an intentional deletion or a
  superseded instruction. Do not resurrect a completed task as pending, restore
  a revoked credential, or combine contradictory settings into apparent fact.
- Use recorded user decisions and attributable later edits to resolve conflicts.
  If incompatible alternatives remain unresolved, preserve them outside the
  published note and state what needs a decision. Do not silently choose one.

A real hq incident had six conflict filenames but only three distinct contents;
two lines existed only in Git HEAD, absent from every live copy. That is evidence
for checking all sources, not a rule that HEAD always wins.

## Validate before retiring copies

Review a diff against every distinct input and account for unique material that
was omitted: duplicate, superseded, intentionally deleted, or unresolved. Check
links and structured syntax when applicable. Content preservation cannot be
proved by line count alone.

Publish the reconciled file after coordinating writers. Resume the affected
share as appropriate and verify the intended recipients received the recovered
content. Keep the original recovery set until the result is validated. Retire
conflict copies only after preserving their evidence and unique information;
never bulk-delete them just to make the sync UI quiet.

If conflict files are tracked in Git, adding an ignore rule does not untrack
them. Review their tracked state and use a path-specific removal from the index
only when that is part of the requested cleanup; retain the recovery copies.
Do not stage unrelated files in the same operation.

Record which sources contributed to the recovered file and where originals
were saved. If versioning had no applicable copy, report that limitation rather
than implying a retention guarantee.
