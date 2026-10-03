# USER_TODO

Things only Oriol can do (or decide) for this repo. One line each; remove
an item when it is done (`git log` is the history).

- [ ] **Ship the LeadHunter `?sendable=1` filter, then simplify the
  skill.** Decided by Oriol 2026-10-03 (option 2): `/api/campaign-accounts/`
  gets a `sendable` filter that re-runs `partition_accounts_for_outreach`
  with the campaign's goal, so only rows that may be contacted now come
  back. Handed to the humans2agents session (`humans2agents-d3`) to record
  in LeadHunter's queue; implementing and deploying it there needs your
  go, since a push there deploys. Until it ships, the
  [leadhunter skill](skills/leadhunter/SKILL.md) § Send list keeps its jq
  copy of the guardrails. Once it is live, replace that section with the
  one call.
  *Why you:* the change lives in a repo another session owns, and its
  deploy is yours to approve. *Blocked until then:* nothing urgent; the
  jq recipe is the interim.
