---
name: oj-codex-review
description: Adversarial QA review by Codex, run in a herdr pane next to yours; the review comes back to this session when Codex finishes. Run only when the user types /oj-codex-review.
argument-hint: "[scope: today | last 7 days | since master | last 3 commits] [focus]"
disable-model-invocation: true
---

# /oj-codex-review — Codex challenges the change, in a pane you can watch

## Scope: from words to a git base

`$ARGUMENTS` may name a scope in plain words. Resolve it to a BASE commit
before doing anything else, show the user the range and the commit count in
one line, and use it in every step:

- nothing about scope → the uncommitted changes (no base);
- "today" / "today's commits" → `first=$(git rev-list --reverse --since=midnight HEAD | head -1)`, BASE=`${first}^`;
- "last N days" / "past week" / "7d" → the same with `--since="N days ago"`;
- "last N commits" → `HEAD~N`;
- "since <branch|tag|sha>" / "vs master" → `git merge-base HEAD <ref>`;
- a range `A..B` → BASE=A (and say B must be HEAD, or check it out first).

If the first commit has no parent (root commit), BASE is the empty tree
`4b825dc642cb6eb9a060e54bf8d69288fbee4904`. If the range is empty, say so and
stop. Whatever text is left after the scope words is the focus.

## Run it

Launch, as a Bash task with `run_in_background: true` (description
"Codex adversarial review"):

```bash
oj-codex review [--base BASE] [focus text]
```

Do not wait for it or poll it in this turn: tell the user Codex is reviewing in
the pane to the right. When the background task finishes you are woken with
its output — the review. Then present it faithfully: the findings by severity,
which ones you agree with and why, and ask before fixing anything.

Exit codes: 3 = Codex is blocked on a prompt in its pane (name the pane, the
user answers it, then rerun); 2 = not in herdr or not a git repo (fall back to
`/codex:adversarial-review`, which the user must type); 4 = timeout or no
answer file (point at the pane).

`oj-codex` (hq homelab/ansible roles/development/files, installed into
~/.local/bin by the herdr tag) owns the mechanics. Source: LLM_SKILLS
skills/herdr/oj-codex-review. Oriol, 2026-10-02.
