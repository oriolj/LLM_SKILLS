---
name: oj-codex-opinion
description: Ask Codex for its opinion on what we are discussing right now — the approach or decision on the table — in a herdr pane that stays open so the user can keep chatting with Codex. Like /oj-codex-ask with the question prefilled. Run only when the user types /oj-codex-opinion.
argument-hint: "[optional angle, e.g. 'mainly the data model']"
disable-model-invocation: true
---

# /oj-codex-opinion — Codex's take on what we are discussing

Same flow as `/oj-codex-ask`, with the question already written.

1. Write the context to `/tmp/oj-codex/context-$(date +%Y%m%d-%H%M%S).md`
   (create the dir), from THIS session, in English, at most ~60 lines, facts
   only, no secrets: the goal; the repo and the files that matter (paths —
   Codex reads the code itself); what we are discussing right now, stated
   neutrally — the options on the table, the one currently favoured and the
   reasons given for it; what is already decided and why; open questions and
   constraints the user stated. Do not argue for our side: Codex should form
   its own view.
2. Launch, as a Bash task with `run_in_background: true` (description
   "Codex opinion"):

   ```bash
   oj-codex ask --context-file /tmp/oj-codex/context-….md "What is your opinion on what we are discussing? Judge the approach or decision on the table: is it right, what would you do differently, which risks or assumptions are we missing, and which option would you pick and why. Be direct and disagree where you do. $ARGUMENTS"
   ```

   (`$ARGUMENTS`, if any, narrows the angle.) Do not wait or poll in this
   turn: tell the user Codex is thinking in the pane to the right.
3. When the task finishes you are woken with Codex's opinion. Present it
   faithfully, then say where you agree, where you do not and why — no
   automatic deference either way — and that the pane stays open for the
   user to keep talking to Codex directly.

Exit codes: 3 = Codex is blocked on a prompt in its pane; 2 = not inside
herdr; 4 = timeout or no answer file. `oj-codex` (hq homelab/ansible, herdr
tag) owns the mechanics. Source: LLM_SKILLS skills/herdr/oj-codex-opinion.
Oriol, 2026-10-02.
