---
name: oj-review
description: Full review pass on the changes in scope — simplify, code-review with fixes applied, then an adversarial Codex review in a herdr pane running alongside a security review. Accepts a scope in words ("today's commits", "last 7 days"). Run only when the user types /oj-review.
argument-hint: "[scope: today | last 7 days | since master | last 3 commits] [focus]"
disable-model-invocation: true
---

# /oj-review — the whole review ladder in one command

## Scope

Resolve `$ARGUMENTS` first, with the one shared implementation:

```bash
oj-codex scope '$ARGUMENTS'
```

Put the user's words in SINGLE quotes (each `'` written as `'\''`), never
double quotes: a `$`, backtick or `"` in them would be run or split by bash. It prints `BASE=` (empty = the uncommitted changes), `COMMITS=`, `RANGE=` and
`FOCUS=` (the words left after the scope). Tell the user the range and the
commit count in one line. On a non-zero exit, relay its stderr and stop.
Every step below gets the scope ("the changes in BASE..HEAD plus the
uncommitted ones", or "the uncommitted changes") and the FOCUS. When BASE is
the empty tree `4b825dc…` (the scope reaches the root commit), it is not a
commit: tell steps 1, 2 and 4 "every commit up to HEAD plus the uncommitted
ones" instead of a BASE..HEAD range, and pass `--base BASE` to `oj-codex`
only.

## The ladder

1. **Simplify** — invoke the `simplify` skill on the code in scope.
2. **Code review, fixes applied** — invoke the `code-review` skill with
   `--fix`, naming the scope (BASE as the target when it accepts one).
3. **Adversarial Codex review** — now, after steps 1–2 changed the code (the
   next step only reports, it changes nothing). As a Bash task with
   `run_in_background: true` (description "Codex adversarial review"):

   ```bash
   oj-codex review [--base BASE] ['FOCUS']
   ```

   Do not wait for it: you are woken with the review when it finishes; then
   present it and say which findings you agree with. Inside herdr it runs in
   a pane next to this one; outside, headless. On a non-zero exit relay its
   stderr (it says what to do).
4. **Security review** — invoke the `security-review` skill on the scope while
   Codex works. Report its findings; fix only what the user asks for.

When steps 1, 2 and 4 are done, give ONE short summary: the scope (range and
commit count), what simplify changed, what code-review fixed (and anything it
left), the security findings, and that Codex's review comes back here when it
finishes. Never claim a step ran if it was skipped, and say why.
