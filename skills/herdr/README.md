# herdr skills

Skills that only work inside a [herdr](https://herdr.dev) pane: they open
panes, start agents in them and talk to those agents through the herdr CLI.
One skill per subfolder (`<name>/SKILL.md`). Claude Code discovers skills only
one level below `skills/`, so these are linked FLAT: `~/.claude/skills/<name>`
-> `LLM_SKILLS/skills/herdr/<name>` (hq homelab/ansible, `claude` tag).

- `oj-codex-review` — adversarial QA by Codex in a pane next to yours.
- `oj-codex-ask` — a second opinion from Codex; the pane stays open to chat.
- `oj-codex-opinion` — `oj-codex-ask` with the question prefilled: Codex's
  opinion on what we are discussing right now.

All three drive `oj-codex` (hq `homelab/ansible/roles/development/files/oj-codex`,
installed into `~/.local/bin` by the `herdr` tag), which owns every mechanic:
scope words -> base commit (`oj-codex scope`), the pane, the question
templates, the headless fallback outside herdr, and the error messages the
skills relay. Design and traps: hq `homelab/dotfiles/HERDR.md`, "Codex in a
pane". `/oj-review` (top-level `skills/oj-review`) uses it too.
