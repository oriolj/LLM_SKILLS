---
name: oj-codex-opinion
description: Ask Codex for its opinion on what we are discussing right now — the approach or decision on the table — in a herdr pane that stays open so the user can keep chatting with Codex. Like /oj-codex-ask with the question prefilled. Run only when the user types /oj-codex-opinion.
argument-hint: "[optional angle, e.g. 'mainly the data model']"
disable-model-invocation: true
---

# /oj-codex-opinion — Codex's take on what we are discussing

The question is built into `oj-codex opinion` (is the approach right, what
would it do differently, which risks we miss, which option it would pick);
`$ARGUMENTS` only narrows the angle. ONE Bash call, as a task with
`run_in_background: true` (description "Codex opinion"), 1. Write the context with the **Write tool** to a new file of your own (in
   your scratchpad directory if this session has one, else under a fresh
   `mktemp -d`). Not a heredoc: a line in the context that equals the
   heredoc's end marker would end it and run the rest as shell commands.
2. Then ONE Bash call, as a task with `run_in_background: true`
   (description "Codex opinion"):

   ```bash
   oj-codex opinion --context-file <that file> -- '$ARGUMENTS'
   ```

Put the user's words in SINGLE quotes (each `'` written as `'\''`), never
double quotes: a `$`, backtick or `"` in them would be run or split by bash.

Write it from THIS session, in English, at most ~60 lines, facts only, no
secrets: the goal; the repo and the files that matter (paths — Codex reads
the code itself); what has been done and decided and why; the current state
(what works, what fails, the exact error); constraints the user stated.
State what we are discussing **neutrally**: the options on the table, the
one currently favoured and the reasons given — do not argue for our side,
Codex should form its own view.

One Codex pane per Claude session: if this session already asked or
consulted Codex and its pane is still open, `oj-codex` sends the question
there and Codex keeps the conversation; otherwise it opens one. So write
the context as if Codex may already know the earlier exchange, but do not
rely on it.

Do not wait or poll in this turn: tell the user Codex is thinking in the pane
to the right (outside herdr it runs headless: no pane, nothing to keep
chatting with). When the task finishes you are woken with its opinion: present
it faithfully, then say where you agree and where you do not, with no
automatic deference either way, and, inside herdr, that the pane stays open. On a non-zero
exit, relay its stderr.
