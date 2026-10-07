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

### Which build is the report from?
- Map the report's release/version to a branch and a commit BEFORE deciding where the
  fix goes (`git branch --contains <sha>`). Production and the integration branch can
  be months apart: a tracker issue that flips to *regressed* may simply be the
  environment that never received the fix — say so instead of re-fixing, and put the
  "how do the fixes reach prod" decision in `USER_TODO.md`.
- A `ModuleNotFoundError` / `ImportError` raised inside a **third-party** frame is a
  packaging bug (lockfile relock dropped a transitive dependency, image built from a
  stale lock), not application code. Diff the lockfile between the deployed commit and
  the fix branch; check the package's declared runtime deps on the registry; restore
  the entry (or relock) and **verify by building the image** the same way the deploy
  does. Then still make the feature degrade if it is optional — a suggestion helper
  must never take the form down with it. If a later unrelated relock drops the same
  required package again, declare it explicitly instead of relying on another
  manual lock repair. Add dependency-consistency and critical SDK import checks
  after installation in the image build. Tests in an existing container do not
  validate the new lock or image.
- The container you run tests in may not be the container serving the app you click
  through: a shared image tag rebuilt by another checkout, a long-running dev server
  started from an older image. Check the failing import in BOTH before concluding
  "cannot reproduce locally" — the test image reproduced a prod bug the dev server
  could not.

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

- For N+1 reports, measure query growth with a small and larger fixture set before
  editing the view; hold cache state constant and distinguish the offending table
  from unrelated queries. A read optimization also needs unchanged response values
  and stored-row snapshots (including financial denorms/ledger balances where relevant).
  With generic relations, preserve explicit tenant/workshop filters and test the
  same object ID under two content types; an unscoped prefetch can silently change totals.
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

For customer-facing automations (a WhatsApp button, an email reply bot), "refused with
a message" means the **customer gets a text back**, never silence: resolve by identity
only when it is unambiguous (one tenant owns every recent conversation with that
phone), otherwise tell them what to do, in the language they were last written in — and
keep the alarm so unresolved cases stay visible.

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

### CPU alerts: separate execution, planning and request lifetime (2026-09-14)

- Read the alert's actual resource and evaluation interval first: a managed-DB
  CPU alert cannot be reconciled using application-host CPU alone.
- When DB spans are slow but statement execution metrics look cheap, inspect
  local `EXPLAIN (ANALYZE, BUFFERS)` planning time. Many joins, including
  inherited-model tables, can cost much more to plan than to execute.
- Reproduce polling leaks through repeated SPA navigation and a virtual clock.
  Reloading the browser destroys every subscription and hides the failure.
  Assert both that active views refresh and that destroyed views stop.
- Query-plan changes may reorder rows with equal sort keys. Compare full
  payloads using a deterministic secondary key or compare tied groups; don't
  mistake an unspecified tie order for changed row data.

### Identity upserts and writable metadata (2026-09-15)

- A successful external upsert is not identity proof. Reproduce the case where the
  stable external key is missing but an email matches an archived/former user.
  Prefer explicit create or update by a verified record ID, including background
  provisioning paths; a lookup followed by email-upsert still has a race.
- If a guard requires stored bindings, test accounts that predate the binding
  migration. Supply an adoption procedure backed by independently verified IDs;
  editable slugs or emails cannot serve as ownership evidence.
- Treat arbitrary JSON metadata as user-controlled when its serializer is writable.
  A revocation/grant ledger belongs in server-owned state. Test API replacement of
  the JSON followed by the actual expiry task, with pre-existing paid features.

- A local user table may include customer contacts as well as employees. Before a
  production identity adoption, check active/unarchived state, tenant and actual
  staff/owner role as well as historical identity evidence. Name/email agreement
  does not establish that the account can hold the intended role. If verification
  disproves a mapping, reverse the scoped change immediately, preserve its audit
  history, and record whether any session or data access occurred.
- Before adding a security ledger column, test mixed old/new processes and inserts
  during rolling deployments. Protecting a reserved JSON key at the API boundary
  can preserve the existing storage contract; reload under a row lock to prevent
  stale serializers from restoring an older ledger.


### Public signup capacity and bot rejection (2026-09-15)

- A rate-cap alert can be caused by gate ordering: replay rejected bot requests
  followed by a legitimate form submission before raising the cap. Separate
  admission quotas from request-abuse controls; rejected forms must not consume
  admission quota or reserve another applicant's email throttle.
- When verified captcha permits overflow past a shared cap, represent provider
  verification separately from disabled configuration. A caller-supplied token
  or a truthy non-boolean provider response is not successful verification.
- A shadow success response proves nothing about persistence: assert the pending
  signup and verification email for the real applicant, and neither for bots.
- When changing an existing counter's meaning, use a new namespace or a scoped
  transition plan. Already polluted counters otherwise survive the code fix;
  document that a fresh namespace grants existing users a fresh quota window.
- Before a live negative signup smoke test, verify provider configuration in that
  environment without exposing its secret. A missing-token request may create a
  real signup when no provider is configured; use a guaranteed rejection instead.
  Check persistence separately from HTTP status and record environment differences.

### Template responses and HTMX validation (2026-09-16)

- A `TemplateView.get_context_data()` method must return a dictionary. Returning
  an HTTP error response there masks a missing object with a template-rendering
  500. Resolve the object and return any branded error response at the view boundary.
- HTMX may send a request before a jQuery `submit` guard runs. Cancel its
  `htmx:beforeRequest` event for client validation and keep server validation.
  For server 4xx feedback, scope `htmx:beforeSwap` handling to the intended error
  target; HTMX does not swap error responses by default. Verify visible feedback,
  retained form values, no duplicate alerts, and clearing after a valid selection.


### Cold startup and failed polling (2026-09-16)

- Capture both browser `pageerror` and console errors. Framework error handlers
  can consume exceptions before Playwright emits `pageerror`; a visible control
  does not prove its surrounding form initialized. Reproduce with an empty
  application cache and delayed account/profile responses, then assert actual
  form values, save/refusal feedback, draft retention and teardown.
- For failures after a sleeping tab resumes, inspect the shipped service worker:
  it may synthesize HTTP 504 when fetch rejects. Compare request duration and
  simultaneous endpoint failures with server logs before blaming database latency.
- Verify recovery after restoring connectivity, not just the first failure:
  an RxJS error can terminate the outer polling subscription permanently.
  Keep retry inside the read mechanism, bound its backoff, avoid overlapping wake
  and timer requests, cancel listeners on unsubscribe, and show stale-data feedback.
- Provider rejection tests must assert persisted business state and every channel
  outcome. An absent secondary channel is not a successful delivery. A sender
  formatting fix does not resolve provider registration or destination permissions;
  document that operational boundary explicitly and never send a customer probe.

### Provider policy failures and partial notification success (2026-09-16)

- Read the provider's exact numeric error and current destination policy before
  fixing sender/input syntax. Syntactically valid identifiers may require prior
  registration; a code fix cannot grant account permissions. Search excerpts do
  not prove a policy's effective date when the opened primary page omits it.
- Reproduce the real notification button AND automatic failed-delivery callback
  with the provider mocked. An HTTP 200 plus a success toast may accompany a
  failed provider result and a wrongly persisted notification flag. Verify all
  three: response, visible feedback and database state.
- Give send helpers an explicit acceptance contract; swallowed exceptions and
  implicit `None` must not become success. Preserve sanitized diagnostics for
  sibling callers when introducing a return value. Test total failure, one-channel
  acceptance and full acceptance; partial success deserves explicit feedback.
- Classify known permanent provider-policy failures separately from throttling,
  transport errors and provider 5xx. Acknowledge permanent callback failures once
  while preserving the diagnostic; retain transient retry semantics. Never try a
  second sender after an ambiguous acceptance, or test through customer messages.

### Layout bugs: measure the scale, then verify with numbers (2026-09-17, Ramen schedules grid)

- A "column X is not aligned with element Y" report is almost always two
  scales: one thing sized in px, the other in percent of a DIFFERENT box.
  Check what `absolute inset-0` resolves against — inside a container with
  `overflow: auto` + `max-height`, it is the visible viewport, not the
  scrollable content. Derive every vertical value from ONE constant in a
  pure module, unit-test the invariant "label offset === block offset for
  the same minute", then read the DOM: `style.top` of the block wrapper vs
  the hour label (the fix was accepted when both printed 1248px).
- Remote Chrome (the extension runs on another machine): `localhost` and
  `*.localhost` show an error page and `localStorage` throws. Use a host
  already listed in `next.config.ts` `allowedDevOrigins` (Ramen:
  `http://minisforum-um880:3203`); other hostnames load but Next blocks its
  own chunks and the app never hydrates ("Loading…" forever, no console
  error). Inject the API token with the JS tool on that origin.
- A local backend that answers 500 `Unknown column …` on `/get_user/` is
  behind on migrations from a sibling session's branch: `make migrate` in
  the backend repo, then retry — not a Ramen bug.
- Another session may be editing the same repo. `git status` before AND
  after subagents run; commit only your hunks (for JSON catalogs and
  release notes, build the staged blob as HEAD + your block and
  `git update-index --cacheinfo` it) and leave the rest in the tree.
- Native `<select>` + React: the `find` tool cannot pick an option and
  Enter submits the form (useful: it proved the "select a program" refusal).
  Set the value with the prototype setter + a bubbling `change` event.

### Upload sniffs: a container header is not the codec (2026-09-18, EnaCast XFrame MP3)

- A client's "valid MP3 refused since the validation change" was a RIFF/WAVE
  file whose `fmt ` chunk declared MPEG layer III (`wFormatTag 0x0055`):
  radio automation (XFrame) exports MP3 that way, and a sniff that refuses
  every `RIFF` header (right for WebP/AVI/PCM wav) refused it. Sniff the
  container AND the codec tag inside it; keep the refusal for PCM wav.
- Check BOTH sides before blaming the server: here the backend accepted the
  file all along (mutagen finds frames behind the 44-byte header) and only
  the browser-side check refused it; the server half of the fix was
  canonicalising the stored file (`ffmpeg -c:a copy`, no re-encode) before
  ID3 tagging, because tags were being written in front of a RIFF header.
- Build the fixture with ffmpeg instead of asking for the client's file:
  `ffmpeg -f lavfi -i sine=frequency=440:duration=3 -c:a libmp3lame -b:a 256k -f wav x.mp3`
  reproduces the header byte-for-byte (`od -A x -t x1z | head`), and
  `ffprobe -show_entries stream=codec_name:format=format_name` confirms
  `mp3` inside `wav`.
- A "local" dev server can proxy PRODUCTION (ramen's `.env.local` pointed
  `ENACAST_API_URL` at enacast.com): a re-walk that submits creates a real
  row. Read the env before submitting, use the designated test tenant only,
  and delete the row afterwards (the create's 201 on prod was still useful
  evidence that the server accepted the file). Before/after with `git stash`
  of the fixed files while the dev server hot-reloads worked as described
  above; the pre-fix run printed the exact refusal text from the catalog.

### Cleared inputs that never reach the form (2026-09-18, Ramen schedule validity dates)

- "Emptying the field does nothing on save" + "the form refuses for a value
  I can't see" are one mechanism: a wrapped widget that only forwards
  non-empty selections. flatpickr fires `onChange([])` on Backspace/Delete,
  and a `set('minDate'|'maxDate')` that excludes the current date **filters
  `selectedDates` and blanks the input without firing `onChange` at all**.
  Compare `input.value` with what the PATCH body carries — the repro was
  "input shows '', body carries the old date, backend 200".
- Repro the three paths, not one: clear; modify via the calendar (was fine);
  move the start past the end (the bound-drop path). The last one showed an
  error banner my generic selector missed — read the after-save screenshot
  before calling a path "no error".
- Headless Playwright when the package wants a browser build that is not
  cached (`Executable doesn't exist at …chromium_headless_shell-NNNN`): do
  not `npx playwright install`; pass `executablePath` pointing at an existing
  `~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell`.
- Ramen's UI language follows the test radio (radiotest = Spanish): locate by
  the `es` catalog strings, and the schedule list prints dates `en-US`
  ("Sep 1, 2026"), not `dd/mm/yyyy`. The running dev server on :3203 was
  local-backed (`/proc/<pid>/environ`) even though `.env.local` names prod.

### "The editor ignores my setting" can be the renderer's sanitiser (2026-09-18, EnaCast news links)

- Report: "open in new tab" ignored + `www.google.com` opens as a relative
  URL. Walk the editor in the browser and read the DOM it produces BEFORE
  touching it: the ramen editor already emitted `target="_blank"
  rel="noopener noreferrer"`; the attribute died in the public site's
  `DOMPurify.sanitize()` (default allow-list has no `target`). Every
  `set:html` body goes through a sanitiser — grep for it in the renderer
  repo whenever an attribute "does not survive publishing". Fix with one
  shared policy module (`ADD_ATTR: ['target']` + an
  `afterSanitizeAttributes` hook forcing `rel`), and check the sibling
  renderers (episode descriptions had the same gap). Also check what the
  config actually adds: `ADD_TAGS: ['audio','source']` was dead — already
  in DOMPurify's defaults; a 3-line node one-liner against the installed
  package settles it.
- The href half was the editor's: a relative href needs normalising at
  insert time (`src/lib/linkHref.ts`), not on the site.
- Headless walk against the running ramen dev server: the login form is
  on `/` (not `/signin`), the toolbar language followed the account
  (Catalan for `oriol.radiotest` here — list `button` texts first, then
  pick labels from that catalog). Reading the `.ProseMirror a` attributes
  after "Inserir enllaç" gives before/after evidence without saving, so
  nothing lands on production through the :3203 proxy.

### QA batch fixed by parallel agents on a machine without the stack (2026-10-04, BikeCRM)

- **Check free disk before bootstrapping a stack** (`df -h` on the data volume): image build +
  `node_modules` + test-runner caches filled a Mac to 100 % and Docker Desktop crashed mid-run,
  taking every agent's local backend with it. Pause the agents (no docker/test builds) before
  freeing space; ask before deleting anything that is not a regenerable cache you created.
- **Read-only production-data fallback:** the local frontend with a browser-level route that
  forwards GETs to the production API and aborts every other method. It lets a frontend fix be
  walked on real data while the local backend is down; label it as such, never as production.
- **"Search from page 2 shows an error"** = the search did not reset the page and the API
  refuses the out-of-range page (DRF: 404 «Invalid page», localised body — key on the status).
  Fix in the shared list base: reset page on every query change and recover a stale page to 1;
  never leave the previous query's total next to the retry state.
- **"Search does nothing"** on a DRF list = no `SearchFilter`, or `SearchFilter` without
  `search_fields` (both silent). Scan every viewset the frontend sends `search` to.
- **A pager reading 0 under visible rows** = a `@ViewChild` under a structural `*ngIf`, bound once
  in `ngAfterViewInit`; use a setter. Then check whether the page client-pages only API page 1.
- One agent per finding with disjoint file ownership in the shared checkout (no worktrees when
  branches are forbidden), the lead owning catalogs, docs and every commit, worked; scope
  creep from an agent (a history-behaviour change on every list) was reverted and recorded.

### "The totals are right but lines are missing" — silent template gaps (2026-10-05, BikeCRM invoice book)

- **Template engines swallow missing attributes** (Django renders `{{ obj.nope }}` and
  `{% for x in obj.nope.all %}` as empty, Jinja's default `Undefined` too). A document whose
  totals come from stored/denormalised fields keeps adding up while whole line kinds are
  missing — nobody notices until a client compares two documents. When one document is
  "right" and another "wrong", diff the TEMPLATES line kind by line kind (here: the shared
  invoice partial looped tasks but never products; its rental loop read accessors that did
  not exist; a header tested a field that did not exist).
- **Enumerate the line kinds from the models first** (every relation the totals sum over),
  then check every renderer, export and legal serialiser against that list — the same scan
  found the e-invoice XML skipping one kind's surcharge through `hasattr(obj, "get_items")`
  duck-typing. A line kind in the totals but not in the output is the bug pattern.
- **A shared include must not read view-only context**: one caller passed a flag, the other
  (the PDF book) never did, so a column silently never appeared there. Derive it inside the
  include from the object it is given.
- **Tests assert rendered line names AND per-line amounts**, through the real user path
  (the API call that triggers the PDF, capturing the HTML handed to the PDF engine), not a
  200. Pair it with a query-count test when the fix starts rendering more relations in a
  bulk document (a quarter of invoices ⇒ N+1 per invoice AND per line otherwise).
- **"I never received the emailed report"** — read where the code sends it before touching
  configuration: the tester changed the shop's address, the report goes to the requesting
  user's login email; the production log line `… sent to <address>` settled it.

### Outage status codes: reproduce with a fake failing backend (2026-10-06, EnaCast astro)

- Symptom: during an origin/backend overload, uncached SSR pages answered **404** (Googlebot
  included); the class is "should work but fails, and the failure is disguised as not-found".
  Seen live with `curl -A <UA> https://host/?probe=$RANDOM` (a random query bypasses the CDN):
  the same 404 for a browser UA ruled out the bot rules.
- **Reproduce with a fake upstream, not by breaking production:** a ~40-line Python
  `ThreadingHTTPServer` on localhost that proxies GETs to the production API (read-only,
  POST/PUT/DELETE refused) and answers 503 for the API path prefixes listed in a `fail.txt`
  (`ALL` = everything). Point the dev server's `API_BASE_URL` at it with Redis unset, then a
  probe script prints status / `Location` / `Retry-After` / CDN header for a fixed URL set in
  three modes: healthy, content endpoints failing (tenant lookup still OK), everything failing.
  Editing `fail.txt` switches modes without restarts. The before table is the bug report.
- Probe more than pages: feeds (count `<item>`), sitemaps (count `<loc>`), `llms.txt`, legacy
  redirect routes, embeds, a custom-domain Host and an unknown Host, and the healthy run after
  every change (an unknown host must still get its old answer).
- Astro 7 `astro dev` refuses a second server per checkout (lockfile) and auto-backgrounds for
  agents: use a `git worktree add --detach` with `node_modules` symlinked from the main
  checkout, `astro dev stop` there when done. Vite's `server.allowedHosts` in the project config
  answers 403 to other Host headers (`--allowed-hosts` does not override it): pick a host on the
  list for "unknown domain" probes.
- The fix belongs in the shared mechanism (the middleware + the request failure record), with a
  per-page helper only where the page alone knows its main content (a list). Rule and design:
  the seo skill, "Edge / middleware pitfalls" 6.


### "Nothing gets transcribed for this client" can be a sync that judged the source deleted (2026-10-06, EnaCast Montmeló)

- Report: one radio's episodes all "stuck" in ramen, no transcript for three months. Follow the episode
  through BOTH databases before reading code: the backend row was pending, the AI service had transcribed
  and analysed it, and its sync error said the source answered 404 and the episode was "deleted at source".
  The break was in the hand-back, not in the processing the report blamed.
- **An anonymous read is not an existence check.** The sync's GET carried no token; a scheduled (not yet
  published) episode answers 404 to the public, the same answer as a deletion, and a terminal flag made it
  permanent. Prove it with the same URL anonymous vs authenticated (404 vs 200). Only live-recording radios
  were spared, because their episodes are public the moment they exist: when one client class is hit and
  another is not, ask what is different about *when* their objects become public.
- Fix in the shared mechanism: one header helper used by every outbound call (the retry helper included),
  and a "deleted" verdict only from an authenticated 404. Measure that authenticating the polling calls does
  not change what they return before shipping it (same counts both ways here).
- **Repair after the fix, scoped by the source of truth:** for every flagged row an authenticated read first;
  re-sync only where it is 200 AND the target has no result yet (never overwrite), dry run → evidence file →
  apply. Look for older victims under a different signature: before an earlier "fail loudly" change the same
  404 returned silently with an EMPTY error, so filtering on the error text missed half of them.
- Rows on channels disabled today are a client decision (a radio may have opted out), not a re-sync default.

### "I set it in the editor, it does nothing on the site" — read the STORED body first (2026-10-07, EnaCast linked image)

- Fetch the stored content from the API before reading either repo: the custom page body had no `<a>` at all, which
  put the first gap in the editor, not the renderer. Then render a body that DOES have the feature (the old admin's
  `<a href><img></a>`, 501 pages in the DB copy) through the public site in a real browser: that exposed the second
  gap (the renderer lifted `<img>` into a zoom island and left an empty anchor; Chrome re-parented it, so the click
  opened the link AND the zoom).
- **ProseMirror/TipTap: a mark cannot sit on a block atom.** `setLink` on a NodeSelection of a block image node
  applies to nothing, returns, and the dialog closes as if it worked; and on load, an `<a>` around such a node is
  dropped, so **opening and saving a legacy body silently deletes data**. Count how much legacy content carries the
  construct (regex over the local DB copy) before sizing the fix. Fix: node attributes (`href`/`target`) parsed from
  `img.closest('a[href]')`, rendered as `figure > a > img`, and the toolbar dialog branching on
  `selection instanceof NodeSelection`. Node attributes skip the mark's URI check: allow-list schemes yourself.
- Editor walks without a jsdom: `document.querySelector('.ProseMirror').editor` is the TipTap v2 instance —
  `commands.setContent(html)` + `getHTML()` is a load→save round trip, `commands.setNodeSelection(pos)` selects a
  node, then click the real toolbar. Run the dev server against the LOCAL backend on a spare port so nothing can
  write to production; check `/proc/<pid>/cwd` of whatever already listens on a port before trusting its render.
- Unit tests that `ts.transpileModule` a helper into a `vm` context (enacast-astro) compile to ES5: `for…of` over
  `matchAll()` silently iterates nothing there. Use `Array.from(...)`, and compare vm-realm arrays via JSON.

### "The filter doesn't work" can be an empty result with a generic message (2026-10-07, H2A Accountant chips)

- Before reading the frontend, ask production how many rows the filter selects: with the agent API token,
  `GET /api/v1/invoices?direction=purchase&status=scanned` answered `count: 0` and the dashboard queue agreed
  (`to_review: 0`). Then fetch the deployed page chunk (`curl` the page HTML → its `/_next/static/chunks/app/…/page-*.js`,
  grep the chip table) to prove prod runs the code you are reading. The chip worked; the empty state said
  "No invoices match these filters — widen the dates", which reads as broken. Class 3 for the filter, class 2 for the copy.
- Fix: counts on the chips (from the same aggregate the dashboard uses) and an empty state that names the chip
  ("Nothing to review — you're caught up"). A count shown next to a list must equal that list's count: write ONE test
  that walks every chip, compares `queue[key]` with the list count, and seeds rows that must count in neither
  (here sale rows were in three dashboard counts but never in the purchase lists the counts linked to).
- django-filter silently ignores an unknown query param, so a frontend that ships a new filter before the backend
  returns the whole list. Deploy the backend first; that same behaviour makes a nice deploy probe
  (`?awaiting_upload=true` count drops from "everything" to the real number once the new code is live).
- Playwright: after a click that `router.replace`s the URL, `waitForLoadState("networkidle")` returns at once;
  a second click lands before the URL changed and filters stack. Wait for the URL (or reload per case) between clicks.

### Detail page acting on a state a background task already changed (2026-10-07, same app)

- "It says To review but Approve says it's uploaded": the page polled while `scanning` and stopped at `scanned`,
  exactly when the post-scan tasks start (duplicate check adopts the platform document → `uploaded`). Read the row's
  timestamps on prod (`created_at`, `uploaded_at`, `status_detail`) to see the task's footprint 50 s after the scan.
- Fix the mechanism in three places: poll fast for a window after the state that starts follow-up tasks (from the row's
  own `scanned_at`), poll slowly while the page is open, and re-read the row in the shared action runner's `catch`
  (a refusal usually means the row changed). The 400 body explains the refusal in the user's terms per state.
- Repro without the task: open the page headless, then flip the row from a `manage.py shell -c` one-liner (the
  "task" behind the page), click Approve, log the POST body + the follow-up GET; second run with `scanned_at=now()`
  and no click proves the page flips by itself. Restore the row at the end of the script.

### "A link goes to a 404" can be a missing feature with a security surface (2026-10-07, EnaCast password reset)

- Ramen's «Has oblidat la contrasenya?» pointed at a route that never existed; the only reset lived in a legacy
  admin about to be switched off. Before building, list every OTHER path that already does the job: Django's
  `django.contrib.auth.urls` was mounted under a legacy prefix (`/admin-v2/password_reset/`), live in production,
  unthrottled, token in the URL path. Removing it was part of the fix.
- Self-service reset changes the threat model of neighbouring endpoints: an email change without the current
  password turns a stolen API token into a permanent takeover once reset exists. Review the account-update paths
  in the same change.
- Patterns that held up under three reviews: token in the URL FRAGMENT (never reaches logs, proxies, analytics),
  minted inside the mail task; one task per request whatever the lookup finds (no timing enumeration); caps per
  normalised email (NFKC + casefold, hashed) AND per account; re-check the token on a `select_for_update` row after
  slow validators; the API returns the policy (`min_length`, `expires_minutes`) so the frontend holds no copy.
- Per-IP throttles behind a frontend proxy (Vercel → backend) key on the proxy's egress IP: shared by every user.
- Sentry: `beforeSend`/`beforeBreadcrumb` do NOT reach Session Replay (it records `location.href` with the hash at
  init) nor the server SDK's captured request bodies: scrub bodies of credential endpoints, skip Replay on routes
  whose URL carries a secret. Next 16's Turbopack build ignores `sentry.client.config.ts` entirely.
- Walk: ramen against the local backend + Mailpit, Playwright reads the mail through Mailpit's API
  (`/api/v1/messages`), then reload, reuse, and a second link in the same tab (`location.hash = …`, same-document
  navigation) — each found a real bug. `/src/icons` SVG components render as objects under Turbopack: reuse inline SVGs.
