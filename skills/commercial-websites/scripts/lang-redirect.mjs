// Browser-language negotiation for a multi-language site's root `/`.
// CANONICAL SOURCE: LLM_SKILLS skills/commercial-websites/scripts/lang-redirect.mjs
// (rules: that skill, "Language on the home page"). Projects VENDOR this file
// unchanged (src/lib/lang-redirect.mjs) next to lang-redirect.test.mjs; to
// change behaviour, change it here, bump VERSION, re-vendor everywhere.
// Pure: no host APIs, so the same file serves a Cloudflare Pages Function, a
// Vercel Routing Middleware and the Node build test.
export const VERSION = "2026-10-25";

/**
 * The served locale the visitor prefers most, or null when the header names
 * none (absent, `*` only, or only unserved languages). `*` is ignored: it
 * says "anything", not which. Tags match on the primary subtag (`ca-ES-valencia`
 * → `ca`); q outside 0..1 or malformed drops the entry; ties keep header order.
 */
export function pickLocale(header, locales) {
  if (!header) return null;
  const ranked = header
    .split(",")
    .map((part, i) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params.map((p) => p.trim().toLowerCase()).find((p) => p.startsWith("q="));
      const weight = q === undefined ? 1 : /^(0(\.\d{0,3})?|1(\.0{0,3})?)$/.test(q.slice(2)) ? Number(q.slice(2)) : 0;
      return { lang: tag.trim().toLowerCase().split("-")[0], q: weight, i };
    })
    .filter((x) => x.q > 0 && locales.includes(x.lang))
    .sort((a, b) => b.q - a.q || a.i - b.i);
  return ranked[0]?.lang ?? null;
}

/**
 * Where `/` should send this request, or null to serve the root page as-is.
 *
 * options.locales        served locales, e.g. ["en", "es", "ca"]
 * options.defaultLocale  the locale of the root page (or of the fallback)
 * options.prefixDefault  true when every locale, the default included, lives
 *                        under a prefix (`/en/`): `/` then has no content and
 *                        ALWAYS redirects, to the default when nothing matches
 * options.trailingSlash  true → `/ca/`, false → `/ca` (match the host's rule,
 *                        or every redirect costs a second hop)
 *
 * Order: only GET/HEAD on exactly `/`; an explicit `?lang=<served>` wins
 * (it is stripped from the forwarded query); then, on a site whose root IS
 * the default page, an in-site navigation (same-host Referer) is a choice and
 * is served; then Accept-Language; no match → the default.
 */
export function rootRedirect(request, { locales, defaultLocale, prefixDefault = false, trailingSlash = true }) {
  if (request.method !== "GET" && request.method !== "HEAD") return null;
  const url = new URL(request.url);
  if (url.pathname !== "/") return null;
  const asked = url.searchParams.get("lang")?.toLowerCase();
  url.searchParams.delete("lang");
  const query = url.search;
  const to = (lang) => `/${lang}${trailingSlash ? "/" : ""}${query}`;
  if (asked && locales.includes(asked)) {
    return asked === defaultLocale && !prefixDefault ? null : to(asked);
  }
  if (!prefixDefault && isSameHost(request.headers.get("referer"), url)) return null;
  const lang = pickLocale(request.headers.get("accept-language"), locales) ?? defaultLocale;
  return lang === defaultLocale && !prefixDefault ? null : to(lang);
}

function isSameHost(referer, url) {
  if (!referer) return false;
  try {
    return new URL(referer).host === url.host;
  } catch {
    return false; // a malformed Referer is an outside arrival
  }
}

/** Headers for the 302: never stored, it depends on the visitor. */
export const REDIRECT_HEADERS = { "cache-control": "private, no-store", vary: "Accept-Language, Referer" };

/**
 * Make a served root response honest about what it depends on: private and
 * revalidated on every visit (so the negotiation runs again; 304s and the
 * back-forward cache keep working), Vary appended to the asset's own.
 */
export function markNegotiated(headers) {
  headers.set("cache-control", "private, no-cache");
  headers.append("vary", "Accept-Language, Referer");
  return headers;
}
