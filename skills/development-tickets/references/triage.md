# Triage procedure — protocol 1.2

How an agent evaluates captured tickets and records the result in the `triage`/`decision` fields of [the protocol](protocol.md#triage). Triage is read-only investigation: it never implements, pushes, deploys, sends or writes production data.

## Per ticket

1. **Read the whole ticket and list its concrete claims.** Bulk captures written from another session's notes ("according to the agent") are claims, not facts.
2. **Already done, handled or similar?** Since the ticket's `created` date:
   - `git log --all --since=<created> -i --grep=<keyword>` and `git log -S<symbol>` in the repos it names (or the likely ones when `repos: []`);
   - the cited file and line as they are now on the deployed branch;
   - the repo's `QA_PENDING.md`, `USER_TODO.md`, `TODO*.md`, `DEPLOY.md` / `docs/09-deploy-and-ops.md`;
   - other tickets, the project roadmap and the project's findings notes, for duplicates and overlaps.
   Production availability needs a readback: read the live release (a `/health` or version endpoint) and test ancestry with `git merge-base --is-ancestor <fix-sha> <live-release-sha>`. On the remote branch but not an ancestor means pushed, not deployed. Without a readback, say "merged to origin/<branch> on <date>, deploy unknown". A commit never implies production.
3. **Bugs: reproduce.** Code reading, `git show/blame`, a narrow unit test, GET-only requests to public pages, DNS/TLS probes, read-only logs. Then a hypothesis with `file:line` and mechanism, or the evidence still missing. `confidence: reproduced` only for behaviour actually observed; `suspected` for a code-based hypothesis.
4. **Clarity.** Clear to implement (scope and acceptance obvious), needs discussion (a product, UX, cost or scope choice — list the exact questions), or needs investigation (and what access or data it needs).
5. **Size and priority proposal** (S/M/L/XL; p0–p3 or "close"), with the reason. Proposals only.
6. **Write back** (one editor per ticket, fresh-read, narrow patch): a dated `### Triage review <date>` subsection under Source and evidence, in the language of the existing notes, separating checked facts from hypotheses; a History line; `triage: agent-reviewed`, `triaged_by`, `triaged`; `decision: needs-discussion` when step 4 found open questions (otherwise leave `pending`); `confidence` only per step 3; `repos`/`areas` only from verified evidence and the registry; `updated`. Never change status or priority, close, or set `agreed`/`declined`. Run `tickets.py check` afterwards.

An agent may not triage a ticket it captured itself: `agent-reviewed` needs an independent reviewer.

## Whole-backlog runs

One read-only subagent per ticket in parallel, the orchestrator writing every note itself afterwards (serially, after reading each result), works well:

- Fetch every repo once before the fan-out. The subagents never fetch, pull, check out, stash, commit or edit: other sessions keep uncommitted work in the same checkouts.
- Pass the live release SHA and the timestamp into the prompts; each subagent returns a fixed schema (verdict, evidence, deployed status, claims checked, reproduction, confidence, hypothesis, clarity, decisions, blocker, repos, size, priority proposal, overlaps, a ready-to-paste ticket note).
- Hard rails in every prompt: production GET only, no logins or test-tenant writes, no package installs or `uv sync`, no dev servers that proxy production, no make target whose recipe was not read, never print a credential value (report where a secret is, never what it is).
- Afterwards the orchestrator writes the notes, runs `check`, saves a dated receipt note next to the tickets (what was reviewed, the proposals), and brings the human lead the close proposals, priority proposals and the open questions. The human then marks `human-reviewed` and sets `agreed`/`declined` and priorities.
