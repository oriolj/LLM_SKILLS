# Bot skills

Skills for proactive Hermes/similar bots, separate from human-led coding-agent skills under `skills/`. Existing agent skill paths remain unchanged.

- [development-ticket-triage](development-ticket-triage/SKILL.md): capture/triage and handoff; never infer permission to implement.

Both roles share [one canonical development-ticket protocol](../skills/development-tickets/references/protocol.md). The bot package includes generated identical protocol/template copies for standalone portability. Check them from repository root with `python scripts/sync_ticket_protocol.py --check`; regenerate explicitly after a canonical edit (without `--check`).

This directory is not covered by the existing documented Claude Ansible link glob. Do not claim adding it registers a Hermes skill. Read a skill directly for a task, or install only through that runtime's documented, authorized workflow. No installer/cron/config changes are part of this repository addition.

Keep private vault configuration/tickets outside this public repository. Fetch/review/fast-forward on clean clones; record adopted version/commit. Commit authors use their real agent names and accurate Agent/Model/Reasoning-Effort trailers, with not-exposed for unknown metadata. Never infer author identity or permissions from a skill file.
