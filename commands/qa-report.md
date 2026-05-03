---
name: qa-report
description: Generate a QA testing report from recent git changes — lists new features, potential breaking changes, and testing checklist with priorities
user_invocable: true
---

# QA Report Generator

Generate a comprehensive QA testing report based on recent changes on the current branch.

## Instructions

1. **Identify all repositories** in the working directory (check for `bikecrm-backend/`, `bikecrm-frontend/`, `bikecrm-docs-astro/` or similar subdirectories with `.git`). If the working directory itself is a git repo, use that.

2. **For each repository**, run these commands to gather changes:
   - `git log origin/main..HEAD --oneline` (or `origin/master..HEAD` or `origin/beta..HEAD` — use whichever remote branch exists)
   - `git diff origin/main..HEAD --stat` (same branch as above)
   - If no remote tracking, use `git log --oneline -20` to get recent commits

3. **Analyze all commits and diffs** to categorize changes into:
   - **New features**: New pages, endpoints, components, or user-facing functionality
   - **Modified behavior**: Changes to existing features that users will notice
   - **Bug fixes**: Corrections to existing behavior
   - **Security fixes**: Auth, permission, or data exposure changes
   - **Performance**: Index changes, query optimizations
   - **Internal/Docs**: Documentation, refactoring, code cleanup

4. **Assess importance** for each item:
   - **HIGH**: Core business functionality, security fixes, data integrity, breaking changes
   - **MED**: New features, UX changes, performance improvements
   - **LOW**: Documentation, minor UI tweaks, internal refactoring

5. **Generate the markdown file** at `qa/YYYY-MM-DD-short_description.md` where:
   - `YYYY-MM-DD` is today's date
   - `short_description` is a 2-4 word snake_case summary of the main changes (e.g., `rental_calendar_analytics`)

6. **Use this template** for the report:

```markdown
# QA Report — [Date]

## Summary
[1-3 sentence summary of what changed in this batch]

## New Features

| Feature | Description | Importance | Location |
|---------|-------------|------------|----------|
| ... | ... | HIGH/MED/LOW | route or file |

## Things That Could Break

| Risk | Description | Importance | What to check |
|------|-------------|------------|---------------|
| ... | ... | HIGH/MED/LOW | ... |

## Testing Checklist

### HIGH Priority
- [ ] **[Feature/Fix name]** — [Specific test steps]
  - Step 1
  - Step 2
  - Expected result

### MED Priority
- [ ] **[Feature/Fix name]** — [Specific test steps]

### LOW Priority
- [ ] **[Feature/Fix name]** — [Specific test steps]

## New Features to Review & Learn

| Feature | What it does | Where to find it | Notes for QA team |
|---------|-------------|-------------------|-------------------|
| ... | ... | ... | ... |
```

7. **Be specific in test steps** — include actual URLs, button names, and expected outcomes. The QA team should be able to follow the checklist without reading code.

8. **For breaking changes**, explain what worked before and what changed, so the QA team knows what regression to look for.

9. **Create the `qa/` directory** if it doesn't exist.

10. After generating the report, **show a brief summary** of what was created and the key items to test.
