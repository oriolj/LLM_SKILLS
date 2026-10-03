# USER_TODO

Things only Oriol can do (or decide) for this repo. One line each; remove
an item when it is done (`git log` is the history).

- [ ] **Commit the Hermes post-checkout driver into the openclaw skill.**
  Copy it from any claw and commit it:
  `scp oriol@petraclaw:~/backups/hermes_post_checkout.py skills/openclaw/scripts/`
  (check it holds no secret first). Then point the update snippet in
  [skills/openclaw/SKILL.md](skills/openclaw/SKILL.md) § Hermes at
  `scripts/hermes_post_checkout.py` instead of `~/backups/`.
  *Why you:* the script exists only on the three VMs, and the review-fix
  session of 2026-10-03 was told to ask before fetching anything from a VM.
  Say "fetch it" and an agent can do the copy and the commit.
  *Blocked until then:* updating Hermes on a rebuilt or new VM. The snippet
  now stops when the driver is missing instead of skipping the config
  migration.
- [ ] **Decide whether LeadHunter should answer "sendable rows of this
  campaign" itself.** For example a `?sendable=1` filter on
  `/api/campaign-accounts/` that re-runs `partition_accounts_for_outreach`
  with the campaign's goal, or account `status` / `relationship_types` /
  `do_not_contact_purposes` on that list's serializer. Until then the
  [leadhunter skill](skills/leadhunter/SKILL.md) § Send list re-implements
  the filter in jq, a copy of `campaigns/goals.py` that can drift.
  *Why you:* it is a product/API change in humans2agents, which another
  session owns. *Blocked until then:* nothing urgent; the jq recipe is the
  interim.
