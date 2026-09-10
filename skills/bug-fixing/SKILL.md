---
name: bug-fixing
description: Bug-fixing workflow for any web app with a backend + frontend, whatever the source of the report (error tracker event, client email, QA finding, "X doesn't work") — reproduce BEFORE touching code (run both locally, walk the user's own path in a real browser via the Claude in Chrome extension, headless Playwright as fallback), classify the bug (should work but fails / must be refused but the user is never told why / pure noise), fix the mechanism across sibling code, re-walk the same path after the fix checking success / refusal-with-message / can't-go-stale, then close the loop (release notes, team email, i18n, monitoring, and this skill). Use for any bug-fix request.
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
- **Classify the bug before designing the fix** — the fix is different for each class:
  1. *The user should be able to do this and it fails* → make it work (an archived
     client's open sheet must still accept tasks).
  2. *The user must NOT be able to do this, but nothing told them why* (a bare
     `Exception` → 500, a silent revert, a blank page) → refuse with a translated
     message that says what to do instead ("close the sheets first", "assign the bike
     to a client"), a 4xx the frontend renders, never a 500. Sometimes one report
     hides both classes (deleting a client with open sheets = class 2; adding a task
     to a deleted client's sheet = class 1) — name each one.
  3. *Nothing is wrong for the user, only noise* (a metrics sidecar missing in an
     environment, a browser extension) → stop the noise at the mechanism (log a
     warning, filter at the SDK), never by resolving the issue and hoping.
  Write the class into the release note ("What happened" vs "Now") and the team
  email — the reader must learn whether a flow was unblocked or a refusal explained.
- **A QA report is a bug source like any other**: map each finding to a tracker issue when
  one exists (the timestamps + user agent pin it), and fix the mechanism behind several
  findings at once (one error renderer, one retry policy, one FormData serialisation)
  rather than each symptom on its page.

### When the report says "it did X by itself" / "nobody did this"
Field note (EnaCast, 2026-09-10): an episode "cut by nobody", "uploaded
directly", "already cut". Every symptom was a *deduction* by some layer, and
the real cause was a person: a radio user had saved a photo into a raw file
field of the Django admin from a phone. Before theorising about automation:
- **Read the action logs first**: Django `django_admin_log` (`LogEntry`
  by `object_id`: who, when, which fields), the web access log around the
  timestamps, file mtimes and the first bytes of the suspect file (`od -A x
  -t x1z | head`). Do it on the real row before reading code for causes.
- **Distrust assertive UI copy derived from an empty field** ("uploaded
  directly" = `audio_recorded_url == ""`). Trace the condition to the
  serializer and list every other state that yields the same value.
- **A derived artefact must never condemn its source**: when a pipeline
  flags something "unrecoverable", check *which* file it judged; a bad cut
  must not invalidate a fine original.
- **Uploads: extension, `accept` and `file.type` are all caller-supplied.**
  Sniff bytes on both sides; the client check is for the message, the
  server check is the guard (ramen `src/lib/fileSniff.ts`, backend
  `sniff_audio_signature`).
- **Automatic actions need provenance** (who/what/when) the day they ship,
  or the next report is "nobody did it".

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

**Headless Playwright fallback that worked (2026-09-07, extension not connected):** one
shared helper module in the session scratchpad (`pw-common.mjs`: launch chromium/webkit
from the frontend's `node_modules`, `addInitScript` that seeds the token in
`localStorage`, an API-response logger with ms offsets, a toast poller, a tiny
authenticated `fetch` wrapper) + one small script per path (`repro-<bug>.mjs`,
`verify-<bug>.mjs <mode> <id>`) that prints each API status, the toasts and the final
URL and saves a screenshot. State changes between steps (archive a client, reopen a
sheet) go through ORM one-liners in the wrapper shell, not through the UI. Real WebKit
for iOS-only reports: the same script inside `mcr.microsoft.com/playwright:v<ver>-noble`
with `--network host` and the repo mounted at the same absolute path. Before starting
a dev server, check whether another session already owns the port.

**"Phone asleep, then woken" bugs in headless Playwright (2026-09-10, Panotxa
analysis watcher):** CDP `Page.setWebLifecycleState {state:'frozen'}` is a
**no-op in headless Chromium** — timers kept firing and no `freeze` /
`visibilitychange` event reached the page, so a "frozen" run measures nothing.
What works is the signal the app actually consumes: `page.evaluate` that
redefines `document.hidden` / `document.visibilityState` (configurable
getters) and dispatches `visibilitychange` — Android Chrome sends exactly
that on screen off/on, and Capacitor's App web plugin turns it into
`appStateChange`. Model "Wi-Fi still reconnecting after wake" with a
`page.route` that aborts every API request plus `navigator.onLine` overridden
and `offline`/`online` events dispatched; **`page.unroute` needs the SAME
matcher and handler references** or the abort stays in place and every
"after" number reads as a failure. Measure wake → DOM-marker-gone with a
25 ms poll and log every request with an offset from the wake instant — the
first request after wake tells you whether the code re-checked or waited for
a timer. Run the same script against the pre-fix bundle (a copy of `dist/`
served on another port) for the before numbers.

**Not reproducible after a bounded, honest attempt** (both engines, the user's device
class emulated, every gesture sequence the code path admits, the third-party source
read for the null path): say so, ship NO speculative fix, leave the tracker issue open,
and write the sequences tried + the code facts into the companion skill so the next
attempt starts further along. A guard added "just in case" hides the next real event.

- **Never type a password into a login form.** Obtain a token/session through the API
  with the repo's documented test credentials and inject it the way the app stores it
  (`localStorage` / cookie) via the JS tool, then reload.
- Material/headless-UI selects: click the combobox, then `find` the open listbox and
  click the option by **ref** — coordinates shift as the page re-layouts while data loads.
- Inline/contenteditable cells: a coordinate click may not enter edit mode; verify with
  a zoom before typing (a stray `ctrl+a` selects the whole page). When the UI path is
  flaky, drive the component itself in dev mode (`ng.getComponent(el).method()`) — it
  exercises the same wiring (emitters → parent handler → toast) deterministically.
- Toasts are short-lived and the toast container may be recreated per toast: read
  `#toast-container` within ~1 s of the action (poll in the same JS call); a
  MutationObserver on the old container misses them.
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
  wording on the frontend); ask whether public release notes deserve an entry. Each
  bug entry gets a **3–5 word name** in bold, then *How you hit it* (the exact clicks),
  *What happened* (what the user saw — often "nothing"), and *Now* (the new behaviour).
  A reader who never saw the bug should be able to reproduce the old path from it.
- UX question, every time: *did the user have any way of knowing?* If the failure was
  silent, add the toast/error/banner and the i18n keys in **all** supported languages.
- If production is monitored for that flow (synthetic smoke tests), update the suite.
- Run a cleanup review (`/simplify`) on the fix and *apply* the "this belongs in the
  shared service/base class" findings — a page-level special case usually means every
  other caller has the same gap. Then `/code-review --fix`: each round on this kind of
  fix found real gaps (an exception type change that turned a 400 into a 500, probes
  on a manager that hides rows). A review agent may stop mid-verification without a
  final report — check `git status` for its uncommitted edits and verify them yourself.
- **Sibling scan the MECHANISM, not the symptom**, once the fix is in: grep for the
  pattern (hand-rolled `__init__` trackers, per-tenant uniqueness probes against a
  global unique, `isNaN` on user text…) across every model/component. Write a tiny test
  per candidate on the pre-fix code: some are real (deferred recursion in a second
  tracker), some are false alarms (a filtering manager that isn't the default) — the
  test settles it in seconds and documents the scan for the next person.
- External QA reports: triage each item against `git log` first — half were already
  fixed by a concurrent review round; the rest (non-finite numbers passing `isNaN`, a
  success toast for a no-op path added later) were real and cheap.
- Pushing: a `Permission denied (publickey)` line can come from a first key attempt
  while the push still lands — confirm with `git ls-remote origin <branch>` vs
  `git rev-parse HEAD` before reporting a failed push.
- **Tell the team by email** once the fix is deployed somewhere they can try it (the
  project's `CLAUDE.md` names the CLI, the recipients, the sender and the language).
  One section per bug: *how the user hit it* (the exact clicks), *what they saw*,
  *what happens now* (quote the new UI text verbatim from the catalog), *how to test
  it* (environment + steps), and *what is NOT fixed / not reproduced* — the team must
  not discover an open item from the tracker. Send after the re-walk, never before.
- **Update this skill and the project's companion skill in the same turn** — a repro
  trick, a landmine, a test-account change, an investigation that ended "not
  reproduced" — and refresh the pointer to both in every repo's `CLAUDE.md` when the
  loop changes. The next bug is faster only if the write-up exists; a session can end
  at any moment.
