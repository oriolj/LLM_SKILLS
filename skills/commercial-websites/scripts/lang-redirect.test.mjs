// Behaviour of lang-redirect.mjs, in both site shapes. Vendored next to it
// and run by the project's build (`node src/lib/lang-redirect.test.mjs`).
// CANONICAL SOURCE: LLM_SKILLS skills/commercial-websites/scripts/lang-redirect.test.mjs
import assert from "node:assert/strict";
import { pickLocale, rootRedirect, markNegotiated } from "./lang-redirect.mjs";

const LOCALES = ["en", "es", "ca"];
const run = (config, acceptLanguage, { path = "/", method = "GET", ...headers } = {}) => {
  if (acceptLanguage) headers["accept-language"] = acceptLanguage;
  return rootRedirect(new Request(`https://example.org${path}`, { method, headers }), config);
};

// Shape 1: the root IS the default-language page (Panotxa, BikeCRM, EnaSuite).
const rootIsDefault = { locales: LOCALES, defaultLocale: "en" };
const rootCases = [
  // [Accept-Language, expected Location or null, options]
  ["ca-ES,ca;q=0.9,en;q=0.8", "/ca/"],
  ["ca-ES-valencia", "/ca/"],
  ["es-MX,es;q=0.9", "/es/"],
  ["es-419", "/es/"],
  ["fr-FR,fr;q=0.9,es;q=0.8,en;q=0.7", "/es/"],
  ["en-GB,ca;q=0.5", null],
  ["en-US,en;q=0.9,es;q=0.8", null],
  ["ca;q=0.5,es;q=0.9", "/es/"],
  ["ca;Q=0.1,es;Q=0.5", "/es/"],
  ["es;q=0,ca;q=0.3", "/ca/"],
  ["en;q=0.8,es;q=2", null], // q > 1 is invalid: es dropped
  ["es;q=abc,ca;q=0.2", "/ca/"],
  ["*;q=1,es;q=0.5", "/es/"], // `*` names no language
  ["de-DE,fr;q=0.9", null],
  ["*", null],
  [null, null],
  ["ca", null, { referer: "https://example.org/ca/pricing/" }],
  ["ca", "/ca/", { referer: "https://www.google.com/" }],
  ["ca", "/ca/", { referer: "not a url" }],
  ["ca", null, { path: "/?lang=en" }],
  ["en", "/ca/", { path: "/?lang=ca" }],
  ["en", "/ca/?utm_source=x", { path: "/?lang=CA&utm_source=x" }],
  ["ca", "/ca/", { path: "/?lang=xx" }], // unserved value: negotiate
  ["en", "/es/", { path: "/?lang=es", referer: "https://example.org/" }],
  ["ca", "/ca/?utm_source=instagram&utm_medium=bio", { path: "/?utm_source=instagram&utm_medium=bio" }],
  ["ca", "/ca/?utm_term=hello%20world&x=~&sig=a%2Bb", { path: "/?utm_term=hello%20world&x=~&sig=a%2Bb" }], // raw bytes kept
  ["en", "/ca/?a=1&b=2", { path: "/?a=1&lang=ca&b=2" }],
  ["en", "/es/?x=%7E", { path: "/?%6Cang=es&x=%7E" }], // an encoded `lang` key is still `lang`
  ["ca", "/ca/", { path: "/?" }],
  ["es", null, { path: "/pricing/" }],
  ["es", null, { path: "/index.html" }],
  ["ca", null, { method: "POST" }],
  ["ca", "/ca/", { method: "HEAD" }],
];
for (const [al, want, opts] of rootCases) assert.equal(run(rootIsDefault, al, opts), want, `root-is-default ${al} ${JSON.stringify(opts ?? {})}`);

// Shape 2: every locale prefixed, `/` has no content (EnaCast), no trailing slash.
const prefixed = { locales: LOCALES, defaultLocale: "en", prefixDefault: true, trailingSlash: false };
const prefixedCases = [
  ["ca-ES,ca;q=0.9", "/ca"],
  ["en-GB", "/en"],
  [null, "/en"],
  ["de", "/en"],
  ["ca", "/ca", { referer: "https://example.org/en/pricing" }], // no root page to keep
  ["ca", "/en", { path: "/?lang=en" }],
  ["ca", "/en?utm_source=x", { path: "/?lang=en&utm_source=x" }],
  ["es", null, { path: "/es/pricing" }],
  ["es", null, { method: "POST" }],
];
for (const [al, want, opts] of prefixedCases) assert.equal(run(prefixed, al, opts), want, `prefixed ${al} ${JSON.stringify(opts ?? {})}`);

assert.equal(pickLocale("CA-es", LOCALES), "ca", "tags are case-insensitive");
const h = markNegotiated(new Headers({ "cache-control": "public, max-age=600", vary: "Accept-Encoding" }));
assert.equal(h.get("cache-control"), "private, no-cache");
assert.equal(h.get("vary"), "Accept-Encoding, Accept-Language, Referer");

console.log(`lang-redirect ok: ${rootCases.length + prefixedCases.length + 4} checks`);
