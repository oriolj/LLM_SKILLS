---
name: send-to-claws
description: Hand a message, a task or a file to one of Oriol's own AI agents (the "claws", Hermes Agent on the home LAN) — Pep (personal), Enzo (Enantena/EnaCast) or Bruno (SmartupSoft/BikeCRM) — from a Claude Code or Codex session on a dev machine. Use only when Oriol asks ("send this to Pep", "tell Enzo…", "pass it to Bruno", "give the claw this file") or a task explicitly says to hand something to an agent. Covers which agent gets what, the one ssh command that sends a message (named thread, stdin, no quoting traps), sending files, and what never to send.
---

# Send to the claws

Three Hermes agents, one per scope, each in an LXC container on the home LAN
(state and setup: hq `shared/docs/agents.md`; operating Hermes itself: the
`hermes` skill).

| Agent | ssh host | Scope — send it |
|---|---|---|
| **Pep** | `pep` | personal (oriolj): Oriol's life, home, family, health, side projects |
| **Enzo** | `enzo` | Enantena / EnaCast: radio, streaming, podcasts, the company's books and team |
| **Bruno** | `bruno` | SmartupSoft / BikeCRM: bike shops, BikeCRM customers, billing, support |

## Rules

- **Send only when asked** (by Oriol, or by a task that says to). Ask which
  agent when the scope is not obvious; never guess.
- **Accounts follow the scope**: never send one scope's data to another scope's
  agent (no personal health to Enzo, no EnaCast books to Bruno).
- **No secrets** (keys, tokens, passwords) in a message or a file.
- LAN only: `ssh pep` works from the dev machines at home. If it fails
  (away, box down), say so and stop; no workarounds.
- Quote the agent's reply back to Oriol. The agent may act on what you send
  (it has tools), so phrase requests exactly as Oriol meant them.

## Send a message (one command)

```bash
HOST=pep THREAD="from-claude-code"   # host from the table; one thread per topic
printf '%s\n' "From a Claude Code session for Oriol: <the message>" |
  ssh -o ConnectTimeout=5 "$HOST" 'f=$(mktemp) && cat > "$f" &&
    timeout 900 ~/.local/bin/hermes chat -Q --oneshot --source claude-code \
      -c "'"$THREAD"'" --create-if-missing --query-file "$f"; rc=$?; rm -f "$f"; exit $rc'
```

- The message travels on stdin into `--query-file`: no shell-quoting of the text.
- `-c <thread> --create-if-missing` keeps follow-ups in one conversation (verified:
  the second send resumes the thread). Use a new thread name for a new topic.
- `--source claude-code` (or `codex`) tags the session so Oriol can tell it apart.
- The reply prints on stdout, then `session_id: …`. A turn can take minutes.
- If what you send changes the agent's lasting instructions (memory, persona,
  a skill), finish with the `hermes` skill's self-review step: a fresh one-shot
  asking the agent to review those files read-only.
- Never pass `--yolo`. If the agent should remember something durably, say so in
  the message and check the reply says where it saved it.
- Where the dev machine has them, `hermes-pep` / `hermes-enzo` / `hermes-bruno`
  wrap the same `ssh <host> ~/.local/bin/hermes …` for interactive use.

## Send a file

```bash
ssh pep 'mkdir -p ~/inbox/from-agents'
scp ./report.pdf pep:inbox/from-agents/
```

Then send a message naming the path (`~/inbox/from-agents/report.pdf`) and what
to do with it. Audio is fine: the agents transcribe it themselves (NaN Whisper,
any of English/Catalan/Spanish).
