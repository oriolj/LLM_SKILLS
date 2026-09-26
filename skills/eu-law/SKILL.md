---
name: eu-law
description: EU + Spanish web-law compliance checklist for shipping websites and SaaS — GDPR/RGPD + LOPDGDD (privacy policy, legal bases, data subject rights, DPAs, international transfers), LSSI-CE (aviso legal, mandatory company identity, email marketing opt-in), ePrivacy/cookies (when a banner is actually required, AEPD rules, reject-as-easy-as-accept), SaaS terms of service (B2B vs B2C, 14-day withdrawal), public-sector accessibility statements (Directive 2016/2102 / RD 1112/2018, European Accessibility Act), AI Act art. 50 transparency, and DSA/NIS2 scoping. Use when launching or auditing a site/app for the Spanish/EU market, adding legal pages (aviso legal, política de privacidad, cookies, términos), deciding whether a cookie banner is needed, wiring analytics consent, sending marketing email, or when the user mentions GDPR, RGPD, LOPD, LSSI, cookies law, aviso legal, privacy policy, AEPD, accessibility statement, AI disclosure, "are we legally compliant?", or EU compliance.
---

# EU / Spanish web-law compliance playbook

Engineering checklist for shipping legally-defensible websites and SaaS
in Spain/EU. **This is not legal advice** — it encodes the common,
well-established requirements so projects launch with the right
structure; a lawyer reviews the result for anything with real exposure.

## First questions to ask about any project

1. Who is the **controller**? Multitenant platform → each client is the
   controller and the platform is its processor; every obligation below
   must then be **templated per tenant** (name, address, contact email,
   in the tenant's language) so each tenant gets compliant pages by default.
2. What visitor data flows exist? (Forms, accounts, analytics, logs, error
   reporting, embeds, payments.) Anything that does not flow needs no paperwork.
3. Any **public-sector** clients? → accessibility statement (below).
4. Any **AI-facing** features? (Chatbots, generated content → AI Act art. 50.)

## The four legal pages and when each is required

| Page | Law | Required when |
|---|---|---|
| **Aviso legal** | LSSI-CE (Ley 34/2002) | ANY site with economic activity (ads, SaaS, e-commerce, freelance portfolio that sells) |
| **Política de privacidad** | GDPR + LOPDGDD (LO 3/2018) | Any personal data processing: signup forms, contact forms, server logs with IPs, analytics |
| **Política de cookies** | ePrivacy (LSSI art. 22.2) | Only if non-essential cookies/storage exist (see cookie decision tree) |
| **Términos y condiciones** | Contract law + consumer law (TRLGDCU) | Selling anything: SaaS subscriptions, e-commerce, paid services |

Link all of them from the footer of every page. i18n: legal pages must
exist in every language the site offers (same binding content).

## Aviso legal (LSSI-CE art. 10) — mandatory identity block

Must state, accessibly and free of charge:

- Razón social / nombre del titular
- NIF / CIF
- Domicilio social (full postal address)
- Email (and any other effective contact channel)
- Registro Mercantil data (tomo, folio, hoja) — companies only
- If the activity is regulated: professional body, license number
- Domain ownership statement

**Placeholder pattern**: when the entity isn't decided yet, ship the
page with visible `[RAZÓN SOCIAL]`-style markers and a tracking issue —
never launch commercial activity with the block missing entirely
(LSSI fines: 30k–150k € for missing identity info).

## Privacy policy (GDPR arts. 13–14) — required contents

Structure as answers to these, in plain language:

1. **Responsable** — who (identity block again) + DPO contact if one exists
2. **Qué datos** — categories collected (account email, company data, logs, payment)
3. **Finalidades y base legal** — one row per purpose:
   - Providing the service → contract (art. 6.1.b)
   - Service emails (alerts the user configured) → contract
   - Marketing email → consent (6.1.a) — see LSSI rules below
   - Security logs → legitimate interest (6.1.f)
   - Invoicing/tax retention → legal obligation (6.1.c)
4. **Conservación** — retention per purpose (e.g. account data until deletion + tax docs 4–6 years)
5. **Destinatarios / encargados** — name processor categories and the big ones explicitly (hosting, email provider, LLM/AI APIs, payments). Each needs a **DPA** (art. 28) — Resend, Stripe, Google Cloud, AWS, Coolify-hosted VPS provider all publish standard DPAs; keep copies.
6. **Transferencias internacionales** — US providers (Resend, Google/Gemini, Stripe, OpenAI/Anthropic): rely on **EU-US Data Privacy Framework** membership when the vendor is certified, otherwise SCCs. Say which mechanism.
7. **Derechos** — access, rectification, erasure, restriction, portability, objection + how to exercise (email) + right to complain to **AEPD** (aepd.es)
8. **Menores** — if not aimed at minors, say 14+ (Spanish threshold) / 16+ (default GDPR)

Supervisory authority to name: ES **AEPD** (Catalan public bodies: **APDCAT**)
· FR **CNIL** · DE the state DPA.

**First layer at every form**: each form that collects personal data shows,
at the point of collection, controller identity, purpose, legal basis,
rights and a link to the full policy (layered approach). Consent-based
forms gate submit on an **unticked** required checkbox.

### GDPR engineering checklist (the parts that are code)

- [ ] Signup collects only what's needed (data minimization)
- [ ] Account deletion path exists (erasure) — cascade or anonymize
- [ ] Data export for portability (JSON dump is fine)
- [ ] Marketing email separate from service email, each marketing send has working unsubscribe (one click, no login)
- [ ] Server/app logs with IPs have a retention cap
- [ ] Personal data sent to LLM APIs? Disclose in policy; prefer vendors with EU processing or DPF; don't send more than needed (e.g. company website text is fine; don't ship the whole user DB)
- [ ] Breach plan: AEPD notification within 72h (art. 33) — know who does it
- [ ] Error monitoring (Sentry/GlitchTip SDKs): `sendDefaultPii: false` / `send_default_pii=False` on client AND server, Session Replay off unless justified; prefer EU data residency

## Cookies (ePrivacy / LSSI art. 22.2 + AEPD guide)

**Decision tree — do you even need a banner?**

1. Site sets **no cookies/localStorage** at all (pure static marketing) → **no banner, no cookie policy needed**. State "no usamos cookies" in the privacy page for transparency. This is achievable and worth engineering for: skip analytics or use a cookieless option.
2. Only **technical/essential** cookies (session auth, CSRF, language chosen by user, cart) → **exempt**: no consent needed, but list them in a cookies page.
3. **Analytics/marketing** cookies (GA4, Meta pixel, hotjar…) → full consent regime:
   - Banner **before** setting them (prior consent, no cookies on landing)
   - **Reject as easy as accept** (AEPD 2023: reject button same layer, same prominence)
   - Granular per-purpose toggles on second layer
   - Consent revocable anytime (footer link "Configurar cookies")
   - No cookie walls for non-subscription content (limited "pay or ok" tolerance, contested)
   - Re-ask at most every 24 months; log consents
4. **Cookieless analytics** (Plausible, self-hosted, no cross-site identifiers) → AEPD/CNIL treat properly configured ones as exempt or low-risk; still disclose in privacy page.

**Engineering rule**: default new marketing sites to tier 1 or 4.
A cookie banner is a conversion tax — don't pay it for vanity metrics.

## Terms of service (SaaS)

Minimum sections: service description; account rules; plans, pricing,
billing & taxes (state VAT treatment); trial terms; acceptable use;
availability disclaimer (no SLA unless sold); IP (customer owns their
data, you own the platform); data protection cross-reference (privacy
policy + DPA for B2B customers); liability cap (typically 12 months of
fees, B2B); termination & data export window; changes to terms
(notice); governing law & jurisdiction (Spanish law; consumer's forum
for B2C, your city's courts for B2B).

**B2C extra (TRLGDCU)**: 14-day withdrawal right for digital services —
handled by making the user expressly waive it when service starts
immediately, or by offering a free trial before charging (cleanest).
B2B-only SaaS can state it's for professionals/companies and skip
consumer provisions — but then don't market to individuals.

## Accessibility statement (public-sector clients)

- Directive (EU) 2016/2102 (ES: RD 1112/2018) requires **public-sector**
  websites to meet WCAG 2.1 AA (EN 301 549) **and publish an accessibility
  statement** with: conformity status, non-accessible content, preparation
  date + method (self-assessment vs audit), feedback channel, enforcement
  pointer. Footer-linked, in every UI language.
- **Never claim full conformity without an audit** — "partially conformant,
  self-assessment" is the honest default; upgrade only after an axe/pa11y
  pass + manual keyboard/screen-reader review.
- Private sector: the European Accessibility Act (Directive 2019/882, in
  force since 2025-06-28) covers e-commerce, banking, transport, e-books —
  check scope before assuming it applies.

## AI Act touchpoints (for AI-features SaaS)

- **Transparency (art. 50, applies from 2026-08-02)**: users must know
  they're interacting with AI when it could be mistaken for a human, and
  AI-generated content presented as real must be disclosed. Chatbots: a
  visible "AI chat" label at first interaction plus a persistent
  "AI-generated answers may contain errors" line near the input.
  Generated summaries/sections/images: a badge + tooltip is enough in UI
  (a "perfil generado con IA" label satisfies the spirit cheaply);
  deepfake-like media needs stronger marking.
- Most SMB SaaS features (scoring, summaries, RAG) are **minimal/limited
  risk** — no conformity assessment; just transparency + GDPR hygiene.
- High-risk list (Annex III: employment screening, credit, biometrics,
  essential services access…) — if the product touches those, stop and
  get counsel.

## Email marketing (LSSI arts. 20–21)

- **Opt-in required** — no unsolicited commercial email. Exception
  (art. 21.2): existing customers, similar products, easy opt-out.
- Every commercial email: identified sender, "publicidad" nature clear,
  working unsubscribe.
- Transactional/service emails (the alerts a user configured) are NOT
  commercial email — no opt-in beyond the service itself, but respect
  the user's notification settings.

## Quick scoping of the rest

- **DSA**: only if you host user-generated content or act as an
  intermediary; B2B-authored content and 1:1 AI chat don't trigger it.
- **NIS2**: essential/important entities only.
- **Business-side paperwork** (not code, but flag it): art. 28 DPA between
  platform and clients; art. 30 record of processing; DPO if public body
  or large-scale processing.

## Launch checklist (copy into the project)

- [ ] Footer links: aviso legal · privacidad · cookies (if any) · términos
- [ ] Identity block real or `[PLACEHOLDER]`-marked with an issue
- [ ] Privacy policy covers every actual processor (grep the codebase for API clients)
- [ ] Cookie audit: open devtools → Application → confirm what's actually set on first load; banner only if needed
- [ ] Signup: link to terms + privacy at the point of registration ("Al registrarte aceptas…")
- [ ] Unsubscribe in marketing emails; notification settings honored
- [ ] Legal pages in every UI language
- [ ] `noindex` NOT set on legal pages (they should be public/indexable)
- [ ] Accessibility statement with feedback channel (public-sector clients)
- [ ] AI disclosures on any chatbot / generated content
- [ ] Multitenant: legal pages templated per tenant and language
- [ ] e2e guards: legal pages return 200 per tenant, footer links exist, no provider iframe before click, cookie count stays 0 (see **zero-cookies**)
- [ ] A `docs/legal-compliance.md` in the repo mapping obligation → implementation → open items, so the next audit starts from facts

## When NOT to use this skill

- US/UK-only products (different regimes: CCPA, UK GDPR nuances)
- Regulated verticals (health, fintech, insurance) — baseline applies
  but sector law dominates; get counsel
- Actual legal disputes, DPIAs for high-risk processing, or contracts
  with enterprise customers — lawyer territory, this skill only
  preps the groundwork
