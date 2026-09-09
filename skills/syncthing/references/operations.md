# Live state, configuration and device operations

## Discover the daemon before reading credentials

On Linux, both `~/.config/syncthing/` and `~/.local/state/syncthing/` may exist;
one can be an obsolete installation. Discover the active CLI connection first:

```bash
syncthing cli show version
syncthing cli config gui raw-address get
syncthing cli config folders list
```

Capture `syncthing cli config gui apikey get` inside a script, without printing
it or putting the value in shell history or a command argument. Discover the
GUI TLS setting too; do not assume an HTTP URL or disable certificate checking
to work around discovery errors. If the CLI cannot reach the daemon, inspect
the running process/service and its configured paths. Do not install a second
daemon merely because a binary is absent from PATH.

Useful read-only REST endpoints:

| Endpoint | Evidence |
|---|---|
| `GET /rest/system/status` | Local device identity and runtime information |
| `GET /rest/system/connections` | Which peers are connected |
| `GET /rest/config/folders` | Actual paths, folder types, pause and versioning settings |
| `GET /rest/db/status?folder=<id>` | Scan/sync state, pending counts and pull errors |
| `GET /rest/db/ignores?folder=<id>` | Installed rules, expansion and parse errors |
| `GET /rest/db/file?folder=<id>&file=<relative-path>` | Indexed state of a particular file |

Use the discovered address and an `X-API-Key` header. URL-encode ids and file
paths. Read the fields needed rather than logging a full configuration with
credentials. Treat configured peer identity as authoritative; a LAN IP alone
is not an identity check.

## Diagnose before changing settings

- Check daemon/service state, share/device pause state, connectivity, folder
  errors, disk space and permissions. A peer can be connected while a particular
  share is paused or unavailable.
- Check the folder type before treating local differences as an error.
  Send-only and receive-only change which side's modifications propagate.
  **Override Changes** and **Revert Local Changes** can discard differences;
  do not use them as generic conflict-cleanup buttons.
- A missing `.stfolder` may mean an unmounted disk or wrong path. Verify the
  intended filesystem before recreating the marker; an empty replacement path
  must not become an authoritative deletion of the real data.
- If a known source file was never announced, rescan the device holding that
  file with `POST /rest/db/scan?folder=<id>`. Rescanning only a receiver cannot
  announce an object the sender has not indexed. Bound retries and examine the
  source/error after a failed rescan instead of repeatedly restarting services.

For Oriol's managed Linux laptops, inspect `powerprofilesctl get` and
`syncthing-power-guard.service`: the guard stops Syncthing in `power-saver`,
which can persist even after charging. Confirm this host actually uses the
guard. Changing the power profile may require an active local login session.

On the managed Mac mini, the existing app uses
`/Applications/Syncthing.app/Contents/Resources/syncthing/syncthing`.
Use its CLI instead of installing Homebrew Syncthing alongside it. If a restart
is needed, account for the app supervising its child process and the GUI login
session needed to reopen it. Check the host's runbook first.

## Ignore rules: location, precedence and rollout

An `.stignore` only applies at the **Syncthing folder root**, and that file is
not itself synchronized. A repository nested in a larger share needs rules
relative to the enclosing share. `.gitignore` has no effect on Syncthing.

For a repository at `share/project/`, a shared policy might contain:

```text
/project/.git
/project/.git/**
/project/.git-bundles/.partial-*
```

Install `#include project/syncthing-ignore.txt` in each device's share-root
`.stignore`. Ensure the included file exists first. Included patterns remain
relative to the share root, while nested include filenames resolve relative
to the including file. Do not create a nested `.stignore` and call it effective.

The first matching rule wins. Place protective exclusions before broad `!`
exceptions; preserve existing rules and any leading `#escape=` directive.
Use UTF-8, `//` for comments, and avoid a trailing slash when matching the
folder itself. Do not use `(?d)` on data or metadata that must be preserved.

Read existing rules, then update using
`POST /rest/db/ignores?folder=<id>` with `{"ignore": ["..."]}`. Re-read the
response and effective expansion and check for parse errors. Updating config
through REST avoids editing a stale XML file or fighting the running daemon.
For other changes, prefer a narrowly scoped PATCH where the installed version
supports it. Do not PUT a partial object that silently drops unrelated settings.

An offline peer remains unmigrated. Excluding metadata on a healthy machine
protects that machine, but unprotected peers can still sync metadata between
themselves. Keep a per-device result list and a first-use migration instruction.

Sources: [ignore semantics](https://docs.syncthing.net/users/ignoring.html),
[ignore update API](https://docs.syncthing.net/rest/db-ignores-post.html),
[configuration API](https://docs.syncthing.net/rest/config.html).

## Versioning and platform limits

Versioning is per device and defaults to off. Read the selected strategy,
retention parameters and actual version path; it can differ from `.stversions`.
Simple Versioning's count limit and age cleanup both matter. A setting of five
versions and thirty days does not promise every revision for thirty days.
Remote replacements/deletions can be archived; local edits are not versioned
by that same device. Keep an independent backup for stronger recovery.

Case-only path differences can fail on case-insensitive filesystems. Preserve
and compare both variants on a filesystem that can hold them before choosing
one spelling. Do not discard a directory merely because its name looks like a
duplicate. Sleep/background limits on mobile devices also mean "app installed"
is not evidence that a handoff has synced.

Sources: [versioning](https://docs.syncthing.net/users/versioning.html),
[folder types](https://docs.syncthing.net/users/foldertypes.html),
[synchronization behavior](https://docs.syncthing.net/users/syncing.html).
