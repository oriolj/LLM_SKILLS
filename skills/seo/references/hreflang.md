# Hreflang / international SEO

Load this when the site targets more than one language or more than
one country in the same language (`en-US` vs `en-GB`). Skip otherwise
— hreflang on a single-language site is cargo cult.

The tags are finicky and break quietly — implementations break often.
Validate on every release (validators listed at end of file).

## When you actually need hreflang

- **Parallel translations** of the same content into multiple
  languages (`/es/`, `/fr/`, `/de/` versions of the same article).
- **Same language, different regions** (`en-US` site with different
  pricing than `en-GB` site, or `es-ES` vs `es-MX` with different
  product availability).
- **Not needed** for: single-language sites, pages available only in
  one language, user-generated content where translation coverage is
  inconsistent.

## The rules, strict

### Bidirectional self-references

Every page with hreflang must list:
- A self-reference (the page pointing at itself)
- Every alternate version (every other language/region variant)
- Ideally an `x-default` fallback

Every listed page must list back to every other page in the set.
Missing bidirectionality = Google ignores the whole group.

### Correct ISO codes

- **Language**: lowercase ISO 639-1 — `en`, `es`, `fr`, `de`, `ca`
- **Region** (optional): uppercase ISO 3166-1 alpha-2 — `US`, `GB`,
  `ES`, `MX`, `CA`, `FR`
- **Separator**: hyphen, not underscore — `en-US`, not `en_US`
- **Case matters**: `EN-us` is invalid; must be `en-US`
- **`uk` is wrong for the UK** — the ISO code is `gb`. `en-GB`, not
  `en-UK`.

### Canonical tags don't cross languages

Each language version's `<link rel="canonical">` must point at
**itself**. Not at the "master" English version. Canonicalizing the
Spanish page to the English page tells Google the Spanish page is a
duplicate — which directly contradicts the hreflang annotation. Both
signals fight, Google picks one, you get broken indexing.

Correct:
```html
<!-- on /es/articulo -->
<link rel="canonical" href="https://example.com/es/articulo" />
<link rel="alternate" hreflang="es" href="https://example.com/es/articulo" />
<link rel="alternate" hreflang="en" href="https://example.com/en/article" />
<link rel="alternate" hreflang="x-default" href="https://example.com/en/article" />
```

Wrong:
```html
<!-- on /es/articulo -->
<link rel="canonical" href="https://example.com/en/article" />  <!-- WRONG -->
```

### x-default is a fallback, not a default homepage

`x-default` tells the crawler: "for users whose language/region
doesn't match any other variant, show this page." Common uses:

- A language-picker landing page at `/` that shows "Choose language"
- The English (or native) version as the "everything else" fallback
- A multi-region gateway like `/choose-country`

You don't always need `x-default`. If all your hreflang variants
cover every likely user, skip it.

### Absolute URLs only

`href="https://example.com/es/articulo"` — not `/es/articulo` or
`//example.com/es/articulo`. Relative URLs work in some edge cases
but fail silently in others.

## Three placement options (pick one)

1. **HTML `<link>` tags in `<head>`** — most common, works everywhere.
   Best for SSR pages.
2. **HTTP `Link:` response headers** — for non-HTML assets (PDFs).
   Equivalent content in response header.
3. **XML sitemap annotations** — `<xhtml:link rel="alternate">` inside
   each `<url>` entry. Best for large sites where you don't want to
   bloat every HTML `<head>`. Works well with sitemap-index pattern.

Mixing all three is fine if consistent. Don't emit conflicting
hreflang via two channels.

## Implementation pattern (SSR)

```ts
// Single source of truth: a map of { lang → URL } for the current content
const translations = {
  en: 'https://example.com/en/article',
  es: 'https://example.com/es/articulo',
  fr: 'https://example.com/fr/article',
};
const defaultUrl = translations.en;

// Emit self + all alternates + x-default
for (const [lang, url] of Object.entries(translations)) {
  html += `<link rel="alternate" hreflang="${lang}" href="${url}" />`;
}
html += `<link rel="alternate" hreflang="x-default" href="${defaultUrl}" />`;
```

Every locale's template should emit the *same* alternates array — the
only variable is which URL is "self". This prevents bidirectionality
bugs since the array is shared.

## Common mistakes to audit for

1. **Missing self-reference.** Every page needs `hreflang="<its own
   lang>"` pointing at itself. Validators catch this.
2. **Asymmetric links.** A → B exists but B → A doesn't. Run a
   hreflang audit tool (Screaming Frog, Ahrefs, Sitebulb, Merkle
   Hreflang Tag Testing Tool).
3. **Canonical pointing at different language.** Catastrophic; see
   above. Grep for `rel="canonical"` cross-referencing the wrong URL.
4. **Wrong ISO codes.** `en_US`, `en-UK`, `EN-us`, `es-LATAM`
   (LATAM isn't an ISO code; use `es-419` for "Latin America" via
   the UN M.49 region code, one of the few exceptions).
5. **Emitting hreflang for URLs that 404 or redirect.** Validator
   flags these; the listed URL must resolve 200.
6. **Hreflang on a single-language site.** Zero benefit, some parsers
   get confused. Drop it.
7. **Pages that aren't real translations.** Hreflang is for the same
   content in different languages, not for "similar but regionalized"
   versions where the content actually diverges. Use canonical
   relationships for those, not hreflang.
8. **Different `<title>` / `<meta description>` per language** —
   this is a win, not a bug, but many hreflang setups forget to
   translate the meta tags themselves.

## Verification

```bash
# Pull the hreflang tags off a page
curl -s https://example.com/es/articulo | grep -E 'hreflang|rel="canonical"'

# Merkle hreflang tester: https://technicalseo.com/tools/hreflang/
# Ahrefs Site Audit / Screaming Frog / Sitebulb all have hreflang audits
```

After shipping, watch Google Search Console → Legacy Tools → International
Targeting (if still available) or the Search Console coverage report
for hreflang-related errors.
