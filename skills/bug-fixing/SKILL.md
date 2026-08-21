---
name: bug-fixing
description: Bug-fixing workflow for any web app with a backend + frontend — reproduce BEFORE touching code (run both locally, walk the user's own path in a real browser via the Claude in Chrome extension, Playwright as fallback), read Sentry events for the payload and the user's click, suspect masked bugs and stale UI, fix the mechanism across sibling code, re-walk the same path after the fix checking success / refusal-with-message / can't-go-stale, then close the loop (release notes, UX feedback, i18n, monitoring). Use when handed a Sentry/error-tracker event, a client bug report, a failing production flow, or any "X doesn't work" request.
---

# Bug fixing — reproduce, fix, re-walk the user's path

A fix is not done when the traceback disappears. It's done when the **user's path**
works end-to-end on the dev machine, the user is **told** what happened when it can't,
and the change is **recorded** where people will look for it. Project-specific
commands (how to start the stack, test accounts, routes) belong in a per-repo companion
skill; this file is the method.

## 0. Read the report properly

- **Error-tracker event (Sentry) JSON**, the parts that matter: `request.data` (the exact
  payload the user sent), `transaction` + `request.method`, the `in_app: true` frames and
  their `vars` (object reprs: which record, which value), and the `breadcrumbs` (the SQL
  or HTTP right before the crash — the *same query repeated* is a loop). `release` is
  usually the deployed git SHA: `git log <sha>` tells you what code was live.
- Ask **"what did the user click to send this?"** before reading code. If the UI is
  supposed to prevent that action (disabled button/selector/guard), assume **stale UI**
  until proven otherwise: the backend changed state behind the page's back (a server-side
  automation, another tab, a webhook) and the page never re-read it.
- Suspect a **masked bug**: a crash inside shared infrastructure (an ORM collector, a
  serializer, a model `__init__`, a middleware) often hides the real failure underneath.
  After fixing the crash, run the flow again and look at what fails *next* — the real
  bug may have been there for months.
- Check whether **sibling code** shares the pattern (three models with copy-pasted
  methods, three handlers with the same tracker). Fix them all or you'll be back.

## 1. Reproduce BEFORE changing code

### Run the real stack locally
Backend and frontend on the dev machine, pointed at each other, with hot reload. Read
the backend log for the real status codes — the UI may swallow them. If the bug involves
an integration (e-commerce store, payment provider, SMTP, a webhook source), **spin up
that service locally too** (a docker WooCommerce/Shopify dev store, MailHog/Mailpit, a
Stripe CLI listener…) rather than reproducing against a client's live account.

If the local DB is a production copy: never touch client rows; create dedicated test
records on a designated test tenant from a shell snippet.

### Walk the user's path in a real browser
Use the **Claude in Chrome extension** (`claude-in-chrome` skill →
`mcp__claude-in-chrome__*` tools). Fallback when the extension misbehaves or the flow
needs scripting: the project's **Playwright** setup (`playwright` CLI / the repo's e2e
target).

- **Never type a password into a login form.** Obtain a token/session through the API
  with the repo's documented test credentials and inject it the way the app stores it
  (`localStorage` / cookie) via the JS tool, then reload.
- Material/headless-UI selects: click the combobox, then `find` the open listbox and
  click the option by **ref** — coordinates shift as the page re-layouts while data loads.
- `read_network_requests` only records from its first call — call it (with `clear`)
  *before* the action you want to inspect. Pair it with the backend log.
- Check whether detail pages **poll** or re-fetch on component events before calling
  repeated GETs "polling" (read the network log); a stale-UI repro must inject the
  server-side change *after* the page loaded, then act quickly — or you'll be testing a
  refreshed page.
- To show the *original* failure after you've already fixed it: temporarily put the
  files back (`git stash` WIP, `git checkout <pre-fix-sha> -- <files>` in each repo),
  walk the path, then restore (`git checkout HEAD -- <files>`, `git stash pop`). Both
  dev servers hot-reload. Keep the evidence: screenshot, log line, DB state.

## 2. Fix

- Load the project's guardrail docs/skills for the area first (legal/financial
  invariants, sync invariants) — a correct-looking fix can still corrupt records.
- Fix the **mechanism**, not the symptom; apply it to the sibling code found in step 0.
- Add a regression test that encodes the **user path** (the API call with the real
  payload), not only the unit that crashed. Prefer minimal fixtures over big
  parametrized fan-outs — they're faster and they don't trip fixture-teardown landmines.
- Compare the related test suites against a **baseline** (a worktree at the pre-fix
  commit) and diff the FAILED *sets* — raw counts lie when a suite has pre-existing
  failures.

## 3. Re-walk the user's path (after)

Same browser path, fixed code. Verify all three outcomes, not only the happy one:
1. the action **succeeds** and the UI reflects the real server state (toast with the
   result when the action is consequential — e.g. "invoice reissued as X");
2. the action is **refused** and the user is *told why* — a 4xx with a translatable
   message the frontend renders, never a silent 200 that reverts the value;
3. the UI **cannot get stale** into the dangerous state — re-read the fields an action
   depends on after the events that change them server-side (payments, closes, syncs).

Then confirm in the DB — the UI can lie in both directions.

## 4. Close the loop

- Release notes in **every** repo you touched (technical on the backend, user-facing
  wording on the frontend); ask whether public release notes deserve an entry.
- UX question, every time: *did the user have any way of knowing?* If the failure was
  silent, add the toast/error/banner and the i18n keys in **all** supported languages.
- If production is monitored for that flow (synthetic smoke tests), update the suite.
- Run a cleanup review (`/simplify`) on the fix and *apply* the "this belongs in the
  shared service/base class" findings — a page-level special case usually means every
  other caller has the same gap.
- Pushing: a `Permission denied (publickey)` line can come from a first key attempt
  while the push still lands — confirm with `git ls-remote origin <branch>` vs
  `git rev-parse HEAD` before reporting a failed push.
- Write down what you learned that wasn't obvious (a landmine, a repro trick) in the
  project's companion skill or testing docs — the next bug will be faster.
