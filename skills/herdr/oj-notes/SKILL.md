---
name: oj-notes
description: Work with the shared note beside this herdr pane — one Markdown file the user and the agent both edit, shown in a 30% side pane (the user opens it with prefix+m). Use when the user mentions "the note", "my notes", "the wall", "the side note", "the note on the right", "write that down", "add it to the note / to the todo list", "tick that off", "remove that line from the note", "what is in my notes", "open the TODO next to you", "show me that file on the side", "close the note", or asks to plan something together in the note. Also when the user types /oj-notes. Covers finding this pane's note, reading and editing it safely while the user types in it, opening and closing other files in the side editor, and what to do outside herdr.
argument-hint: "[what to do with the note]"
disable-model-invocation: false
---

# /oj-notes — the shared note beside this pane

Each herdr pane can have one **shared note**: a Markdown file that the user
edits in Neovim in a narrow pane on the right, and that you edit as a file.
Think of it as a wall you both write on: plans, todos, decisions, things to
come back to. The user opens it with `prefix+m`; you can open it too.

Everything goes through one CLI, `oj-notes`. It only knows the shared note
when `HERDR_ENV=1` (you are inside a herdr pane). Check that first.

## Find it

```bash
oj-notes status          # JSON: note path, whether the side pane is open, what it shows
oj-notes path            # the path only; exit 3 = this pane has no note yet
oj-notes path --create   # create the file without opening anything
oj-notes list            # every note of this folder; * marks this pane's or session's
```

The first time you use the note, `oj-notes` writes your session id into its
front matter, so a resumed conversation finds the same note from another
pane.

If you only see a note on screen (for example after `herdr pane read`), its
front matter names the file: `path:` is where it lives, `file:` its name,
`session:` and `herdr_pane:` who it belongs to. Go to the file; do not work
from the screen text.

## Read and edit it

The note is a normal file. Use your own Read and Edit tools on the path.
Bracket the work with `oj-notes sync`:

```bash
oj-notes sync    # 1. the editor writes what the user just typed
# 2. Read the file, then Edit it
oj-notes sync    # 3. the editor shows your change at once
```

Rules that keep it a shared space:

- **Read right before you edit, and make small edits.** The user may be
  typing in the note this very second. Change the lines you mean to change
  with Edit; never rewrite the whole file with Write.
- **Never touch the front matter** (the block between the first two `---`).
  It is how the note is found again.
- **Do not reformat or reorder the user's text.** Add, tick, remove or amend
  what was asked. Their wording stays theirs.
- **Todos are Markdown checkboxes**: `- [ ] open`, `- [x] done`. Tick an
  item by changing its box, do not delete it unless asked to.
- **Say what you changed** in one line in the chat, since the edit appears
  beside the user without any other signal.
- When both of you change the note at the same moment, the editor merges the
  two versions and keeps both sides' lines. If the same line was edited on
  both sides you will see both versions one after the other: tidy that up
  only if the user asks.

`oj-notes sync` exit codes: `0` done (also when the note is not open in an
editor: then the file is all there is, which is fine); `5` the editor holds
unsaved edits it could not merge, so tell the user to choose in the editor
(`:e!` takes the disk version, `:w!` keeps theirs) and do not edit until
then; `6` the editor is waiting on a prompt the user has to dismiss, and
the file on disk is still safe to read and edit.

## Open and close things for the user

```bash
oj-notes wall --no-focus   # open this pane's note in the side pane (creates it if needed)
oj-notes open <file>       # show another file below the note, e.g. a TODO you wrote
oj-notes close <file>      # take that file off the side editor again
oj-notes close             # close the side pane (the note stays on disk)
```

- Use `open` when you created or changed a file the user should keep an eye
  on (a TODO, a plan, a checklist). It opens the side pane first if needed.
  Markdown and text files there save themselves; other files do not.
- **Always pass `--no-focus` to `wall`**, and never call `herdr agent focus`,
  `tab focus` or `workspace focus`: the user runs several herdr windows, and
  a focus call drags the one they are typing in. `open`, `close` and `sync`
  never move the focus.
- Close what you opened once it is no longer needed, and say so. `close`
  refuses (exit 5) while a file there has unsaved changes.
- Do not close the side pane on your own initiative: the user put it there.

## Outside herdr, or without the side editor

- `HERDR_ENV` unset: there is no shared note. `oj-notes list --all` still
  lists every note, and `oj-notes new <title>` (run by the user; it opens an
  editor) makes a plain note for the current folder. Offer to keep the notes
  in a file of the project instead.
- Neovim missing on the machine: `oj-notes wall` and `open` exit 4 and the
  side pane does not open. `oj-notes path --create` still gives you a note
  file to write in; tell the user it will show beside them once Neovim is
  installed.

## What not to put in the note

It is a synced folder that also reaches the user's phone: no credentials,
tokens or other people's personal data. Durable project facts belong in the
project's own docs; the note is for the work in progress.
