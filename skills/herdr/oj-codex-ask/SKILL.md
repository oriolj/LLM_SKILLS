---
name: oj-codex-ask
description: Ask Codex for a second opinion about what we are working on right now, in a herdr pane that stays open so the user can keep chatting with Codex there. Run only when the user types /oj-codex-ask.
argument-hint: "<question for Codex>"
disable-model-invocation: true
---

# /oj-codex-ask — a second opinion from Codex, in a pane that stays open

Send Codex the context of the current work and the question in ONE Bash call,
as a task with `run_in_background: true` (description "Codex second opinion"),
the context on stdin:

```bash
oj-codex ask --context-file - '$ARGUMENTS' <<'CONTEXT'
<the context>
CONTEXT
```

Put the user's words in SINGLE quotes (each `'` written as `'\''`), never
double quotes: a `$`, backtick or `"` in them would be run or split by bash.

Write it from THIS session, in English, at most ~60 lines, facts only, no
secrets: the goal; the repo and the files that matter (paths — Codex reads
the code itself); what has been done and decided and why; the current state
(what works, what fails, the exact error); constraints the user stated.

One Codex pane per Claude session: if this session already asked or
consulted Codex and its pane is still open, `oj-codex` sends the question
there and Codex keeps the conversation; otherwise it opens one. So write
the context as if Codex may already know the earlier exchange, but do not
rely on it.

Do not wait or poll in this turn: tell the user Codex is thinking in the pane
to the right (outside herdr it runs headless: no pane, nothing to keep
chatting with). When the task finishes you are woken with the answer: present
it, say where you agree or disagree and why, and, inside herdr, that the pane
stays open to keep talking to Codex. On a non-zero exit, relay its stderr.
