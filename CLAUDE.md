# CLAUDE.md

This repo is a personal collection of Claude Code skills and slash commands authored by the user. It is the source-of-truth copy; the live versions get symlinked (or copied) into `~/.claude/skills/` and `~/.claude/commands/`.

## Repo layout

- `skills/<name>/SKILL.md` — skill body with YAML frontmatter (`name`, `description`). Optional `references/` folder for supporting docs the skill loads on demand.
- `commands/<name>.md` — slash command, invoked as `/<name>`. Frontmatter sets `name`, `description`, and `user_invocable`.

## Conventions when editing

- **Frontmatter `description` is load-bearing.** It's how Claude decides whether to invoke the skill/command, so be specific about triggers. Include concrete user phrasings and example questions, not just topic names.
- **Don't rename a skill or command without updating the symlink target** in `~/.claude/`.
- **Keep skills self-contained.** A skill should reference its own `references/*.md` files using relative paths, not absolute ones — that way it works whether installed via symlink or copy.
- **No emojis** in skill or command bodies unless the user explicitly asks.
- **Commands write output to predictable paths** (e.g. `/qa-report` writes to `qa/YYYY-MM-DD-*.md`). Preserve that contract when editing.

## Adding a new skill or command

1. Create `skills/<name>/SKILL.md` or `commands/<name>.md` with frontmatter.
2. Add a one-line entry to `README.md` under the matching section.
3. Symlink it into `~/.claude/` so it becomes active.
