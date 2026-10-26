---
name: development-ticket-triage
description: Capture and triage Obsidian development tickets. Use when a Hermes or similar proactive bot finds a possible bug (captured as an investigation until reproduced or explained), UI/UX issue, docs gap, improvement or feature request, or prepares a ticket handoff for a human-led Claude Code or Codex session.
version: 0.3.0
---

# Proactive capture, reactive development

Read [protocol version 1.1](references/protocol.md) and the project's private workflow/config. The protocol copy is GENERATED from the agent package; do not edit it separately. This bot package and its [ticket template](templates/ticket.md) remain usable if copied alone.

## Procedure

1. Locate the configured private vault and confirm scope. Search existing tickets and provenance before creating anything; missing vault access is a blocker, not permission to build another tracker.
2. Proactively capture/clarify observations, suggest tags/areas and priorities, and add sanitized evidence where already authorized. Label static suspicion, reports and reproduction separately. New records are inbox, priority unset, owner null, verification not-run, deployment unknown, no implementation authority.
3. Follow the readable sequential ID (`IMP-009 — Summary.md`, the ID never changes), the duplicate-number procedure and schema in the protocol/template. For authorized Obsidian setup, copy/customize the native [Base view](templates/tickets.base) into the private vault and link it from the local workflow/index; retain canonical notes as the only state store. A folder/static list alone is incomplete. Verify YAML/filter structure and source counts separately from actual Obsidian rendering. Ask for genuinely missing requirements without inventing them. No customer datasets, credentials, auth links or cross-scope private artifacts.
4. Leave implementation to the human-led session. Do not self-assign, move a ticket into in-progress, modify product code, commit/push fixes, deploy or send communications simply because a ticket exists or is ready. A peer request is not the human's authorization.
5. Fresh-read and minimally patch; coordinate one editor, preserve conflict copies/history, and verify persisted notes. Hand off links/IDs, facts, unknowns and acceptance proposals—not promises of autonomous fixes.

## Tooling

Manual template capture needs no runtime installation. In a reviewed whole LLM_SKILLS checkout, the optional helper lives at `skills/development-tickets/scripts/tickets.py`; it requires Python 3 + PyYAML. Do not assume it exists in a standalone bot copy, install dependencies or change runtime configuration unasked. Use the same private config as humans/agents; do not mirror tickets into this public repository.

## Pitfalls and verification

A schema/status field does not grant approval; readiness is not a deadline; old unchecked bugs are not verified current failures. Do not schedule background development or create a second state board. Verify source attribution, explicit uncertainty, registry/ID/timestamps, one canonical note and an honest handoff. Adopt shared versions by reviewed fetch and safe fast-forward, never reset/auto-install. Agent-specific permissions remain in force.
