---
name: qa-web-frontend
description: Perform exploratory and regression QA on web applications through the browser, verifying persisted data and connected workflows. Use for requests such as "test this feature on beta", "do a general QA review", or "check whether this bug happens elsewhere"; deliver reproducible findings, not a code-only review.
---

# Web frontend QA

Test the user-visible feature and the consequences of its changes. Produce evidence that distinguishes a working interface from correctly persisted data. Adapt coverage to the requested feature and risk; do not turn every session into an exhaustive application audit.

## Establish a useful scope

- Identify the target environment, feature, signed-in role/shop or tenant, and visible deployment version or commit when available. A build label identifies the deployment; it does not prove migration correctness.
- Treat `QA_PENDING.md` as a starting point, not a coverage ceiling. Test adjacent workflows, sibling screens using the same controls, and downstream effects that could regress. Choose cases by risk and explain untested boundaries; do not stop after a few easy checklist items when the authorized scope remains runnable.
- Infer a practical scope from the request and available context. Ask only for information that blocks meaningful work. Explicit QA of a beta feature ordinarily supports labelled test records and routine reversible edits within that feature, subject to the tool's action rules.
- Use the available supported browser tools and their current documentation. Follow the user's chosen browser. Do not assume a connector, hidden API, or browser-control implementation exists.
- If testing an entity refactor, catalogue, pricing feature, or dependent records, read [entity-regressions.md](references/entity-regressions.md).
- For a general review or checking whether a defect extends to other modules, read [cross-module-qa.md](references/cross-module-qa.md). Sample comparable workflows and include counterexamples; similar-looking forms need not share save behaviour.

## Run evidence-driven scenarios

Start with the normal workflow, then choose boundary cases and connected workflows that can expose the change's likely failures. Maintain a compact ledger: scenario, inputs, expected result, actual result, persistence check, and status (pass / fail / inconclusive / not tested).

**Select expectations carefully.** Use documented requirements when available. Otherwise state the assumed rule. Duplicate names, negative prices, fractional quantities, and historical name propagation may be intentional; distinguish a product question from a defect. Prefer concrete inconsistencies, lost changes, broken references, and incorrect calculations over speculative warnings.

**Check state transitions, not just clicks.** An enabled Save button is not proof of valid input; a toast or navigation is not proof of successful persistence. After consequential test edits, reopen or reload the record and inspect the relevant fields. For dependent workflows, check the destination's saved values too.

**Treat asynchronous UI correctly.** Use fresh observed state after actions. Search debounce, loading skeletons, detached elements, stale accessibility indices, and briefly missing content are not automatically defects. Let the tool's supported state checks resolve the relevant transition. If a mutation returned ambiguously, inspect whether it already succeeded before retrying; do not create duplicates by replaying Save. After a bounded retry with no reliable result, record the test as inconclusive and continue independent coverage.

**Exercise realistic input.** Include keyboard entry and blur where formatting/validation depends on them. Use actual form controls rather than changing application state through injected code. Inspect screenshots when layout, hidden information, focus, or a visual claim matters. Do not claim a mobile or accessibility audit from a desktop accessibility tree alone.

**Investigate failures proportionally.** Confirm a suspected bug with the smallest safe reproduction or persisted-state check. Record before/after values and the exact error. Separate transient rendering, rejected input, partial saves, and durable corruption. Stop repeating a mutation if it could damage data or create uncertain duplicate effects.

**Separate selection from search verification.** Finding and selecting a visible record proves the selection path works. It does not prove the typed query filtered the list. Check settled counts/results before calling search a pass. Likewise, report an edit as submitted rather than persisted when the field was not rechecked.

## Test data and operational boundaries

- Prefer uniquely labelled records, e.g. `QA <date> <session> <purpose>`, and reuse them across scenarios. Use synthetic contact details only if required; avoid real recipients.
- Keep changes off existing business records where equivalent coverage is possible with QA data. Creating a pack that references an existing service does not require editing that service.
- A QA request does not authorize customer notifications, real payments, invoice issuance, permission changes, or permanent deletion. Apply current tool/action approval rules to those steps; do not invent an additional approval gate for ordinary authorized testing.
- Plan cleanup before creation. Use verified reversible archive/restore mechanisms when appropriate and allowed. If records must remain for evidence or deletion is not authorized, report their exact links and states, including effects on totals, pending work, and inventory. Never report cleanup as complete without checking the resulting state.
- New-record buttons and inline blur may save immediately, even without a final Save action. Inspect the resulting URL/record before repeating them. Track automatically created records as well as deliberately submitted ones; label them promptly. An unpaid or unapproved QA document can still affect dashboards and balances.
- Do not fix the application, deploy, or publish the report to others unless the task includes that work.

## Keep session evidence and the QA queue current

For repository-backed QA, keep a dated, Git-tracked session report in the project's existing QA evidence location and index. Discover those conventions first; use one coordinating report for cross-repository features and link from sibling repositories. Record results as work proceeds, not only in the final chat. Commit only authorized QA files with explicit paths; do not push or deploy unless authorized. If an unresolved merge or another blocker prevents a commit, preserve the report and state that it is uncommitted rather than claiming it is in Git history.

Include the operator, date and actual execution times when captured, environment, tested role/tenant, observed frontend/backend releases (unknown where unavailable), scenario steps/inputs, expected and actual outcomes, persistence checks, pass/fail/partial/inconclusive/not-tested status, evidence links, and test-data/cleanup ledger. Do not substitute checkout HEAD for the deployed release. Save sanitized screenshots for material findings; never archive credentials, authenticated storage or raw customer data. State when evidence was only inspected and not retained.

Record every observed failure and worthwhile improvement, separating confirmed defects, UX suggestions, requirement questions and QA infrastructure gaps. Give defects stable IDs and severity with reproduction steps and impact; give suggestions their rationale without presenting them as bugs. A missing fixture is remaining QA work, not automatically something only the user can do. Continue independent coverage when one scenario is blocked.

Update the canonical `QA_PENDING.md` in the same session. Remove completed checks only for the environment and variants actually verified; retain exact remaining steps for partial checks and link failures to their report. Beta results do not close production-only verification. Keep detailed results in the report and concise remaining work in the queue. Re-check prior findings when returning to the same area; preserve dated evidence rather than erasing earlier outcomes.

## Deliver the report

Lead with the practical assessment, deployment tested, and highest-impact confirmed finding. Scale the detail to the session; link the maintained session report for repository-backed QA; use an inline or local report for work without a repository.

For each confirmed defect include:

- Priority and a title describing the failure, not a guessed root cause.
- Page/entry point, preconditions, and minimal reproduction steps.
- Exact observed result versus expected result, including persisted values.
- User impact, evidence or record links, and a focused regression test/fix recommendation.

Use P1 for a major core-flow blocker or serious data loss, P2 for a material functional inconsistency or credible wrong-result risk, and P3 for minor usability/presentation issues. Explain severity through impact; reserve critical claims for evidence supporting them.

Separate confirmed defects, UX suggestions, and unresolved requirement questions. Include passed scenarios with concrete evidence, untested areas and blockers, and the test-data ledger. Do not imply browser QA proves database reconciliation, tenant isolation, migration rerun safety, backend atomicity, or compatibility with historical data unless those were actually tested. End testing once the scoped coverage and necessary reproductions are complete; list remaining release checks without silently expanding the task.
