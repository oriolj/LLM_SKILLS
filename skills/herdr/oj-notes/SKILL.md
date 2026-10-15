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

The first time you use the note from a pane, `oj-notes` records your session
id and that pane in its front matter, so a resumed conversation finds the
same note from another pane, and the user's `prefix+m` there opens the same
one.

If you only see a note on screen (for example after `herdr pane read`), its
front matter names the file: `path:` is where it lives, `file:` its name,
`session:` and `herdr_pane:` who it belongs to. Go to the file; do not work
from the screen text.

## Read and change it: only through `oj-notes`

**Never write the note's file yourself** (no Write, no Edit tool, no `sed`,
no `>` redirection). The user may have typed and auto-saved a line a second
after you read the file: a write from your copy would undo it, and the
editor would reload the result without a word. `oj-notes` hands your change
to the editor, which applies it to the text the user is typing in, between
two keystrokes; when the note is not open, it changes the file under a lock.

```bash
oj-notes read                              # the note as the user sees it now (unsaved typing included)
oj-notes append '- [ ] call the supplier'  # add a line at the end
oj-notes append <<'EOF'                    # several lines, any characters
## Friday
- [ ] deploy the fix
EOF
oj-notes replace -- '- [ ] call the supplier' '- [x] call the supplier'   # tick it
oj-notes replace -- $'- [ ] stale item\n' ''                               # remove a whole line
oj-notes replace --json <<'EOF'                                           # awkward text
{"old": "text with 'quotes'", "new": "the new text"}
EOF
```

`replace` has the contract of an Edit tool: OLD must appear **exactly once**
in the current note. If it is not there (the user changed it meanwhile) or
appears twice, nothing changes and the exit code is 7: `oj-notes read`
again, then retry with the current text (more context if it was ambiguous).
Put `--` before OLD and NEW: a todo line starts with `-`. To remove a line,
include its newline in OLD (bash `$'...\n'`).

`--file FILE` makes `read`, `append` and `replace` work on another file, for
example a TODO you showed with `oj-notes open`: the same rule applies to
every file the side editor shows.

Rules that keep it a shared space:

- **Small changes, from a fresh read.** Read right before you change
  something, change the lines you mean, never the whole note.
- **Never touch the front matter** (the block between the first two `---`).
  It is how the note is found again.
- **Do not reformat or reorder the user's text.** Add, tick, remove or amend
  what was asked. Their wording stays theirs.
- **Todos are Markdown checkboxes**: `- [ ] open`, `- [x] done`. Tick an
  item by changing its box, do not delete it unless asked to.
- **Say what you changed** in one line in the chat, since the change appears
  beside the user without any other signal.

Exit codes of `read`, `append`, `replace` and `sync`:

| code | meaning | what to do |
| --- | --- | --- |
| 0 | done | |
| 3 | this pane has no note yet (`read`, `replace`) | `append` creates it, or `oj-notes path --create` |
| 4 | the editor failed, or runs without its config | tell the user the message |
| 5 | the user must act in the editor: a conflict (`:e!` takes the disk version, `:w!` keeps theirs), or text it cannot write (auto-save switched off, a failed save) | tell the user, change nothing until then |
| 6 | the editor cannot answer now: a prompt, a command line they are typing, or still starting | retry in a few seconds; do not fall back to writing the file |
| 7 | `replace` refused: OLD not in the note, or not once | `read` again and retry |

`oj-notes sync` makes the editor write what the user typed and pick up the
disk. `read` and `replace` already do that; use `sync` before reading the
file with other tools (a `grep` over the notes folder) or before handing it
to something else.

When the user changes the same lines you changed at the same moment, the
editor keeps both versions one after the other: tidy that up only if the
user asks.

## Open and close things for the user

```bash
oj-notes wall --no-focus   # open this pane's note in the side pane (creates it if needed)
oj-notes open <file>       # show another file below the note, e.g. a TODO you wrote
oj-notes close <file>      # take that file off the side editor again
oj-notes close             # close the side pane (the note stays on disk)
```

- Use `open` when you created or changed a file the user should keep an eye
  on (a TODO, a plan, a checklist). It opens the side pane first if needed.
  Markdown and text files there save themselves; other files do not. Write
  such a file with your own tools BEFORE you open it; once it is open,
  change it only with `oj-notes append/replace --file <file>`.
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
- Neovim missing or older than 0.10, or its config not deployed: `oj-notes
  wall` and `open` exit 4 and the side pane does not open (or closes again).
  `oj-notes append` still works on the file; tell the user it will show
  beside them once Neovim and the dotfiles are installed.

## What not to put in the note

It is a synced folder that also reaches the user's phone: no credentials,
tokens or other people's personal data. Durable project facts belong in the
project's own docs; the note is for the work in progress.
