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
