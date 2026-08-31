---
name: auth-session-resilience
description: Diagnose and fix "users keep getting logged out" in SPA + JWT apps, and wire login/token-refresh correctly from day one. Use when the user reports "the app logs me out every hour / regularly / randomly", "I have to log in again and again", "logged out when offline / after waking the laptop / on bad wifi", "session expires constantly", or when building or reviewing ANY SPA (React/Ionic/Vue/Astro) + API (Django dj-rest-auth + SimpleJWT, or any JWT backend) login flow, axios/fetch 401 refresh interceptor, or token rotation setup. Covers the dj-rest-auth JWT_AUTH_HTTPONLY empty-refresh trap (refresh:"" in the body -> forced re-login every access-token lifetime), never treating network errors as session expiry, single-flight refresh under ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION (parallel 401s blacklist each other), cross-tab rotation races, the boot-time fetchUser token-wipe trap, server-side token-contract pytest, and the Playwright verification playbook (tampered access token + parallel requests, route-abort offline simulation, dead-session redirect).
---

# Auth session resilience: stop logging users out

Field-tested 2026-08-01 on GoalTracker (Ionic React + Django 5.2 / dj-rest-auth
/ SimpleJWT), where three stacked bugs produced "the SaaS logs me out every
hour, and going offline logs me out instantly". Every rule below was a real
bug, found and verified against the live app.

## The one diagnostic to run FIRST

Before reading any client code, **curl the login endpoint and look at the
actual body**:

```bash
curl -s -X POST https://api.example.com/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"..."}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); \
      print('keys:', list(d)); \
      print('access len:', len(d.get('access','') or '')); \
      print('refresh:', repr(d.get('refresh'))[:60])"
```

If `refresh` is `''` you have found the bug and can stop looking. Do not trust
that the server's auth mode matches what the client reads — verify the
contract empirically.

## Trap 1: dj-rest-auth `JWT_AUTH_HTTPONLY=True` returns `refresh: ""`

With `REST_AUTH = {"USE_JWT": True, "JWT_AUTH_HTTPONLY": True}`, dj-rest-auth
puts the refresh token **only** in an HttpOnly cookie and returns an **empty
string** (not a missing key!) in the login/refresh response body.

A localStorage-based SPA then stores `refresh_token = ""`. Everything works
until the access token expires (default 60 min), at which point the first 401
finds a falsy refresh token and force-logs the user out. Symptom: **logout
exactly once per access-token lifetime, every time** — "the app logs me out
every hour".

It is nasty because:
- `const { access, refresh } = response.data` destructures `""` without error.
- `if ("refresh" in data)` passes. Only a **non-empty** check catches it.
- The cookie-based refresh doesn't work either on a different-origin SPA
  unless you also wire `withCredentials` + `CORS_ALLOW_CREDENTIALS` + cookie
  domains — a half-migrated setup fails silently.

**Fix (localStorage-token SPA):** `JWT_AUTH_HTTPONLY: False`, with a comment
explaining why it must stay False. If you *want* cookie-mode instead, commit
to it fully (axios `withCredentials`, CORS credentials, no localStorage) —
never mix.

**Lock the contract with tests** so nobody re-enables the flag "for security"
and silently breaks every session:

```python
def test_login_returns_usable_tokens_in_the_body(user):
    response = login(APIClient())
    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"], (
        "Empty refresh token forces a re-login every access-token lifetime."
    )

def test_refresh_rotates_and_returns_both_tokens(user):
    refresh = login(client).data["refresh"]
    response = client.post("/api/auth/token/refresh/", {"refresh": refresh})
    assert response.data["access"]
    assert response.data["refresh"]           # rotated token must come back
    assert response.data["refresh"] != refresh

def test_used_refresh_token_is_blacklisted_after_rotation(user):
    # replaying the pre-rotation token must 401
```

## Trap 2: treating network errors as session expiry

The classic broken interceptor:

```ts
} catch {
  // Refresh failed -> logout            <- WRONG: catches EVERYTHING
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.href = '/welcome';
}
```

That `catch` fires for: wifi down, laptop waking from sleep before the
network is up, DNS hiccups, server restarts (5xx), deploy windows. None of
those mean the session is dead — but the user gets logged out on every one.

**Rule: only an explicit 400/401 *response* from the refresh endpoint means
the session is dead.** No response at all (network error) or a 5xx means
"this attempt failed, keep the tokens, fail the one request".

Encode the distinction in a type, not a comment:

```ts
class SessionExpiredError extends Error {}

const requestNewAccessToken = async (): Promise<string> => {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) throw new SessionExpiredError('No refresh token stored');
  try {
    const response = await axios.post(`${baseUrl}/api/auth/token/refresh/`, {
      refresh: refreshToken,
    });
    return saveTokens(response.data);   // stores access + rotated refresh
  } catch (error) {
    const err = error as { response?: { status?: number } };
    if (!err.response) throw error;     // offline/wake-up: NOT expiry
    // cross-tab guard - see Trap 4
    const current = localStorage.getItem('refresh_token');
    if (current && current !== refreshToken) {
      const retry = await axios.post(..., { refresh: current });
      return saveTokens(retry.data);
    }
    if (err.response.status === 400 || err.response.status === 401) {
      throw new SessionExpiredError('Refresh token rejected');
    }
    throw error;                        // 5xx: server hiccup, NOT expiry
  }
};
```

**The same trap wears a different costume on magic-link / one-time-token
pages** (FichaChat, field case 2026-08-31): a check-in page did
`catch { setMessage("Enlace no válido o expirado") }` around its
token-status fetch, so EVERY transport failure — including the API's TLS
cert having silently expired server-side — rendered as "your link
expired". Users and support then chase link-expiry logic while the real
fault is the network/TLS/route layer; it hid a month-long cert outage.
Same rule as above, applied to token flows: only an explicit 4xx
*response* from the token endpoint may claim the token is invalid/used/
expired; no response at all gets its own message ("no se pudo conectar,
inténtalo de nuevo") and ideally a retry. Audit any `catch` on
one-time-token pages exactly like the refresh interceptor.

And in the interceptor, only `SessionExpiredError` logs out:

```ts
} catch (refreshError) {
  if (refreshError instanceof SessionExpiredError) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/welcome';
    return new Promise(() => {});   // never resolves: no error dialogs
  }
  return Promise.reject(error);     // offline/5xx: stay logged in
}
```

## Trap 3: parallel 401s + token rotation = self-inflicted logout

With SimpleJWT's `ROTATE_REFRESH_TOKENS: True` + `BLACKLIST_AFTER_ROTATION:
True` (both good settings, keep them), a refresh token is **single-use**. Any
dashboard that fires several API calls at once will, at the moment the access
token expires, produce several simultaneous 401s. Without a guard, each one
POSTs the *same* refresh token; the first wins and blacklists it, the others
get 401 → "session expired" → logout. Symptom: random-looking logouts that
correlate with token-expiry boundaries and data-heavy screens.

**Fix: single-flight.** All concurrent 401s share one refresh promise:

```ts
let refreshPromise: Promise<string> | null = null;

const refreshAccessToken = (): Promise<string> => {
  if (!refreshPromise) {
    refreshPromise = requestNewAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
};
```

Verify it: count requests to the refresh endpoint in the browser test
(below). The assertion is `refreshCalls === 1`, not "roughly one".

## Trap 4: two tabs share localStorage but not the in-flight promise

Single-flight only dedupes within one tab. Tab A rotates the token; tab B
still holds the old one in a variable and gets 401 on its refresh. Before
declaring the session dead, **re-read localStorage**: if the stored refresh
token differs from the one you just sent, another tab won the race — retry
once with the newer token instead of logging out. (Shown in the Trap 2 code.)

## Trap 5: boot-time "fetch current user" wipes tokens on any error

```ts
fetchUser: async () => {
  try { ... } catch {
    localStorage.removeItem('access_token');    // <- WRONG
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
  }
}
```

This runs on **every app start**. Open the app on a train, or wake the laptop
before wifi reconnects → `/users/me/` fails with a network error → tokens
deleted → login screen. Symptom: "going offline logs me out immediately".

**Rule: the 401-refresh interceptor is the ONLY place that may clear tokens
and redirect.** The boot-time check keeps the cached (persisted) session on
any failure:

```ts
} catch {
  // Offline or server hiccup: keep the cached session. If the tokens are
  // genuinely invalid the interceptor has already redirected to /welcome.
  set({ isLoading: false });
}
```

This requires the user/isAuthenticated state to be persisted (e.g. zustand
`persist`) so the UI has something to show while offline.

## Trap 6: auth endpoints inside the refresh loop

A 401 from `/auth/login/` means wrong credentials, not an expired session.
If the interceptor tries to refresh-and-retry it, a failed login can cascade
into clearing tokens or a redirect loop. Exclude auth endpoints:

```ts
const isAuthEndpoint = originalRequest?.url?.includes('/auth/');
if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) { ... }
```

Also keep the `_retry` flag so a request that 401s *again* after a successful
refresh propagates as an error instead of looping.

## What NOT to do

- **Do not "fix" hourly logouts by extending `ACCESS_TOKEN_LIFETIME`** to
  days/weeks. That papers over a broken refresh path and enlarges the stolen-
  token window. 60-minute access + 30-day rotating refresh is a fine default
  once refresh actually works.
- **Do not disable rotation/blacklisting** to make the race go away —
  single-flight is the fix, rotation is a feature.
- **Do not put the logout redirect in more than one place.** Every extra
  `removeItem('refresh_token')` call site is a future "logs me out randomly"
  bug. Grep for it (see audit).

## Browser verification playbook (Playwright)

Unit tests can't catch these — the failures live in the interplay of
interceptor, storage, parallel requests, and navigation. Drive the real app:

```js
// count refresh calls
let refreshCalls = 0;
page.on('request', (r) => {
  if (r.url().includes('/auth/token/refresh/')) refreshCalls++;
});

// 1. login -> assert localStorage refresh_token length > 50 (non-empty!)

// 2. simulate hourly expiry: corrupt the access token, then load a screen
//    that fires PARALLEL requests
await page.evaluate(() => localStorage.setItem('access_token', 'expired.invalid.token'));
refreshCalls = 0;
await page.goto(`${APP}/app/dashboard`);
// assert: still on the dashboard, access token replaced (3 JWT segments),
// refreshCalls === 1  (single-flight proven)

// 3. simulate offline: block the API, corrupt the access token, navigate
await page.context().route('**/api/**', (route) => route.abort('connectionfailed'));
// assert: NOT redirected to /welcome, refresh_token still in localStorage
await page.context().unroute('**/api/**');
// navigate again -> assert the same session recovers with no login

// 4. genuinely dead session: set refresh_token to garbage, navigate
// assert: DOES redirect to /welcome (the logout path still works)
```

Scenario 4 matters: after making logout harder to trigger, prove you didn't
make it impossible.

## Audit checklist for an existing codebase

- `curl` the login endpoint: is `refresh` non-empty in the body? (Trap 1)
- `grep -rn "JWT_AUTH_HTTPONLY" backend/` — if True with a localStorage
  client, that's the bug. (Trap 1)
- `grep -rn "removeItem.*refresh_token\|removeItem.*access_token" src/` —
  every hit outside the single session-expired branch of the interceptor is a
  logout bug waiting to fire. (Traps 2, 5)
- In the interceptor's refresh `catch`: does it distinguish `!err.response`
  (network) from 400/401 (rejected)? (Trap 2)
- Is there a shared in-flight refresh promise? (Trap 3)
- Does the boot-time user fetch clear tokens in its catch? (Trap 5)
- Are `/auth/` endpoints excluded from the 401-refresh path? (Trap 6)
- Server tests: is there an assertion that login returns a **non-empty**
  refresh token, and that rotation returns the new one? (Trap 1)

## Symptom -> trap mapping

| Symptom | Look at |
|---|---|
| Logged out at a fixed interval after login (e.g. hourly) | Trap 1 (empty refresh), then Trap 2 |
| Logged out when offline / on flaky wifi / waking laptop | Traps 2 and 5 |
| Random logouts on data-heavy screens | Trap 3 (rotation race) |
| Logouts when using two tabs/windows | Trap 4 |
| Logged out at app start only | Trap 5 |
| Redirect loops or logout after a failed login attempt | Trap 6 |
