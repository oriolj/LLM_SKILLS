---
name: oj-codex-review
description: Adversarial QA review by Codex, run in a herdr pane next to yours; the review comes back to this session when Codex finishes. Accepts a scope in words. Run only when the user types /oj-codex-review.
argument-hint: "[scope: today | last 7 days | since master | last 3 commits] [focus]"
disable-model-invocation: true
---

# /oj-codex-review — Codex challenges the change, in a pane you can watch

Launch, as a Bash task with `run_in_background: true` (description "Codex
adversarial review"):

```bash
oj-codex review --scope '$ARGUMENTS'
```

Put the user's words in SINGLE quotes (each `'` written as `'\''`), never
double quotes: a `$`, backtick or `"` in them would be run or split by bash.

`--scope` resolves the words ("today", "last 7 days", "since master", "last 3
commits", "A..B"; nothing = the uncommitted changes) to a base commit, and the
words left over are the focus. Do not wait or poll in this turn: tell the
user Codex is reviewing in the pane to the right (headless outside herdr).
When the task finishes you are woken with its output, the review: present it
faithfully, say which findings you agree with and why, and ask before fixing
anything. Reviews from the same session reuse their own Codex pane (kept apart
from /oj-codex-ask chats so a chat does not bias the review). On a non-zero exit, relay its stderr — it says what to do.
