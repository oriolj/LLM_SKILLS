---
name: eod-report
description: End-of-day report mailed to Oriol (oriolj@gmail.com), one mail per project: what was implemented across every local repo that day, what changed for customers and the business, and what he must know as maintainer and developer (deploys and how they were verified, migrations, new env vars or credentials, unpushed or uncommitted work, USER_TODO and QA_PENDING additions, new rules in CLAUDE.md and skills). A project with several repos (EnaCast backend + Ramen + client sites, BikeCRM backend + frontend) gets ONE mail with a section per repo. Use when the user says "send me the end-of-day report", "EOD", "end of day summary", "what did we ship today", "mail me what was done today / yesterday", "daily report per project", or types /eod-report. Deterministic collection by scripts/collect.py (all repos under ~/git plus hq, fetches other machines' pushes, maps repos to projects through hq docs/projects.md, dedupes against the sent ledger); the agent writes and sends the prose and archives each mail in hq.
argument-hint: "[today | yesterday | YYYY-MM-DD] [project ...] [--dry-run] [--no-fetch]"
---

# /eod-report: what happened today, one mail per project

The reader is Oriol in three roles at once: the **business owner** (what
customers see, money, legal, decisions only he can take), the **maintainer**
(what is deployed, what is pending, what can break tonight) and the
**developer** (what changed in the code, which rules and gotchas are new). He
did not watch most sessions: several agents on several machines did the work.
The mail has to stand on its own.

Sending this mail is pre-authorized: "send ME an email" goes to
`oriolj@gmail.com`, in English, without asking (global rule). Nobody else ever
gets it from this skill; a team mail is a different ask.

## 1. Resolve the arguments

- **Day**: `today` (default), `yesterday` or `YYYY-MM-DD`, as a local
  calendar day (Europe/Madrid). Run before 05:00 with no day given, use
  `yesterday` and say so: an end-of-day report usually runs the next morning.
- **Project filters**: any other words keep only the mails whose name,
  project or repo contains them (`EnaCast`, `bikecrm`).
- `--dry-run`: write the bodies and show them, send nothing, write nothing
  to the ledger.
- `--no-fetch`: skip `git fetch` (offline, or a quick look). Without a fetch,
  commits pushed from other machines are invisible; the footer must say so.

## 2. Collect, never hand-assemble

```bash
S=<this skill's directory>   # the folder holding this SKILL.md; fallback ~/git/oriolj/LLM_SKILLS/skills/eod-report
python3 "$S/scripts/collect.py" --date <day> --fetch --out <scratchpad>/eod.json
python3 "$S/scripts/collect.py" --date <day> --format text      # the overview, for you and the user
```

(Use the same `--date` for both, and pass `--project` filters to both.) It
scans every repo under `~/git` to depth 4 (skipping `archived/`,
`node_modules`, other mounts) plus hq, and for each repo with commits or
uncommitted edits in the window it emits:

- `commits` on local and remote-tracking branches (so pushes made on other
  machines show up after the fetch), each with author, time, body, files,
  `pushed` (`None` when the repo has no remote, as hq does) and
  `already_reported` (the hash is in the sent ledger)
- `upstream` ahead/behind, `dirty_today` (uncommitted files touched in the
  window; an old dirty tree is not news), `worktrees` (worktrees share one
  object store and are merged into one entry)
- `flags`: the paths that matter even when the commit subject is quiet:
  `migrations`, `deploy_config`, `dependencies`, `env_settings`, `secrets`
  (paths only), `user_todo`, `qa_pending`, `deploy_docs`, `agent_rules`,
  `i18n`, `pricing_billing`, `legal`, `release_notes`, `tests`,
  `private_life` (hq's `oriolj/finances|recordings|crm|homebox`)
- `todo_changes`: the lines added to and removed from `USER_TODO.md` and
  `QA_PENDING.md` (at any depth): "waiting on you" and "what QA must test", for free
- `make_targets` among `prod-status`, `deploy-status`, `version`,
  `logs-prod-errors`, `error-traces`
- the mapping: `project` (the bold row name in hq
  [docs/projects.md](../../../../../Syncthing/Syncthing-mobile-docs/hq/docs/projects.md),
  matched by the repo's remote in the row's Code column, then by a sibling
  repo's name prefix), `family` and `in_projects_md`

Tell the user, in one short block, which mails you are about to write (the
`==` lines of the text overview) and any fetch failures. Then write them.
Do not stop to ask for confirmation.

## 3. One mail per project

**Grouping**: one mail per `mail` entry of the JSON. A `###` product family
in projects.md ("EnaCast — the radio platform", "EnaSuite — …") is ONE mail
with a section per repo; rows under a plain bucket heading (`## SmartupSoft`,
`### Other Enantena`) stay separate mails. Worktrees are already merged.

**Special cases**:

- **hq**: commits recording a project's state (`projects: Panotxa in Google
  Play review`, a server file updated for a deploy) go into THAT project's
  mail as maintainer facts, citing hq. The rest (estate, homelab, agents,
  skills index) is an "Estate (hq)" mail. `private_life` paths (finances,
  recordings, CRM, home inventory) are never summarized; put a single footer
  line with their count. Those topics get their own mails when Oriol asks.
- **Unmapped repos** (`in_projects_md: false`): still reported. Say in the
  maintainer section that the repo has no row in projects.md (a finding the
  global rules want fixed), and add the row in hq in the same turn when the
  project is obvious from the repo.
- **Nothing new** (every commit `already_reported`, no `dirty_today`): no mail.
- **A rerun the same day** with some new commits: subject `EOD update <date>
  — <Project>`, covering only the commits not yet reported, opening with one
  line pointing at the earlier mail's subject.

**Read before you write.** The commit subjects are not enough for a business
reader. Per mail:

1. Read each new commit's body (in the JSON) and, for the ones that matter,
   `git -C <repo> show --stat <hash>`. Read the diff only to answer a
   specific question; never paste it.
2. Read today's additions to the deploy ledger
   (`git -C <repo> log -p --since=… --until=… -- DEPLOY.md docs/09-deploy-and-ops.md`),
   to release notes and to the operations history, if the repo has one. They
   say what was deployed and how it was checked.
3. Use `todo_changes` as given: added `USER_TODO.md` lines are "waiting on
   you", removed ones are "done". Do the same for `QA_PENDING.md`.
4. When many commits are in play (more than ~40 in a mail, or more than 5
   mails), fork one subagent per mail, each writing its body file and
   returning only the path and a three-line TL;DR. The parent sends and
   archives.

**Deploy state needs evidence. Never promote "pushed" to "live".** Every
deploy claim carries one label:

- `committed, not pushed`: `pushed: false`, or the repo is ahead of its upstream
- `pushed`: pushed to the deploy branch. If that branch push-deploys, write
  "deploy triggered, health not verified"
- `deployed, verified`: name the evidence. One option is a ledger row today in
  DEPLOY.md saying how it was checked, with its commit. The other is a check
  you ran now: `make prod-status` / `make version` (read-only; run them for
  the repos pushed today that have the target, and quote the release SHA and
  health it reports)

A pushed commit is not a release, and a successful deploy job is not a
healthy app (global rule). If you cannot tell, write what you know and
"not verified by this report".

**Secrets**: never a credential value, never a hunk of a `secrets/`, `.env`
or `.enc` file. Name the credential (`OPENROUTER_API_KEY`, "RevenueCat v1
secret key") and say what changed: added, rotated, moved to production.

## 4. The mail

Subject: `EOD <YYYY-MM-DD> — <Project>: <the most important thing, in plain words>`
(for example `EOD 2026-10-03 — BikeCRM: approving an online rental now emails the customer`).

Plain text, English, no hard wrapping (Gmail and phones reflow), `-` bullets,
section titles in capitals. No commit hashes or jargon in the business
section; hashes belong in the maintainer section and the appendix. An empty
section says so in one line ("Nothing customer-facing today.") instead of
being padded or left out.

```
TL;DR
<three lines at most: what changed for users, what is live vs waiting, the one thing that needs Oriol>

FOR THE BUSINESS
- <user-visible change, who sees it, where (exact UI label), live or waiting for QA/deploy>
- <money: pricing, billing, LLM/infra cost changes with the figure if known>
- <customers, legal, public sites and docs, communications sent or due>
- Decisions waiting on you: <from USER_TODO additions that are decisions, with why it is blocked>

FOR THE MAINTAINER
Per repo (one block each when the project has several):
<repo> (<branch>): <N> commits, <pushed / N unpushed>, <deploy label + evidence>
- Migrations: <names, whether rehearsed, whether applied>
- Config: new or changed env vars BY NAME, credentials (names only), compose/Dockerfile/CI changes, new or bumped dependencies
- Incidents and risks: <outages recorded today, fragile spots, what to watch tonight>
- Waiting on you (USER_TODO): <added items, verbatim but trimmed>; done today: <removed items>
- For QA (QA_PENDING): <added entries, one line each>
- Uncommitted work: <repo, files touched today, which worktree>
- Housekeeping: <repo not in projects.md, worktrees behind their upstream, failed fetches>

FOR THE DEVELOPER
- <technical changes grouped by theme, not commit by commit>
- <new or changed rules: CLAUDE.md / AGENTS.md / skills, and what they now require>
- <gotchas learned today and where they were written down>
- <tests: only what a commit or ledger says was run, with counts; otherwise "no test run recorded">
- <follow-ups and known gaps>

COMMITS
<repo>
<hash> <HH:MM> <author> <subject>     (every new commit, the collector's order; mark unpushed with [unpushed]; name non-Oriol authors)

--
Window <start> to <end> (local). Collected on <host> at <UTC time>, fetch <yes|no>, <N> repos scanned.
Not visible here: uncommitted work on other machines, and branches never pushed from them.
<M private hq commits not summarized.>
Written by <model name and id>, <harness>, launched by <Oriol | a schedule>. Archive: hq/oriolj/eod-reports/<file>
```

Keep it scannable: a busy day (EnaCast had 104 commits on 2026-10-02) gets
5 to 8 business bullets grouped by feature, not 104 lines of prose; the
appendix carries the full list.

## 5. Send, then archive

The archive is [hq/oriolj/eod-reports/](../../../../../Syncthing/Syncthing-mobile-docs/hq/oriolj/eod-reports/README.md)
(hq is Syncthing-synced everywhere and git-tracked on minisforum only):

1. Write the body to `hq/oriolj/eod-reports/<YYYY-MM-DD>_<project-slug>.txt`
   (`_update-<HHMM>` suffix for a rerun). That file IS the sent body: do not
   edit it after sending.
2. `--dry-run` stops here: show the bodies, delete nothing, send nothing.
3. Send:
   ```bash
   oj-sendmail --to oriolj@gmail.com --subject "<subject>" --body-file <body file>
   ```
   Exit 0 prints `sent: id=<resend id>`. A non-zero exit is a failure: retry
   once on a network error, otherwise record it as failed. If the result is
   ambiguous (timeout after the request went out), do not resend blind. Say so
   and record it as ambiguous.
4. Add a row at the top of the archive README's table (UTC sent, To,
   Subject, body link + first 16 hex of its sha256, Resend id, status:
   "accepted by Resend (oj-sendmail)". Acceptance is not delivery). Then
   append one JSON line to `sent.jsonl`; the collector reads it to mark
   commits `already_reported`:
   ```json
   {"date":"2026-10-03","mail":"BikeCRM","subject":"…","sent_utc":"2026-10-03T21:58Z","to":"oriolj@gmail.com","body_file":"2026-10-03_bikecrm.txt","body_sha256_16":"…","resend_id":"…","status":"accepted","host":"minisforum-um880","commits":["<full hash>", "…"]}
   ```
   Record failed sends too (`"status":"failed"`, no `commits`) so they are
   retried, not marked as reported.
5. Commit hq: `make -C ~/Syncthing/Syncthing-mobile-docs/hq git-commit
   MSG="eod-reports: <date> (<N> mails)" FILES="oriolj/eod-reports"` (on
   another machine the target waits for Syncthing and commits on minisforum).
   Commit only those files: other sessions work in hq too.

## 6. Report back

One short block to the user: each mail's subject and status, the
mails skipped (nothing new) and why, fetch failures, and housekeeping findings
you fixed (a projects.md row added) or left (the remaining ones). Do not repeat
the mails' contents.

## Traps

- **Worktrees** (`bikecrm-backend`, `-master`, `-rental-review`) share commits;
  the collector merges them by git common dir. Do not count their commits
  twice, and say which worktree holds uncommitted work.
- **A commit's date is its committer date in the window**: a rebase or
  cherry-pick today brings older work into today's report. When the author
  date is days older, say "rebased today" instead of "written today".
- **Remote-tracking branches lag**: without `--fetch`, another machine's pushes
  are missing, and a fetch that failed (`fetch_failures`) leaves that repo
  partial. Name it.
- **hq has no remote**: `pushed: null` there is normal, not "unpushed".
- **Parallel sessions**: two sessions can run this at once. Read `sent.jsonl`
  again just before sending. A line for the same mail and date with the same
  commits means it went already: skip.
- Prior art: hq lists `projectreporter` (a 2025 cron tool for LLM-written,
  per-company change reports, never run). This skill replaces it for Oriol's
  own daily view.
