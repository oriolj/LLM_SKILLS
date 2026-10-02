---
name: oj-codex-ask
description: Ask Codex for a second opinion about what we are working on right now, in a herdr pane that stays open so the user can keep chatting with Codex there. Run only when the user types /oj-codex-ask.
argument-hint: "<question for Codex>"
disable-model-invocation: true
---

# /oj-codex-ask — a second opinion from Codex, in a pane that stays open

1. Write the context to a file Codex will read, e.g.
   `/tmp/oj-codex/context-$(date +%Y%m%d-%H%M%S).md` (create the dir). Make it
   what a colleague joining now would need, from THIS session, in English:
   the goal, the repo and the files that matter (paths), what has been done
   and decided so far and why, the current state (what works, what fails, the
   exact error if any), and any constraint the user stated. Facts only, no
   secrets or credentials, at most ~60 lines. Codex can read the code itself,
   so point at files rather than pasting them.
2. Launch, as a Bash task with `run_in_background: true` (description
   "Codex second opinion"):

   ```bash
   oj-codex ask --context-file /tmp/oj-codex/context-….md "$ARGUMENTS"
   ```

   Do not wait or poll in this turn: tell the user Codex is thinking in the
   pane to the right.
3. When the task finishes you are woken with Codex's answer. Present it, say
   where you agree or disagree and why, and mention the pane stays open
   for the user to keep talking to Codex directly.

Exit codes: 3 = Codex is blocked on a prompt in its pane; 2 = not inside
herdr; 4 = timeout or no answer file. `oj-codex` (hq homelab/ansible, herdr
tag) owns the mechanics. Source: LLM_SKILLS skills/herdr/oj-codex-ask.
Oriol, 2026-10-02.
