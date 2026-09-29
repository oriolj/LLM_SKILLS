---
name: self-service-signup
description: Build or review public self-service signup that creates a new tenant/account (free trials, "try it free", demo accounts), with email confirmation, password setup, Google/social login linking, trial expiry and team notification. Use when adding a signup/trial flow to any SaaS, wiring Google login onto existing accounts, or reviewing one — it carries the account-takeover, lockout and token-leak traps found by six adversarial reviews of the EnaSuite rollout (2026-09-29).
---

# Self-service signup + trials + Google login — the traps

Reference implementation and full contract: EnaSuite
`docs/self-service-signup.md` (§9 + «Review rules»), six products (4 Django +
allauth, 2 Go + x/oauth2/go-oidc), each adversarially reviewed. The anti-bot
kit itself (Tor block, enforced Turnstile, signed challenge, honeypot, caps,
confirm-on-POST) is the global rule in the house CLAUDE.md and the
`commercial-websites` skill; this skill is what goes *around* it.

## Flow shape

- **No tenant or user exists until the confirm POST.** Pending signups live in
  their own table (hashed token, 48 h, single use via
  `UPDATE … WHERE used_at IS NULL RETURNING` / `select_for_update`). The emailed
  link's GET shows a button; mail scanners click links.
- **The password is chosen on the confirm page, never on the signup form.**
  Otherwise: attacker signs up with the victim's email + attacker's password →
  victim clicks «confirm» → account whose password the attacker knows
  (pre-account takeover). Same for any «verify your email» flow of an account
  that already has a password.
- **Existing email → same «check your email» page** + a «you already have an
  account» mail (no enumeration). Don't echo typed-in text (org name) in mails
  sent to a typed-in address — it is a spam/phishing relay from your domain.
- **One provisioning function** for admin-created, password and Google paths,
  one transaction, team notification queued inside it and **deduplicated by
  tenant id, never by subject** (two signups with the same org name are exactly
  the impersonation case the team must see).
- **Trial slugs get a random suffix** (`girona-k7p2`) so a stranger's trial
  never occupies a real customer's clean public URL; support renames on
  activation (keep old slugs redirecting if URLs were shared).

## Google (social) login on EXISTING accounts

- **`email_verified` is only authoritative for gmail.com/googlemail.com or when
  the ID token's `hd` equals the email domain (Workspace).** For any other
  domain Google verified the address *once*; a former holder of a role address
  (`secretaria@town.cat`) can still own a Google account on it. Auto-link only
  in the authoritative cases; otherwise «sign in with your password».
- Where tenant staff can create users, also require an email **you** verified
  (a stranger can create `secretaria@…` in their own trial and catch the real
  owner's later Google login).
- Never auto-link admin/superuser accounts — and re-check on every login, not
  only when linking (an old link survives a promotion).
- Email the owner whenever a link is made; a password reset removes the links.
- Go/hand-rolled OAuth: bind `state`+nonce to the browser (short-lived HttpOnly
  SameSite=Lax cookie set on the click, cleared on callback) — a signed state
  alone allows login CSRF. allauth binds it to the session already.
- allauth: mount only the provider login + callback (404 while unconfigured —
  a missing SocialApp is a 500), and 404 the One Tap `…/login/token/` route.

## Logins, lockouts, backends

- **No global per-hour cap on login flows** (challenge tokens are free: a few
  IPs shadow-reject every real user). Per-IP + per-account only; a rate refusal
  says so, never «wrong credentials».
- A per-account lockout that refuses the correct password needs Turnstile in
  front of it (otherwise anyone keeps a known admin locked out).
- Adding a custom Django auth backend: keep `ModelBackend` listed after it, or
  every live session (which stores the old backend path) is logged out on deploy.
- Route the Django admin login through the same guarded login (including POSTs
  from already-authenticated users).
- Match usernames/emails case-insensitively at login when signup lowercases.

## Tokens must not leak

- Auth-link mail bodies redacted in the email log once delivered (and on
  permanent failure); purge unconfirmed signups/used tokens 7 days after expiry.
- **Analytics records URLs**: a page with a token in its path (magic links,
  confirm/reset links) leaks it to anyone with analytics access. Umami:
  `data-exclude-search="true"` + `data-before-send` redacting secret-looking
  segments (mixed case, ≥20-char alnum run, UUID), or swap the token into the
  session and redirect to a tokenless URL (Django's reset view does).

## Trials

- Lock is **computed** from `trial_ends_at` (a sweep only records the status);
  expired = read-only staff + public 404 + no AI/mail, data kept.
- Every cost path gated **before** enqueueing (uploads, retries, reprocess,
  regenerate, worker-boot orphan resume), counted under a per-tenant lock, over
  the trial window (not calendar months), refunds only for failures before the
  expensive work started (never on a soft time limit), unreadable/spoofed media
  refused for trials. «Extend trial» only on trial/expired; «Activate» restores
  paid defaults (budgets). The read-only gate fails closed and targets the
  tenant being written to, not the user's first tenant.
