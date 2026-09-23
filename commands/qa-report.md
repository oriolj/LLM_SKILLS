---
name: qa-report
description: Review a batch of commits since the last QA review — per-feature reports with numbered, severity-rated findings, a dated index that records the exact commit list and the reviewing agent, a re-check of the previous review's findings, and the qa/QA_AGENTS.md log
user_invocable: true
---

# QA report

Review a batch of commits and leave a record a future reader can trust: which
commits were looked at, by which agent, what was actually run, what was found,
and what happened to the previous review's findings. Reports live in `qa/` at
the repo root (create it if missing, with a `README.md` index and a
`QA_AGENTS.md` log — templates below).

## Rules (Oriol, 2026-09-23)

1. **The commit list analyzed is always in the report.** The index (or the
   single report) carries a `## Commits analyzed` section with the verbatim
   output of `git log --format='%h %ad %s' --date=format:'%Y-%m-%d %H:%M' <base>..<head>`
   — every commit, none summarized away. A commit deliberately left out of the
   review (the previous QA commit itself, a vendored blob, a binary asset drop)
   is still listed, with the reason next to it. Record `<base>` and `<head>` as
   short hashes in the header line.
2. **The reviewing agent is always named.** Every report's header line and the
   index say who did it: model name and id, the harness (Claude Code, Codex,
   …), the session kind (interactive session, forked subagent that inherited
   the session, or a fresh subagent), and who launched it (Oriol, a cron, a
   routine). No "Claude (automated review)" without the model id. The same
   identity goes in the `qa/QA_AGENTS.md` row for the review.
3. **Base = the head of the previous review.** Read the last row of
   `qa/QA_AGENTS.md` (or the previous index) for its head hash; that is the
   base of this review. First review of a repo: `origin/main..HEAD`
   (`master`/`beta` if that is the remote branch), or the last 20 commits
   without a remote.
4. **Previous findings are re-checked, never forgotten.** Each report re-checks
   every finding of the previous report in the same area and gives it one
   status in a `## Previous findings status` table: FIXED (commit), PARTIAL
   (what remains), OPEN, or WONTFIX-documented (where the decision is written).
   Finding ids are never reused: new findings continue the numbering after the
   previous report's last id, keeping the area prefix (B- billing, S- social
   login, P- push, D- digests, C- console, R- pro panel, T- store lanes,
   L- layout, K- docs/skills, H- home/today, M- media …; pick a new letter for
   a new area and say so).
5. **Reports are snapshots.** A report is not edited when a finding is fixed;
   the fix's commit message names the finding id (`fix B-2`, `closes P-1`).
   Decisions that only the owner can take go to `USER_TODO.md` (with why it
   needs them and what is blocked), never only into the report.
6. **Say what was actually run.** The index has a `## What was actually run`
   table: backend tests (exact pass/fail/skip counts), lint (ruff/mypy/eslint
   — and when lint is red, split the errors into "introduced by this batch"
   vs "pre-existing at base" by checking whether each file changed in the
   range), frontend builds, i18n key parity per catalog, e2e (usually NOT run —
   say so), device/store checks (usually not run — say so). Findings that
   nobody ran are static: mark each `VERIFIED` (confirmed by reading the code
   or an external doc, cited inline) or `PLAUSIBLE` (needs a run or a device).
7. **Fan out by feature area when the batch is big** (more than ~15 commits or
   more than one product surface): one report per area
   `qa/YYYY-MM-DD-<feature>.md` written by a parallel subagent, plus one index
   `qa/YYYY-MM-DD-<batch-name>.md` written by the parent that ranks everything
   across areas. Subagents are forks of the session (they inherit the repo
   context) and are told: static review only, read with `git show`/`git diff
   <base>..<head> -- <paths>`, no builds/tests/docker (the parent runs those
   once, centrally, before or while the reviewers work), do not modify any repo
   file except their own report, web research allowed where a claim rests on a
   third party (cite it, mark VERIFIED (external doc)), final message short
   (verdict, counts, Highs, previous-findings counts, stale docs) — the report
   holds the detail. A small batch is one report by the session itself, with
   the same sections.
8. **Domain owner sections.** When the project's `CLAUDE.md` names a domain
   owner who is not an engineer (Panotxa: Anna for nutrition science), every
   report whose batch changes what the product tells users in that domain gets
   a `## For <owner>'s review` section quoting the user-visible text from the
   primary-language catalog. Those items are decisions, not findings.
9. **After the index is written**: add the review's row to the `qa/README.md`
   table and to `qa/QA_AGENTS.md`; add the owner decisions to `USER_TODO.md`;
   if the project keeps `RELEASE_NOTES.md`, add a one-line entry; commit `qa/`
   with those files in one commit whose message names the base and head.

## Report format (per feature, or the single report)

```markdown
# QA review — <Area>

Reviewed: YYYY-MM-DD · Commits: <hashes, or "see index"> · Base: <hash> · Head: <hash> · Reviewer: <Model name> (`<model-id>`), <session kind> of <who>'s <harness> session — static review, no code run, repo untouched [· live pages curled read-only]

## Summary            — verdict in one paragraph + counts Critical/High/Medium/Low/Note
## Scope and what changed          — table: commit · area
## Previous findings status        — table: id · title · status (FIXED (commit) / PARTIAL / OPEN / WONTFIX-documented)
## For <domain owner>'s review     — only when rule 8 applies
## Findings                        — `### X-n · Severity · Title — VERIFIED|PLAUSIBLE`, each with file:line, failure scenario, suggested fix
## Security review
## Test coverage and QA gaps
## Manual test plan                — steps a tester follows without reading code: URL/screen, action, expected result; per ring/environment
## Internal docs audit             — table: doc · claim · status (current / stale: what is true now)
## What is solid
## Open questions for <owner>
```

Severity: **Critical** — data loss, money lost or charged wrongly, auth bypass,
production down; **High** — a user or the owner will hit it within the first
week, or a store/legal gate; **Medium** — real defect with a workaround or a
narrow trigger; **Low** — correctness nit, dead code, small UX wart; **Note** —
observation, no action required.

## Index format (fan-out batches)

```markdown
# QA Report — YYYY-MM-DD — <batch name> (<n> commits, <m> files)

Index over <k> feature reviews run in parallel on the commits between
`<base>` (<date>) and `<head>` (<date>). Reviewer: <identity per rule 2>;
per-area reports by forked subagents of the same session.

## Summary                      — the one-paragraph verdict for the batch + totals by severity
## What was actually run        — table per rule 6
## Per-feature verdicts         — table: area · report link · verdict · High · Med · Low · Note
## The Highs, grouped           — every High across reports, one line each with its id
## Previous review: what got fixed   — totals FIXED / PARTIAL / OPEN across areas, and the OPEN Highs by id
## Cross-cutting patterns
## Decisions for <owner>        — mirrored into USER_TODO.md
## Commits analyzed             — verbatim git log per rule 1, exclusions with reasons
```

## `qa/README.md` and `qa/QA_AGENTS.md`

`qa/README.md` explains the convention in a paragraph and keeps one table row
per review day (date · index · reports). `qa/QA_AGENTS.md` is the log of who
reviewed what:

```markdown
| Review | Base → Head | Commits | Agent | Session | Launched by | Ran |
|---|---|---|---|---|---|---|
| [2026-09-23](2026-09-23-<batch>.md) | `1173575` → `aeb4290` | 58 | Claude Fable 5.1 (`claude-fable-5-1`), Claude Code | interactive + 8 forked subagents | Oriol | backend tests, ruff, mypy, app + console lint/build, i18n parity |
```

Update the row when a review is re-run or extended; never delete rows.

## Small-batch template (one report, no fan-out)

Use the per-feature format above with the area set to the batch name. If the
batch is trivially small (a handful of commits on one surface) the sections
"Security review" and "Internal docs audit" may say "nothing in scope" — but
the header line, `## Commits analyzed`, the previous-findings table and the
`## What was actually run` table are never skipped.

## Steps

1. Find base and head (rule 3); `git log`/`git diff --stat` the range; group
   files by area; decide single report vs fan-out (rule 7).
2. Start the central checks in the background (tests, lint, builds, i18n
   parity) and launch the reviewers in one message.
3. Read the checks; classify lint failures (rule 6).
4. When the reviewers finish, write the index from their short summaries and
   the report files, including the verbatim commit list (rule 1).
5. Rule 9: README + QA_AGENTS rows, USER_TODO decisions, release notes, one
   commit. Then tell the owner the verdict, the Highs and what needs them.
