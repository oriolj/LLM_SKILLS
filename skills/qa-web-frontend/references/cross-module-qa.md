# Cross-module QA lessons

Use for broad reviews or investigating whether a known defect occurs elsewhere. Choose a representative path through the application rather than testing every screen shallowly: a master record, a related record, a transaction/draft, and a list/calendar view often expose different behaviour.

## Compare outcomes, not presumed implementations

Apply an equivalent invalid-input scenario to a small sample of sibling forms. Capture whether Save is enabled, whether the editor stays open, the error shown, and the values after reload. Classify each result separately:

- Entire edit rejected; original values retained.
- Invalid field ignored while valid sibling changes persist.
- Invalid data itself persists.
- Save result is ambiguous or still pending.

A failure in one module is a reason to test another, not proof that the other is broken. In the BikeCRM review, customer whitespace-name edits retained the old name but saved notes; product edits with VAT 150 rejected the whole edit. This supports a consistency review without asserting a shared backend root cause. Without a baseline or code comparison, say the issue is present on the deployment, not that the branch introduced it.

## Validation feedback and recovery

- Compare creation and editing: required-field handling may differ. Try an empty/whitespace required name and an omitted numeric field that the UI allows submitting. Do not assume an enabled button means the field is optional.
- Pair a valid sibling edit with the invalid field. After rejection, correct the field and submit once; verify no duplicate or partial record was left by the failed attempt.
- Inspect error messages for untranslated keys, internal property names, wrong display units, and cascades of notifications. A percentage field should explain limits in percentage units, not an unexplained backend fraction.
- If a screenshot shows fragments such as `<`, `!`, `D`, `O` in separate errors, record the exact visible evidence. Treat HTML-response parsing as a hypothesis unless the response was inspected through an available, permitted tool. Do not deliberately trigger an outage to reproduce malformed responses.
- Distinguish correct data rejection from poor feedback. A red field and disabled Save can protect data while still needing an accessible explanation. Do not claim a full accessibility audit from this observation.

## Secondary actions and context restoration

Verify the result promised by each tested control. **Save and add another** must both persist the first record and reach a fresh form; landing on the saved detail only satisfies the first half. Test a clean submission and a correction-after-error path when a difference is suspected. A single recovery-path observation must be reported as such.

When closing a picker, check that the parent page regains its title and context. Follow representative links from parent records and list tabs, not only direct URLs. A quote associated with a customer should be discoverable from that customer's quote tab; a working direct URL does not prove that association.

## Price semantics and locale

Use distinct cost, recommended price and selling price so incorrect field transfer is detectable. For example:

| Scenario | Inputs | Expected result under these rules |
|---|---|---|
| Purchasing at cost | Cost €3.21, VAT 10%, quantity 2 | €7.06 gross, rounding to cents |
| Quoting at selling price | Selling price €20.50 gross, quantity 2 | €41 gross |
| Locale entry | Enter `20,50` in a Spanish price field | Persist numeric value 20.50 |
| Existing quote snapshot | Reprice catalogue to €30 after inserting at €20.50 | Existing quote retains €41 if snapshot semantics apply |

Read labels to establish whether prices include tax. A negative discount may express a markup over recommended price; report the arithmetic and clarify the intended rule before calling it a calculation defect. A discontinued item remaining on an existing quote is different from being offered for a new selection.

## Autosave, reminders and navigation

Wait for an inline edit's save transition to settle before editing the next control in a rerendered row. Reopening/reloading should verify the field and any dependent total/date, not just a success message.

For reminder intervals, check the resulting due date and list membership. Negative months could intentionally backdate a reminder; clarify the rule, then restore a valid future value on QA data. Test overdue/completed filters against known records and restore the original view state. For calendars, distinguish successful week/Today/view navigation from testing event creation, drag-and-drop, timezone handling or capacity arithmetic.

## Keep evidence portable

Put live record URLs and environment-specific IDs in the session report, not in the reusable skill. Carry forward the decision rule and a minimal synthetic example. Record one-off observations and untested variants honestly; do not turn every new finding into a mandatory test for unrelated applications.
