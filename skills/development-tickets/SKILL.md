---
name: development-tickets
description: Work human-led development from Obsidian tickets. Use when asked to capture a bug, feature, improvement or investigation (an error-tracker event or user report not yet confirmed as a bug), triage a development backlog, pick a ticket with Claude Code or Codex, update ticket progress, verify completion, or coordinate tickets with a Hermes bot.
version: 0.4.0
---

# Human-led development tickets

Read [the shared protocol](references/protocol.md) (version 1.2) and the project's private workflow/config before touching tickets. This package is self-contained when copied. Shared protocol source is in this package; the bot package receives a generated exact copy.

## When to use

Capture/triage bugs, improvements, features, investigations, docs, chores or research; work a ticket selected by the human lead; record truthful implementation, verification and deployment history. Do not use to start autonomous development or replace a project tracker without authority.

## Procedure

1. Locate the private ticket-system.json and local workflow from project AGENTS.md/CLAUDE.md or the current human instruction. If unavailable, stop rather than inventing a fallback vault. Load [protocol](references/protocol.md) and [template](templates/ticket.md).
2. Read the current ticket/source; search existing IDs and summaries, including linked historical boards. Capture only an inbox record with no owner/authorization by default. Explicitly label suspected vs reproduced. When authorized to set up an Obsidian tracker, include the native [Base template](templates/tickets.base) as the working view, customize its vault-relative folder/project filters, and link it from the private workflow/index. A folder/static list alone is not the finished Obsidian setup; see the protocol for verification limits.
3. For implementation, confirm the human lead chose this ticket and authorized the actual scope. Read repository/domain guardrails; ticket fields and bot suggestions do not supply authority. Record actor/time/scope before work. Push/deploy/send still require separate authorization.
4. Keep one active editor, fresh-read and narrow-patch. Maintain dates/history and canonical ID/filename. Capture implementation, verification and per-environment deployment independently. When a deployed change needs a human tester, add a `QA_PENDING.md` entry in the owning repo carrying the ticket ID and link it from Deployment evidence; the entry is a request for testing, not verification (protocol, "Handing a deployed change to QA").
5. To triage (evaluate captured tickets: already done?, reproduce, hypothesis, clarity, size, priority proposal, overlaps), follow [triage.md](references/triage.md): record `triage: agent-reviewed` only for tickets you did not capture, set `decision: needs-discussion` when a human decision is open, never set priority, close or set `agreed`/`declined`. A whole backlog runs as one read-only subagent per ticket with the orchestrator writing the notes.
6. Review every acceptance criterion. Close only with evidence and completed time; reopen without erasing history. Validate and read back the actual note. A validator is not evidence the outcome is true.

## Optional local helper

Python 3 and PyYAML are required; never install dependencies automatically. Review fetched code first. From this package directory:

    python scripts/tickets.py --config /path/to/private/ticket-system.json check
    python scripts/tickets.py --config /path/to/private/ticket-system.json list
    python scripts/tickets.py --config /path/to/private/ticket-system.json create --summary "Describe the issue" --kind bug --actor "your-actor" --area ui --repo app-ui

The first two are read-only. Create writes one inbox note with the next readable ID (`IMP-009 — Summary.md`) and empty/unknown facts. It does not authorize or start development. Use configured area/repo names; the example names are illustrative. Manual template use also works without dependencies: take the next number for the prefix (one above the highest existing, closed tickets included), name the file `<ID> — <summary>.md`, fill timestamps, set record_type to development-ticket and all actual fields before saving it in Tickets.

## Pitfalls

Do not derive production availability from master, treat ready as approval, duplicate live status into a board, guess dates/owners, reclassify old reports as current bugs, bypass opt-outs/permissions, or hide sync conflicts. Helper duplicate detection is exact-summary only; perform semantic search yourself. No helper lock coordinates multiple hosts: two hosts can mint the same number before sync converges; `check` flags the duplicate and the protocol says how to renumber.

## Verification

The correct private note exists once, links to its source, uses the documented schema, retains history, has no secrets, and reflects only observed work. The bot protocol copy must match the canonical file (`python scripts/sync_ticket_protocol.py --check` from repository root). New-session tool registration is separate from the skill existing on disk.
