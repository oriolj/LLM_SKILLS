# RSS feeds (including Podcasting 2.0)

Load this when adding or auditing an RSS / podcast feed. Skip otherwise.

## Baseline RSS 2.0

Worth shipping when the site has a stream of content (blog, news,
podcasts). Required elements:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>...</title>
  <link>...</link>
  <atom:link href="<feed URL>" rel="self" type="application/rss+xml" />
  <description>...</description>
  <language>...</language>
  <lastBuildDate>...</lastBuildDate>
  <item>
    <title>...</title>
    <link>...</link>
    <guid isPermaLink="true">...</guid>
    <pubDate>...</pubDate>
    <description>...</description>
  </item>
  ...
</channel>
</rss>
```

## Podcasting 2.0

Modern podcast apps (PocketCasts, Overcast, Fountain, Castamatic, Apple
Podcasts iOS 26+) expect the Podcasting 2.0 namespace:

```xml
xmlns:podcast="https://podcastindex.org/namespace/1.0"
```

### `<podcast:guid>` — channel-level GUID

UUID v5 over the scheme-stripped feed URL, using the Podcast Index
namespace UUID `ead4c236-bf58-58c6-a2c6-a6b28d128cb6`. Stable
identifier that survives URL moves between http/https and between
hosts.

**Node.js implementation** (20 lines, no external deps):

```ts
import { createHash } from 'node:crypto';

const PODCAST_NAMESPACE = 'ead4c236-bf58-58c6-a2c6-a6b28d128cb6';

function parseUuid(uuid: string): Buffer {
  return Buffer.from(uuid.replace(/-/g, ''), 'hex');
}

function formatUuid(bytes: Buffer): string {
  const hex = bytes.toString('hex');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
}

export function podcastGuid(feedUrl: string): string {
  const name = feedUrl.replace(/^https?:\/\//, '');
  const hash = createHash('sha1')
    .update(parseUuid(PODCAST_NAMESPACE))
    .update(name)
    .digest();
  const bytes = hash.subarray(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x50; // v5
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC 4122 variant
  return formatUuid(bytes);
}
```

**Python equivalent** (for Django / FastAPI):

```python
import uuid
PODCAST_NAMESPACE = uuid.UUID('ead4c236-bf58-58c6-a2c6-a6b28d128cb6')
def podcast_guid(feed_url: str) -> str:
    name = feed_url.replace('https://', '').replace('http://', '')
    return str(uuid.uuid5(PODCAST_NAMESPACE, name))
```

**Cross-check**: both implementations produce identical output for the
same input. Verify with:

```bash
python3 -c "
import uuid
ns = uuid.UUID('ead4c236-bf58-58c6-a2c6-a6b28d128cb6')
print(uuid.uuid5(ns, 'example.com/rss'))
"
```

Emit inside `<channel>`, right after `<atom:link>`:

```xml
<podcast:guid>c765eca7-94b3-5608-989c-fe37422b3ab5</podcast:guid>
```

### `<podcast:chapters>` — per-episode chapters

Point at a JSON endpoint returning the Podcasting 2.0 v1.2.0 chapter
format. Serve with `Content-Type: application/json+chapters`.

```xml
<podcast:chapters url="<chapters URL>" type="application/json+chapters" />
```

Only emit when the episode actually has markers — apps penalize feeds
that point at empty chapter files.

### `<podcast:transcript>` — per-episode transcripts

Point at a VTT or SRT file. VTT is the safer default — every Podcasting
2.0 client that supports transcripts supports VTT, and SRT support is
a strict subset.

```xml
<podcast:transcript url="<transcript URL>" type="text/vtt" language="<lang>" />
```

### `<itunes:*>` essentials

Still required for Apple Podcasts ingestion:

- `<itunes:author>` at channel + item level
- `<itunes:image>` with `href=` attribute (1400×1400 minimum)
- `<itunes:category>` at channel level
- `<itunes:explicit>` (`true` or `false`)
- `<itunes:duration>` per item in seconds (integer) or `HH:MM:SS`
- `<itunes:summary>` per item (plain text, no HTML)

## Reusable helpers

Extract these once, share across all feeds:

```ts
// src/utils/rss.ts
export const rssHeaders = {
  'Content-Type': 'application/rss+xml; charset=utf-8',
  'Cache-Control': 'public, max-age=300, stale-while-revalidate=600',
  'CDN-Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
};

// RFC 822 date required by <pubDate> and <lastBuildDate>
export function rfc822(date: string | Date): string | undefined {
  if (!date) return undefined;
  const d = typeof date === 'string' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return undefined;
  return d.toUTCString();
}

// Minimal XML-safe escape — 5 chars, no he.encode verbosity
export function xmlEscape(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
}
```

Same `xmlEscape` should be shared with the sitemap generator — one
helper, multiple feeds.

## Per-radio / per-tenant feeds

Three types usually worth shipping on a multi-program radio / podcast
network:

| Route | Content |
|-------|---------|
| `/podcasts/<program>/rss.xml` | Per-program feed with iTunes tags, chapters, transcripts, guid |
| `/podcasts/all-episodes/rss.xml` | All episodes across every program (lighter RSS 2.0) |
| `/news/rss.xml` | News articles (RSS 2.0 with per-tag `<category>`, `<enclosure>` image) |

Keep the per-program feed full-featured (iTunes + Podcasting 2.0).
Aggregate feeds stay simpler — they're for cross-program discovery, not
for Apple Podcasts ingestion.

## Common bugs

- **`<pubDate>` in wrong format.** Must be RFC 822
  (`Thu, 23 Apr 2026 10:04:56 GMT`), not ISO 8601. Use `toUTCString()`.
- **`<guid>` changes between fetches.** Apps dedupe on `guid`; a changing
  value creates duplicates. UUID-based guids are safest.
- **Missing `<atom:link rel="self">`.** Apple and Google validators
  flag its absence.
- **Bare URLs without `xmlEscape`** when they contain `&` — common on
  tracked URLs with query parameters.
- **`<enclosure length="0">`** — many apps tolerate it, a few refuse to
  play. Compute `max(duration * bitrate / 8, 1_000_000)` as a fallback
  when you don't know the byte length.
