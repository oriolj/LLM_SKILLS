---
name: oj-review
description: Full review pass on the changes in scope — simplify, code-review with fixes applied, security review, then an adversarial Codex review in a herdr pane. Accepts a scope in words ("today's commits", "last 7 days"). Run only when the user types /oj-review.
argument-hint: "[scope: today | last 7 days | since master | last 3 commits] [focus]"
disable-model-invocation: true
---

# /oj-review — the whole review ladder in one command

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

## The ladder

Run these four steps **in this order**, each to completion before the next.
Tell every step the scope explicitly: "review the changes in BASE..HEAD plus
the uncommitted ones" (or "the uncommitted changes"), and pass the focus text.

1. **Simplify** — invoke the `simplify` skill on the code in scope.
2. **Code review, fixes applied** — invoke the `code-review` skill with
   `--fix`, naming the scope (BASE as the target when it accepts one).
3. **Security review** — invoke the `security-review` skill on the scope.
   Report its findings; fix only what the user asks for.
4. **Adversarial Codex review** — last on purpose, so it challenges the code
   AFTER steps 1–3 changed it. Our own reviewer, in a herdr pane next to this
   one: as a Bash task with `run_in_background: true` (description "Codex
   adversarial review") run

   ```bash
   oj-codex review [--base BASE] [focus text]
   ```

   and do not wait for it in this turn — you are woken with the review when
   it finishes; then present it and say which findings you agree with.
   Exit 2 (not inside herdr): fall back to the plugin's own script in the
   background, `node <~/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs>
   adversarial-review --background [--base BASE]`. Exit 3: Codex is blocked
   on a prompt in its pane — name the pane.

When steps 1–3 are done, give ONE short summary: the scope (range and commit
count), what simplify changed, what code-review fixed (and anything it left),
the security findings, and "Codex is reviewing in the pane to the right; its
review comes back here when it finishes." Never claim a step ran if it was
skipped, and say why.

Source: LLM_SKILLS skills/oj-review, symlinked into each Claude profile's
skills/ by homelab/ansible (claude tag). Oriol, 2026-10-02.
