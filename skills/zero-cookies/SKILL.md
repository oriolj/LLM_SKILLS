---
name: zero-cookies
description: Engineer and audit cookie-free web surfaces — state via localStorage/server-side tokens instead of cookies, so no consent banner is ever needed. Use when building ANY citizen/public-facing surface (widgets, embeds, public chat sites, marketing pages), when the user asks "do we set any cookies", "make this cookie-free", "can we use localStorage instead", "why is Set-Cookie appearing", when adding analytics/fonts/maps/video embeds to a public page, or when reviewing a PR that touches sessions, CSRF, language switching or third-party scripts on public routes. Covers the localStorage-is-also-regulated trap (ePrivacy art. 5(3) applies to ALL terminal storage — necessity is the exemption, not the technology), Django cookie-emission gotchas (sessions, CSRF, messages, i18n), the staff-backoffice exception, third-party embed swaps (youtube-nocookie, self-hosted fonts, cookieless analytics), audit greps, and the Set-Cookie regression test every public route needs. Legal side (when a banner IS required, AEPD rules) lives in the eu-law skill — this one is the build/enforcement counterpart.
---

# Zero cookies: build and enforce cookie-free public surfaces

House rule (portfolio-wide): citizen/public surfaces set **zero cookies** —
no banner to defend, no consent UI, no third-party trackers a town has to
explain. State lives in **localStorage** or server-side keyed by explicit
tokens. The ONLY exception: staff/backoffice logins may use the framework's
strictly-necessary session+CSRF cookies (consent-exempt; still no banner).

## The trap nobody tells you: localStorage is regulated too

ePrivacy art. 5(3) covers *any* storage/access on the user's terminal —
cookies, localStorage, sessionStorage, IndexedDB alike. **The exemption is
NECESSITY, not the technology.** Moving a tracking id from a cookie to
localStorage changes nothing legally.

- ✅ Exempt (strictly necessary / user-requested): a chat's conversation id,
  a user-chosen language, a cart, an offline queue, PWA caches.
- ❌ Not exempt even in localStorage: analytics ids, A/B buckets,
  fingerprints, marketing attribution.

So "zero cookies" really means: **only necessary state, in localStorage,
plus nothing third-party that stores anything.** That combination is what
removes the banner.

## The consent-free localStorage rules (the operating policy)

We don't track users — that stance is what makes consent-free possible.
localStorage needs no consent **when and only when** all of these hold:

1. **The state exists to deliver something the user asked for, right now.**
   A conversation id (so the chat can continue), a user-chosen language, a
   form draft, an offline queue, a PWA cache. If you deleted the key and the
   only thing lost is *our* knowledge about the user — it was tracking.
2. **No identifier outlives its purpose.** The chat session id is meaningless
   once the conversation is over; retention on the server purges it. Never a
   permanent "device id", never "first_seen", never counters of visits.
3. **Nothing is ever sent to a third party or joined across sites/services.**
   Keys are namespaced per product, read only by our own first-party code,
   and never combined into a profile.
4. **The site works without it.** Storage-blocked browsers degrade
   gracefully (new conversation each time, default language) — proof the
   state is convenience, not surveillance.
5. **Measure without identifiers**: aggregate server-side counts (requests,
   answered-rate, top topics) give product metrics with zero terminal
   storage. If a per-user metric ever seems "needed", the answer is no — we
   don't track users.

Say it in the privacy page: «no fem servir galetes ni cap identificador de
seguiment; el navegador només guarda l'estat imprescindible (p. ex. l'id de
la conversa) per oferir el servei».

## localStorage patterns that work

- **Session identity**: mint a UUID server-side (e.g. conversation id),
  return it in the response body, client stores it in localStorage and sends
  it back explicitly (JSON field or header). Never a cookie — and the server
  must treat it as a lookup key, not authentication.
- **Language preference**: `?lang=` query param on server-rendered pages
  (persists via links), or localStorage for client-side widgets. Never the
  framework's language cookie on public routes.
- **Scoping**: namespace keys (`enachat:conversation`, `app:lang`) — embeds
  share the host page's origin storage with everyone else.
- **Embeds/widgets**: localStorage in a widget is per-HOST-origin. Fine for
  per-site continuity; do not expect identity across different town sites —
  that would be tracking anyway.
- sessionStorage when the state should die with the tab (drafts, scroll).
- Wrap access in try/catch: Safari private mode and storage-disabled
  browsers throw; a public widget must degrade, not break.

## Django: where cookies sneak onto public routes

Django only emits cookies when something asks for them — know the askers:

1. **`sessionid`**: set the first time `request.session` is *written*.
   `SessionMiddleware` alone doesn't set it — but `django.contrib.messages`
   (session backend), admin, `auth.login`, or any `request.session[...] = x`
   on a public view does. Keep public views session-free.
2. **`csrftoken`**: set by `{% csrf_token %}` in the template or
   `get_token(request)`. Public GET pages must not render CSRF forms; public
   POST APIs should be `@csrf_exempt` + explicit key auth (the cookie-free
   CORS story: auth via header, wildcard origin is then CSRF-safe).
3. **`django_language`**: `django.views.i18n.set_language` sets it — use
   query-param/dict i18n on public pages instead.
4. **`messages`**: cookie backend writes `messages` cookie — never use the
   messages framework on citizen views.
5. Staff paths (`/admin/`, backoffice logins) legitimately use session+CSRF —
   scope cookie flags there (`SESSION_COOKIE_SECURE`, `HttpOnly`, `SameSite`)
   and don't let shared middleware leak them onto public prefixes.

## Third-party sources of cookies (swap, don't consent)

| Instead of | Use |
|---|---|
| YouTube embed | `youtube-nocookie.com` iframe, or a click-to-load poster |
| Google Fonts runtime | self-hosted woff2 (also faster + private) |
| Google Maps embed | static map image, OSM tile img, or click-to-load |
| GA4 / Meta pixel | cookieless analytics (Plausible/self-hosted, or server-side logs) or none |
| Any `<script src=third-party>` | assume it sets cookies until proven otherwise — read its docs, check Set-Cookie + document.cookie after load |

## Audit checklist (run on every public surface)

- [ ] `curl -sI https://site/every-public-route | grep -i set-cookie` → must
      be empty (script it over the route list, not one URL).
- [ ] Grep the codebase: `document.cookie`, `set_cookie`, `csrf_token`,
      `request.session`, `messages.` on public views/templates.
- [ ] Browser devtools → Application → Storage on a fresh profile after a
      full user journey: Cookies must be empty; localStorage only your
      namespaced, necessary keys.
- [ ] Every third-party request visible in the Network tab is justified (and
      none carries cookies — check the request headers too).
- [ ] Regression test per public route, in CI:
      `assert "Set-Cookie" not in response.headers`.
- [ ] The privacy page says "no usem galetes / no usamos cookies" — the
      transparency line that makes the absence a selling point.

## Review triggers (when to re-run the audit)

Adding: login/auth to anything shared with public routes, a form to a public
page, analytics of any kind, an iframe/embed/font/script from a third party,
i18n switching, Django messages, or middleware that touches `request.session`.
One of these is how a zero-cookie site regresses — never "cookies appeared
by themselves".

## Boundary with eu-law

This skill = build + enforce. The **eu-law** skill owns the legal decision
tree (when a banner IS required, AEPD reject-as-easy-as-accept, cookie-policy
page contents) for surfaces that deliberately do use cookies. If an audit
here finds unavoidable non-essential storage, switch to eu-law for the
consent regime.
